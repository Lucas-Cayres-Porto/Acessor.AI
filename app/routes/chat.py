from fastapi import APIRouter
from app.schemas import ChatRequest, ChatResponse
from app.llms import llm_rapido
from app.graph import executar_fluxo_assessor

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)         
def conversar(requisicao: ChatRequest) -> ChatResponse: 
    
    retorno = executar_fluxo_assessor(
        session_id=requisicao.session_id,
        pergunta_usuario=requisicao.pergunta,
        user_id=requisicao.user_id
    )

    if isinstance(retorno, dict):
        return ChatResponse(
            resposta=retorno["resposta"],
            agentes_chamados=retorno.get("agentes_chamados", []),
        )

    return ChatResponse(
        resposta=retorno,
        agentes_chamados=[],
    )