import operator
import json
import os
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, MessagesState, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import RemoveMessage

from app.tools.financeiro import TOOLS_FINANCEIRO
from app.tools.memoria import TOOLS_MEMORIA  
from app.tools.agenda import TOOLS_AGENDA  
from app.tools.agenda import TOOLS_AGENDA
from app.tools.calendario_google import TOOLS_GOOGLE
from app.tools.faq import faq_retriever
from app.prompts import (
    ROUTER_PROMPT_COMPLETO,
    FINANCEIRO_PROMPT_COMPLETO,
    AGENDA_PROMPT_COMPLETO,
    ORQUESTRADOR_PROMPT_COMPLETO,
    FAQ_PROMPT_COMPLETO
)
from app.guardrail import guardrail_entrada, guardrail_saida, anonimizar_entrada
from app.memory import salvar_mensagem,  recuperar_historico, iniciar_sessao
from app.llms import llm_rapido, llm_especialista
from langchain_core.runnables import RunnableConfig    

from app.memory import salvar_mensagem
from app.observabilidade import abrir_turno, fechar_turno, status_do_estado
from app.juiz import _coleta, _publicar, _julgar_jev, FRASE_SEGURA
from app.tools.staging import (
    definir_turno_atual,
    obter_turno_atual,
    efetivar_operacoes,
    descartar_operacoes,
    limpar_turno_atual,
)

router_app = create_agent(
    model=llm_rapido,
    tools=TOOLS_MEMORIA,
    system_prompt=ROUTER_PROMPT_COMPLETO,
)

financeiro_app = create_agent(
    model=llm_especialista,
    tools=TOOLS_FINANCEIRO + TOOLS_MEMORIA,
    system_prompt=FINANCEIRO_PROMPT_COMPLETO 
)

agenda_app = create_agent(
    model=llm_especialista,
    tools=TOOLS_AGENDA + TOOLS_GOOGLE + TOOLS_MEMORIA,
    system_prompt=AGENDA_PROMPT_COMPLETO
)

orquestrador_app = create_agent(
    model=llm_rapido,
    system_prompt=ORQUESTRADOR_PROMPT_COMPLETO
)

faq_app = create_agent(
    model=llm_rapido,
    tools=[faq_retriever],
    system_prompt=FAQ_PROMPT_COMPLETO
)

# ==============================================================================
# ESTADO
# ==============================================================================
class Estado(MessagesState):
    agentes_chamados: Annotated[list[str], operator.add]
    rota: str
    status_turno: str
    mapa_pii: dict
    session_id: str
    user_id: str
    resumo_historico: str


def _ultima_mensagem(estado: Estado, tipo: str) -> str:
    for mensagem in reversed(estado["messages"]):
        if getattr(mensagem, "type", None) != tipo:
            continue
        conteudo = getattr(mensagem, "content", "")
        if conteudo:
            return conteudo if isinstance(conteudo, str) else str(conteudo)
    return ""


def _executar_agente(app, nome_agente: str, estado: Estado, config: RunnableConfig = None) -> dict:
    """Executa um agente com a pergunta e o resumo de conversas passadas."""
    pergunta = _ultima_mensagem(estado, "human")
    mensagens = []
    if estado.get("resumo_historico"):
        mensagens.append({
            "role": "system",
            "content": f"Resumo das conversas anteriores deste usuário:\n{estado['resumo_historico']}"
        })
    mensagens.append({"role": "human", "content": pergunta})
    saida = app.invoke({"messages": mensagens}, config=config)
    resposta = _ultima_mensagem(saida, "ai") or _ultima_mensagem(saida, "assistant")
    if not resposta and saida.get("messages"):
        ultimo = saida["messages"][-1]
        resposta = getattr(ultimo, "content", "") if not isinstance(ultimo, dict) else ultimo.get("content", "")
    return {
        "agentes_chamados": [nome_agente],
        "messages": [{"role": "assistant", "content": resposta or ""}],
    }

# ==============================================================================
# NÓS
# ==============================================================================
def no_roteador(estado: Estado, config: RunnableConfig = None) -> dict:
    pergunta_usuario = _ultima_mensagem(estado, "human")
    mensagens = []
    if estado.get("resumo_historico"):
        mensagens.append({
            "role": "system",
            "content": f"Resumo das conversas anteriores deste usuário:\n{estado['resumo_historico']}"
        })
    mensagens.append({"role": "human", "content": pergunta_usuario})
    saida = router_app.invoke(
        {"messages": mensagens}, config=config
    )
    texto = saida["messages"][-1].text if hasattr(saida["messages"][-1], "text") else getattr(saida["messages"][-1], "content", "") 
    
    if "ROUTE=" not in texto:
        
        # salvar_mensagem(session_id=estado["session_id"], role="human", content=pergunta_usuario)
        # salvar_mensagem(session_id=estado["session_id"], role="assistant", content=texto)
        
        return {
            "agentes_chamados": ["roteador"],
            "rota": "fim",
            "messages": [{"role": "assistant", "content": texto}]
        }
    
    rota = "fim"  # Valor padrão caso falhe
    for linha in texto.splitlines():
        if linha.startswith("ROUTE="):
            rota = linha.split("=", 1)[1].strip()
            break
        
    # if rota != "faq":
    #     salvar_mensagem(session_id=estado["session_id"], role="human", content=pergunta_usuario)
        
    return {
        "agentes_chamados": ["roteador"],
        "rota": rota
    }


def no_orquestrador(estado: Estado, config: RunnableConfig) -> dict:
    ultima_especialista = (
        _ultima_mensagem(estado, "ai")
        or _ultima_mensagem(estado, "assistant")
    )
    saida = orquestrador_app.invoke(
        {"messages": [{"role": "human", "content": ultima_especialista}]},
        config=config
    )
    conteudo_saida = saida["messages"][-1].content
    return {
        "agentes_chamados": ["orquestrador"],
        "messages": [{"role": "assistant", "content": conteudo_saida}]
    }

def no_guardrail_entrada(estado: Estado) -> dict:
    pergunta_usuario = _ultima_mensagem(estado, "human")

    pergunta_anonimizada, mapa_pii = anonimizar_entrada(pergunta_usuario)
    resultado_guardrail = guardrail_entrada(pergunta_anonimizada)
    limpar_mensagens = [RemoveMessage(id=mensagem.id) for mensagem in estado["messages"] if hasattr(mensagem, "id") and mensagem.id]

    if resultado_guardrail["bloqueado"]:
        return {
            "agentes_chamados": ["guardrail_entrada"],
            "rota": "fim",
            "status_turno": "bloqueado",
            "messages": limpar_mensagens + [{"role": "assistant", "content": resultado_guardrail["mensagem"]}],
        }

    return {
        "agentes_chamados": ["guardrail_entrada"],
        "rota": "roteador",
        "status_turno": "ok",
        "messages": limpar_mensagens + [
            {"role": "human", "content": pergunta_anonimizada}, 
        ],
        "mapa_pii": mapa_pii,
    }
    
def no_guardrail_saida(estado: Estado) -> dict:
    msg_orig = estado["messages"][-1].content
    resposta_orquestrador = msg_orig if isinstance(msg_orig, str) else str(msg_orig)
    if not resposta_orquestrador.strip():
        resposta_orquestrador = "Não foi possível gerar uma resposta para esta solicitação."
    mapa_pii = estado.get("mapa_pii", {})
    resposta_revisada = guardrail_saida(resposta_orquestrador, mapa_pii, restaurar_pii=False)
    
    return {
        "agentes_chamados": ["guardrail_saida"],
        "rota": "fim",
        "messages": [{"role": "assistant", "content": resposta_revisada["conteudo"]}]
    }

def no_juiz(estado: dict) -> dict:
    pergunta, resposta, evidencia = _coleta(estado)
    if not resposta:
        return {"agentes_chamados": ["juiz:sem_resposta"]}
    try:
        return _julgar_jev(pergunta, resposta, evidencia)
    except Exception as exc:
        print(f"[juiz] erro {exc}")
        return _publicar(FRASE_SEGURA, "erro", resposta)
    


def no_efetivador(estado: Estado) -> dict:
    """
    Commit Gate pós-Juiz (Estratégia de Adiar).
    Se o Juiz aprovou a resposta com fidelidade, efetiva as operações pendentes em bloco no Postgres.
    Se o Juiz reprovou ou ocorreu erro/timeout, purga o Turn Staging Buffer sem tocar no banco.
    """
    turno_id = obter_turno_atual()
    agentes = estado.get("agentes_chamados", [])
    
    aprovado = False
    for agente in agentes:
        if agente.startswith("juiz:apoiada") and "abaixo_do_limiar" not in agente:
            aprovado = True
            break
            
    if aprovado:
        resultado = efetivar_operacoes(turno_id)
        efetivadas = resultado.get("efetivadas", 0)
        return {"agentes_chamados": [f"efetivador:commit:{efetivadas}"]}
    else:
        descartadas = descartar_operacoes(turno_id)
        return {"agentes_chamados": [f"efetivador:descarte:{descartadas}"]}


def decidir_pos_guardrail_entrada(estado: Estado) -> str:
    rota_final = estado["rota"]
    if rota_final == "fim":
        return "fim"
    else:
        return "roteador"
# ==============================================================================
# FUNÇÃO DE DECISÃO
# ==============================================================================
def decidir_especialista(estado: Estado) -> str:
    """Lê o protocolo do roteador e devolve o nome do próximo nó."""
    return estado["rota"] if estado["rota"] in ("financeiro", "agenda", "faq") else "fim"


# ==============================================================================
# CONSTRUÇÃO DO GRAFO
# ==============================================================================
grafo = StateGraph(Estado)

grafo.add_node("roteador",           no_roteador)
grafo.add_node("financeiro",         lambda estado, config: _executar_agente(financeiro_app, "financeiro", estado, config))
grafo.add_node("agenda",             lambda estado, config: _executar_agente(agenda_app, "agenda", estado, config))
grafo.add_node("faq",                lambda estado, config: _executar_agente(faq_app, "faq", estado, config))
grafo.add_node("orquestrador",       no_orquestrador)
grafo.add_node("guardrail_entrada",  no_guardrail_entrada)   
grafo.add_node("guardrail_saida",    no_guardrail_saida)
grafo.add_node("juiz", no_juiz)
grafo.add_node("efetivador", no_efetivador)

grafo.set_entry_point("guardrail_entrada")
grafo.add_conditional_edges(
    "guardrail_entrada",
    decidir_pos_guardrail_entrada,
    {
        "roteador": "roteador",
        "fim":   END
    },
)
grafo.add_conditional_edges(
    "roteador",
    decidir_especialista,
    {
        "financeiro": "financeiro",
        "agenda":     "agenda",
        "faq":        "faq",
        "fim":        END,
    },
)

grafo.add_edge("financeiro",      "orquestrador")
grafo.add_edge("agenda",          "orquestrador")
grafo.add_edge("orquestrador",    "guardrail_saida")
grafo.add_edge("guardrail_saida", "juiz")
grafo.add_edge("faq",             "juiz")
grafo.add_edge("juiz",            "efetivador")
grafo.add_edge("efetivador",      END)

# Grafo compilado sem checkpointer em memória para não acumular agentes entre mensagens diferentes
fluxo_agentes = grafo.compile()


# ==============================================================================
# FLUXO PRINCIPAL
# ==============================================================================
def executar_fluxo_assessor(pergunta_usuario: str, session_id: str, user_id: str = "usuario_teste") -> dict:
    historico = recuperar_historico(user_id=user_id, limite=3)
    resumos_texto = ""
    if historico:
        resumos_texto = "\n".join(
            f"- [{h.get('iniciada_em', '')}] {h.get('resumo', '')}" for h in historico if h.get("resumo")
        )

    estado_inicial = {
        "messages": [{"role": "human", "content": pergunta_usuario}],
        "agentes_chamados": [],
        "rota": "",
        "mapa_pii": {},
        "session_id": session_id,
        "user_id": user_id,
        "resumo_historico": resumos_texto,
    }

    # O registro abre antes do invoke e fecha no finally, inclusive quando
    # o grafo levanta. A rota /monitor só lê o que ficou anotado.
    turno_id = abrir_turno()
    definir_turno_atual(turno_id)
    status = "erro"
    rota = ""

    try:
        estado_final = fluxo_agentes.invoke(
            estado_inicial,
            config={"configurable": {"thread_id": session_id, "user_id": user_id, "turno_id": turno_id}},
        )

        rota = estado_final.get("rota", "")
        resposta_final = estado_final["messages"][-1].content
        salvar_mensagem(session_id=session_id, role="human", content=pergunta_usuario, user_id=user_id)
        salvar_mensagem(session_id=session_id, role="assistant", content=resposta_final, user_id=user_id)
        status = status_do_estado(estado_final)
        agentes_unicos = list(dict.fromkeys(estado_final.get("agentes_chamados", [])))
        return {
            "resposta": resposta_final,
            "agentes_chamados": agentes_unicos,
        }
    finally:
        descartar_operacoes(turno_id)
        limpar_turno_atual()
        fechar_turno(turno_id, session_id=session_id, rota=rota, status=status)



# if __name__ == "__main__":
#     session_id = "123"
#     iniciar_sessao(session_id)
#     while True:
#         pergunta_usuario = input("> ")
#         if pergunta_usuario.lower() in ["sair", "exit", "quit"]:
#             print("Encerrando o assistente.")
#             encerrar_sessao(session_id)
#             break
#         try:
#             resposta = executar_fluxo_assessor(
#                 pergunta_usuario=pergunta_usuario,
#                 session_id=session_id
#             )
            
#             print(resposta)
#         except Exception as e:
#             print(f"Erro: {e}")