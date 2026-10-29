from unittest.mock import patch

import psycopg2
import pymongo
import qdrant_client
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

with patch.object(qdrant_client, "QdrantClient"):
    with patch.object(psycopg2, "connect", side_effect=RuntimeError("Postgres isolado no teste")):
        with patch.object(pymongo, "MongoClient"):
            from app import graph


def test_agente_encaminha_chamadas_e_resultados_de_tools_ao_juiz(monkeypatch):
    tool_call = AIMessage(
        content="Texto auxiliar interno da chamada",
        tool_calls=[{
            "name": "add_event",
            "args": {"title": "Evento de IA", "start": "2026-10-30T14:00:00"},
            "id": "call-1",
            "type": "tool_call",
        }],
    )
    resultado_tool = ToolMessage(
        content='{"status":"ok","staging":true,"title":"Evento de IA"}',
        tool_call_id="call-1",
        name="add_event",
    )

    class AgenteFake:
        def invoke(self, *_args, **_kwargs):
            return {"messages": [
                HumanMessage(content="Adicione um evento amanhã às 14h"),
                tool_call,
                resultado_tool,
                AIMessage(content="Evento de IA adicionado à agenda."),
            ]}

    estado_inicial = {"messages": [HumanMessage(content="Adicione um evento amanhã às 14h")]}
    retorno_agente = graph._executar_agente(AgenteFake(), "agenda", estado_inicial)
    recebido_pelo_jev = {}

    def julgar(pergunta, resposta, evidencia):
        recebido_pelo_jev.update(pergunta=pergunta, resposta=resposta, evidencia=evidencia)
        return {"agentes_chamados": ["juiz:apoiada"]}

    monkeypatch.setattr(graph, "_julgar_jev", julgar)
    estado_do_grafo = {
        **retorno_agente,
        "messages": estado_inicial["messages"] + retorno_agente["messages"],
    }

    graph.no_juiz(estado_do_grafo)

    assert recebido_pelo_jev["resposta"] == "Evento de IA adicionado à agenda."
    assert "[chamada add_event]" in recebido_pelo_jev["evidencia"]
    assert '"title": "Evento de IA"' in recebido_pelo_jev["evidencia"]
    assert "staging" in recebido_pelo_jev["evidencia"]
    assert len(estado_do_grafo["messages"]) == 2
