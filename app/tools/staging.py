"""
Módulo de Staging Buffer (Estratégia de Adiar - Deferred Execution).
Gerencia a fila em memória de operações de escrita do turno (transactions, events e integrações externas)
para que o commit no banco ocorra estritamente após a aprovação do Juiz de Fidelidade (JEV).
"""

from __future__ import annotations

import contextvars
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from app.tools.db import get_conn

_FUSO = ZoneInfo("America/Sao_Paulo")

# Estrutura thread-safe e context-safe para armazenar operações por turno
_lock = threading.Lock()
_buffers: dict[str, list[dict[str, Any]]] = {}
_turno_local = threading.local()
_turno_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("turno_id", default=None)
_turno_ativo_global: Optional[str] = None


def definir_turno_atual(turno_id: str) -> None:
    """Define o identificador do turno para a thread, contextvar e fallback global."""
    global _turno_ativo_global
    _turno_local.turno_id = turno_id
    _turno_cv.set(turno_id)
    with _lock:
        _turno_ativo_global = turno_id


def obter_turno_atual() -> Optional[str]:
    """
    Obtém o identificador do turno ativo com múltiplos níveis de resolução:
    1. ContextVar (propaga em corrotinas e threads de executor do LangChain)
    2. threading.local (thread corrente)
    3. Módulo de observabilidade (_turno_da_thread)
    4. Fallback para o turno ativo global do processo
    """
    # 1. ContextVar
    try:
        tid = _turno_cv.get()
        if tid:
            return tid
    except Exception:
        pass

    # 2. Thread local
    tid = getattr(_turno_local, "turno_id", None)
    if tid:
        return tid

    # 3. Observabilidade
    try:
        from app.observabilidade import _turno_da_thread
        tid = _turno_da_thread()
        if tid:
            return tid
    except Exception:
        pass

    # 4. Turno ativo global mais recente
    with _lock:
        return _turno_ativo_global


def limpar_turno_atual() -> None:
    """Limpa a referência do turno na thread corrente e contextvar."""
    global _turno_ativo_global
    _turno_local.turno_id = None
    _turno_cv.set(None)
    with _lock:
        _turno_ativo_global = None


def registrar_operacao(
    tipo_entidade: str,
    sql: Optional[str] = None,
    params: Optional[tuple | list] = None,
    executor: Optional[Callable[[], Any]] = None,
    dados_evidencia: Optional[dict[str, Any]] = None,
    turno_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Enfileira uma operação de escrita no Turn Staging Buffer sem tocar permanentemente no banco.
    """
    tid = turno_id or obter_turno_atual() or "turno_fallback"
    
    operacao = {
        "id": str(uuid.uuid4()),
        "tipo_entidade": tipo_entidade,
        "sql": sql,
        "params": list(params) if params is not None else [],
        "executor": executor,
        "dados_evidencia": dados_evidencia or {},
        "registrado_em": datetime.now(_FUSO).isoformat(),
    }
    
    with _lock:
        if tid not in _buffers:
            _buffers[tid] = []
        _buffers[tid].append(operacao)
        
    return operacao


def obter_operacoes(turno_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Devolve uma cópia das operações enfileiradas para o turno."""
    tid = turno_id or obter_turno_atual() or "turno_fallback"
    with _lock:
        ops = list(_buffers.get(tid, []))
        if not ops and "turno_fallback" in _buffers:
            ops = list(_buffers.get("turno_fallback", []))
        return ops


def efetivar_operacoes(turno_id: Optional[str] = None) -> dict[str, Any]:
    """
    Executa todas as operações enfileiradas no PostgreSQL em uma única transação atômica (commit)
    e dispara executores externos (ex.: Google Calendar).
    Deve ser chamado APENAS se o Juiz de Fidelidade aprovar o turno.
    """
    tid = turno_id or obter_turno_atual() or "turno_fallback"
    
    with _lock:
        operacoes = _buffers.pop(tid, [])
        # Se a chave específica não tinha nada, verifica se a tool caiu em turno_fallback
        if not operacoes and "turno_fallback" in _buffers:
            operacoes = _buffers.pop("turno_fallback", [])
        
    if not operacoes:
        return {"status": "ok", "efetivadas": 0, "detalhes": []}

    operacoes_sql = [op for op in operacoes if op.get("sql")]
    operacoes_exec = [op for op in operacoes if op.get("executor")]

    # 1. Executa operações do Postgres em transação atômica única
    if operacoes_sql:
        conn = get_conn()
        cur = conn.cursor()
        try:
            for op in operacoes_sql:
                cur.execute(op["sql"], tuple(op["params"]))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Falha ao efetivar operações SQL no staging: {e}") from e
        finally:
            try:
                cur.close()
                conn.close()
            except Exception:
                pass

    # 2. Executa chamadas externas preparadas (ex: Google Calendar)
    resultados_externos = []
    for op in operacoes_exec:
        try:
            fn = op["executor"]
            res = fn() if callable(fn) else None
            resultados_externos.append({"id": op["id"], "resultado": res})
        except Exception as e:
            resultados_externos.append({"id": op["id"], "erro": str(e)})

    return {
        "status": "ok",
        "efetivadas": len(operacoes),
        "total_sql": len(operacoes_sql),
        "total_externo": len(operacoes_exec),
        "resultados_externos": resultados_externos,
    }


def descartar_operacoes(turno_id: Optional[str] = None) -> int:
    """
    Purga e descarta todas as operações enfileiradas no turno. Zero escrita é enviada ao banco.
    Chamado em caso de recusa do Juiz, timeout ou exceção no fluxo.
    """
    tid = turno_id or obter_turno_atual() or "turno_fallback"
    with _lock:
        removidas = len(_buffers.pop(tid, []))
        if "turno_fallback" in _buffers:
            removidas += len(_buffers.pop("turno_fallback", []))
        return removidas
