"""
Bateria de Testes Automatizados da Etapa 8: Estratégia de Adiar (Turn Staging Buffer).
Valida o Contrato da Prática:
"SE O TURNO FOR RECUSADO, NENHUMA ESCRITA DESSE TURNO PERMANECE — CRIAÇÃO OU ALTERAÇÃO, NO FINANCEIRO E NA AGENDA."
Utiliza marcadores únicos para comprovação factual no PostgreSQL.
"""

import sys
import uuid
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.tools.db import get_conn
from app.tools.staging import (
    definir_turno_atual,
    obter_turno_atual,
    registrar_operacao,
    obter_operacoes,
    efetivar_operacoes,
    descartar_operacoes,
    limpar_turno_atual,
)
from app.tools.financeiro import add_transaction, update_transaction
from app.tools.agenda import add_event
from app.tools.calendario_google import add_google_event
from app.graph import no_efetivador, Estado


def limpar_marcadores_anteriores(marcador_base: str):
    """Garante ambiente limpo antes de iniciar os testes."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM transactions WHERE source_text LIKE %s", (f"%{marcador_base}%",))
        cur.execute("DELETE FROM events WHERE source_text LIKE %s", (f"%{marcador_base}%",))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def contar_transacoes_por_marcador(marcador: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM transactions WHERE source_text LIKE %s", (f"%{marcador}%",))
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def contar_eventos_por_marcador(marcador: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM events WHERE source_text LIKE %s", (f"%{marcador}%",))
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


# ==============================================================================
# TESTES
# ==============================================================================

def test_01_recusa_add_transaction_staging_zero_writes():
    """
    Cenário 1: Tool add_transaction chamada em turno recusado pelo Juiz.
    Invariante: Zero linhas gravadas no Postgres.
    """
    print("\n[TESTE 01] Recusa em add_transaction -> Zero writes no Postgres")
    marcador = f"ETAPA8_ADIAR_TEST_01_{uuid.uuid4().hex[:6]}"
    turno_id = f"turno_recusa_{uuid.uuid4().hex[:8]}"
    definir_turno_atual(turno_id)

    try:
        # 1. Especialista executa a tool
        res = add_transaction.invoke({
            "amount": 45.0,
            "source_text": f"Gastei 45 dólares em almoço [{marcador}]",
            "type_name": "EXPENSES",
            "category_id": 1,
            "description": "Almoço em dólares não suportado",
        })
        assert res.get("status") == "ok"
        assert res.get("staging") is True
        assert res.get("id") == "(pendente_confirmacao)"

        # 2. Verifica se algo vazou para o Postgres durante a fase de inferência
        count_antes = contar_transacoes_por_marcador(marcador)
        assert count_antes == 0, f"VIOLAÇÃO: Registro foi gravado antes do Juiz! count={count_antes}"

        # 3. Juiz recusa o turno -> nó efetivador purga o buffer
        estado_simulado = {
            "agentes_chamados": ["financeiro", "orquestrador", "guardrail_saida", "juiz:sem_apoio noul=0.15"],
            "messages": [],
        }
        res_efetivador = no_efetivador(estado_simulado)
        assert "efetivador:descarte" in res_efetivador["agentes_chamados"][0]

        # 4. Confirmação factual: Nenhuma linha existe no Postgres
        count_depois = contar_transacoes_por_marcador(marcador)
        assert count_depois == 0, f"VIOLAÇÃO: Registro permaneceu no banco após recusa! count={count_depois}"
        print(f"  -> SUCESSO: Turno recusado. Staging purgado. Linhas no Postgres: {count_depois}")
    finally:
        descartar_operacoes(turno_id)
        limpar_turno_atual()


def test_02_aprovacao_add_transaction_commit_exato():
    """
    Cenário 2: Tool add_transaction chamada em turno aprovado pelo Juiz.
    Invariante: Gravado exatamente uma vez no Postgres.
    """
    print("\n[TESTE 02] Aprovação em add_transaction -> Commit único e atômico")
    marcador = f"ETAPA8_ADIAR_TEST_02_{uuid.uuid4().hex[:6]}"
    turno_id = f"turno_aprovado_{uuid.uuid4().hex[:8]}"
    definir_turno_atual(turno_id)

    try:
        # 1. Especialista executa a tool
        res = add_transaction.invoke({
            "amount": 25.50,
            "source_text": f"Almoço no bandejão R$ 25.50 [{marcador}]",
            "type_name": "EXPENSES",
            "category_id": 1,
            "description": "Almoço legítimo",
        })
        assert res.get("status") == "ok"
        assert res.get("staging") is True

        # Antes do juiz: zero no banco
        assert contar_transacoes_por_marcador(marcador) == 0

        # 2. Juiz aprova o turno -> nó efetivador comita
        estado_simulado = {
            "agentes_chamados": ["financeiro", "orquestrador", "guardrail_saida", "juiz:apoiada noul=0.92"],
            "messages": [],
        }
        res_efetivador = no_efetivador(estado_simulado)
        assert "efetivador:commit:1" in res_efetivador["agentes_chamados"][0]

        # 3. Confirmação factual: Exatamente 1 linha no banco
        count_depois = contar_transacoes_por_marcador(marcador)
        assert count_depois == 1, f"FALHA: Esperado 1 registro, encontrado {count_depois}"
        print(f"  -> SUCESSO: Turno aprovado. Efetivado com commit único. Linhas no Postgres: {count_depois}")
    finally:
        descartar_operacoes(turno_id)
        limpar_turno_atual()


def test_03_recusa_update_transaction_mantem_original():
    """
    Cenário 3: Tool update_transaction chamada em turno recusado pelo Juiz.
    Invariante: O registro existente mantém seus valores originais intactos.
    """
    print("\n[TESTE 03] Recusa em update_transaction -> Registro original preservado intacto")
    marcador = f"ETAPA8_ADIAR_TEST_03_{uuid.uuid4().hex[:6]}"

    # 1. Cria um registro inicial diretamente no banco
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions (amount, type, category_id, description, source_text)
        VALUES (30.0, 2, 1, 'Padaria Original', %s)
        RETURNING id;
        """,
        (f"Gastei 30 na padaria [{marcador}]",)
    )
    transacao_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    turno_id = f"turno_update_recusa_{uuid.uuid4().hex[:8]}"
    definir_turno_atual(turno_id)

    try:
        # 2. Especialista tenta alterar valor para 999.0 em turno com alucinação
        res = update_transaction.invoke({
            "id": transacao_id,
            "amount": 999.0,
            "description": "Tentativa de alteração não suportada",
        })
        assert res.get("status") == "ok"
        assert res.get("staging") is True

        # 3. Juiz recusa o turno
        estado_simulado = {
            "agentes_chamados": ["financeiro", "orquestrador", "guardrail_saida", "juiz:sem_apoio noul=0.10"],
            "messages": [],
        }
        res_efetivador = no_efetivador(estado_simulado)
        assert "efetivador:descarte" in res_efetivador["agentes_chamados"][0]

        # 4. Verifica se o valor original no banco continua 30.0
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT amount, description FROM transactions WHERE id = %s", (transacao_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        assert float(row[0]) == 30.0, f"VIOLAÇÃO: O valor foi modificado para {row[0]} apesar da recusa!"
        assert row[1] == "Padaria Original", f"VIOLAÇÃO: A descrição foi modificada para {row[1]}!"
        print(f"  -> SUCESSO: Registro id={transacao_id} permaneceu intacto com valor R$ {row[0]}.")
    finally:
        descartar_operacoes(turno_id)
        limpar_turno_atual()


def test_04_recusa_add_event_agenda():
    """
    Cenário 4: Tool add_event chamada em turno recusado pelo Juiz.
    Invariante: Zero eventos gravados na tabela events.
    """
    print("\n[TESTE 04] Recusa em add_event -> Zero eventos na tabela events")
    marcador = f"ETAPA8_ADIAR_TEST_04_{uuid.uuid4().hex[:6]}"
    turno_id = f"turno_agenda_recusa_{uuid.uuid4().hex[:8]}"
    definir_turno_atual(turno_id)

    try:
        res = add_event.invoke({
            "title": f"Reunião Fictícia [{marcador}]",
            "source_text": f"Marcar reunião sem horário claro [{marcador}]",
            "start_time": "2026-11-05T14:00:00-03:00",
            "location": "Sala 1",
        })
        assert res.get("status") == "ok"
        assert res.get("staging") is True

        # Antes do juiz: zero no banco
        assert contar_eventos_por_marcador(marcador) == 0

        # Juiz recusa
        estado_simulado = {
            "agentes_chamados": ["agenda", "orquestrador", "guardrail_saida", "juiz:sem_apoio noul=0.20"],
            "messages": [],
        }
        res_efetivador = no_efetivador(estado_simulado)
        assert "efetivador:descarte" in res_efetivador["agentes_chamados"][0]

        # Continua zero no banco
        assert contar_eventos_por_marcador(marcador) == 0
        print(f"  -> SUCESSO: Evento purgado do staging. Total de eventos no Postgres: 0")
    finally:
        descartar_operacoes(turno_id)
        limpar_turno_atual()


def test_05_resiliencia_google_event_descarte():
    """
    Cenário 5: add_google_event enfileirado no staging. Em caso de recusa, executor não dispara.
    """
    print("\n[TESTE 05] Resiliência externa: add_google_event descartado sem chamadas de rede")
    turno_id = f"turno_google_{uuid.uuid4().hex[:8]}"
    definir_turno_atual(turno_id)

    try:
        res = add_google_event.invoke({
            "title": "Dentista Google Staging",
            "start_time": "2026-11-10T10:00:00-03:00",
        })
        assert res.get("status") == "ok"
        assert res.get("staging") is True

        # Verifica se está no buffer
        ops = obter_operacoes(turno_id)
        assert len(ops) == 1
        assert ops[0]["tipo_entidade"] == "google_calendar:create_event"

        # Simula recusa do Juiz
        estado_simulado = {
            "agentes_chamados": ["agenda", "orquestrador", "guardrail_saida", "juiz:sem_chave"],
            "messages": [],
        }
        res_efetivador = no_efetivador(estado_simulado)
        assert "efetivador:descarte" in res_efetivador["agentes_chamados"][0]

        # Buffer purgado
        assert len(obter_operacoes(turno_id)) == 0
        print(f"  -> SUCESSO: Google Calendar não disparou requisições de rede. Staging purgado.")
    finally:
        descartar_operacoes(turno_id)
        limpar_turno_atual()


def executar_bateria():
    print("=" * 80)
    print("INICIANDO BATERIA DE TESTES: ESTRATÉGIA DE ADIAR (ETAPA 8)")
    print("=" * 80)
    
    limpar_marcadores_anteriores("ETAPA8_ADIAR_TEST_")

    test_01_recusa_add_transaction_staging_zero_writes()
    test_02_aprovacao_add_transaction_commit_exato()
    test_03_recusa_update_transaction_mantem_original()
    test_04_recusa_add_event_agenda()
    test_05_resiliencia_google_event_descarte()

    print("\n" + "=" * 80)
    print("TODOS OS 5 CENÁRIOS DE TESTE PASSARAM COM 100% DE SUCESSO!")
    print("A INVARIANTE DA ETAPA 8 FOI RIGOROSAMENTE CUMPRIDA.")
    print("=" * 80)


if __name__ == "__main__":
    executar_bateria()
