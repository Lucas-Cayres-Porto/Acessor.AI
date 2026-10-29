"""
Simulação comparativa das 4 Famílias de Solução para a Etapa 8:
1. Transacionar (Unit of Work)
2. Compensar (Padrão Saga)
3. Adiar (Staging / Two-Phase Action)
4. Interceptar (Pre-Execution Gate)

Testa os dois cenários:
  Cenário A: Aprovado pelo Juiz
  Cenário B: Recusado pelo Juiz (ex: compra em dólares / alucinação)
"""

import sqlite3
import time
from typing import Dict, Any

LATENCIA_SIMULADA_IA = 0.5  # 500ms simulando Orquestrador + API do Juiz JEV


def setup_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, currency TEXT, description TEXT)")
    conn.commit()
    return conn


def imprimir_linha(familia: str, cenario: str, status_banco: str, writes: int, tempo_conexao_ms: float, risco_dirty_read: str):
    print(f"| {familia:<14} | {cenario:<9} | {status_banco:<18} | Writes: {writes} | Conexão presa: {tempo_conexao_ms:>6.1f}ms | Dirty Read: {risco_dirty_read:<5} |")


# ==============================================================================
# 1. TRANSACIONAR (Unit of Work / Long Transaction)
# ==============================================================================
def simular_transacionar(aprovado_pelo_juiz: bool):
    db = setup_db()
    t_inicio_conexao = time.time()
    
    # Tool inicia transação e grava sem commit
    cursor = db.cursor()
    cursor.execute("INSERT INTO transactions (amount, currency, description) VALUES (50.0, 'USD', 'Almoço')")
    writes = 1
    
    # Tempo em que o orquestrador e o juiz JEV estão processando
    time.sleep(LATENCIA_SIMULADA_IA)
    
    if aprovado_pelo_juiz:
        db.commit()
        status = "Gravado definitivo"
    else:
        db.rollback()
        status = "Desfeito (Rollback)"
        
    t_conexao_presa = (time.time() - t_inicio_conexao) * 1000
    db.close()
    return status, writes, t_conexao_presa, "Não (ACID)"


# ==============================================================================
# 2. COMPENSAR (Padrão Saga / Compensating Transaction)
# ==============================================================================
def simular_compensar(aprovado_pelo_juiz: bool):
    db = setup_db()
    writes = 0
    
    # Tool grava e commita imediatamente
    t0 = time.time()
    db.execute("INSERT INTO transactions (amount, currency, description) VALUES (50.0, 'USD', 'Almoço')")
    db.commit()
    writes += 1
    t_conexao_tool = (time.time() - t0) * 1000
    
    # Registra ação compensatória no estado
    compensacao = {"acao": "DELETE", "id": 1}
    
    # Tempo em que orquestrador e juiz pensam (o dado está exposto no banco!)
    time.sleep(LATENCIA_SIMULADA_IA)
    
    t_conexao_compensacao = 0
    if aprovado_pelo_juiz:
        status = "Gravado definitivo"
    else:
        t1 = time.time()
        db.execute("DELETE FROM transactions WHERE id = ?", (compensacao["id"],))
        db.commit()
        writes += 1
        t_conexao_compensacao = (time.time() - t1) * 1000
        status = "Desfeito (Delete)"
        
    db.close()
    return status, writes, (t_conexao_tool + t_conexao_compensacao), "SIM (500ms)"


# ==============================================================================
# 3. ADIAR (Staging / Two-Phase Action)
# ==============================================================================
def simular_adiar(aprovado_pelo_juiz: bool):
    db = setup_db()
    writes = 0
    
    # Tool apenas prepara a ação em memória (Estado Python) - ZERO toque no banco
    escritas_pendentes = [{"amount": 50.0, "currency": "USD", "description": "Almoço"}]
    
    # Tempo de inferência da IA (banco continua 100% livre)
    time.sleep(LATENCIA_SIMULADA_IA)
    
    t_conexao = 0
    if aprovado_pelo_juiz:
        t0 = time.time()
        for item in escritas_pendentes:
            db.execute("INSERT INTO transactions (amount, currency, description) VALUES (?, ?, ?)",
                       (item["amount"], item["currency"], item["description"]))
            writes += 1
        db.commit()
        t_conexao = (time.time() - t0) * 1000
        status = "Gravado definitivo"
    else:
        escritas_pendentes.clear()
        status = "Nenhum dado gravado"
        
    db.close()
    return status, writes, t_conexao, "Não"


# ==============================================================================
# 4. INTERCEPTAR (Pre-Execution Gate)
# ==============================================================================
def simular_interceptar(eh_valido_na_entrada: bool, orquestrador_alucinou: bool):
    db = setup_db()
    writes = 0
    t_conexao = 0
    
    # O interceptador inspeciona antes da tool rodar
    if not eh_valido_na_entrada:
        # Barrado na porta
        db.close()
        return "Barrado na entrada", 0, 0, "Não"
    
    # Se passou pelo interceptor inicial, tool grava
    t0 = time.time()
    db.execute("INSERT INTO transactions (amount, currency, description) VALUES (50.0, 'BRL', 'Almoço')")
    db.commit()
    writes += 1
    t_conexao = (time.time() - t0) * 1000
    
    # Tempo da IA
    time.sleep(LATENCIA_SIMULADA_IA)
    
    # E se o orquestrador alucinar no final?
    if orquestrador_alucinou:
        # Juiz reprova a frase final, mas a tool já comitou!
        status = "FALHA: Banco gravou!"
    else:
        status = "Gravado definitivo"
        
    db.close()
    return status, writes, t_conexao, "Não"


def executar_laboratorio():
    print("=" * 95)
    print("LABORATÓRIO EXPERIMENTAL: COMPARATIVO DAS 4 FAMÍLIAS DE SOLUÇÃO (ETAPA 8)")
    print("=" * 95)
    
    print("\n--- CENÁRIO 1: O JUIZ RECUSA (ex: compra em dólares não apoiada) ---")
    st, wr, tc, dr = simular_transacionar(aprovado_pelo_juiz=False)
    imprimir_linha("Transacionar", "Recusado", st, wr, tc, dr)
    
    st, wr, tc, dr = simular_compensar(aprovado_pelo_juiz=False)
    imprimir_linha("Compensar", "Recusado", st, wr, tc, dr)
    
    st, wr, tc, dr = simular_adiar(aprovado_pelo_juiz=False)
    imprimir_linha("Adiar", "Recusado", st, wr, tc, dr)
    
    st, wr, tc, dr = simular_interceptar(eh_valido_na_entrada=False, orquestrador_alucinou=False)
    imprimir_linha("Interceptar", "Recusado", st, wr, tc, dr)

    print("\n--- CENÁRIO 2: O JUIZ APROVA (operação legítima) ---")
    st, wr, tc, dr = simular_transacionar(aprovado_pelo_juiz=True)
    imprimir_linha("Transacionar", "Aprovado", st, wr, tc, dr)
    
    st, wr, tc, dr = simular_compensar(aprovado_pelo_juiz=True)
    imprimir_linha("Compensar", "Aprovado", st, wr, tc, dr)
    
    st, wr, tc, dr = simular_adiar(aprovado_pelo_juiz=True)
    imprimir_linha("Adiar", "Aprovado", st, wr, tc, dr)
    
    st, wr, tc, dr = simular_interceptar(eh_valido_na_entrada=True, orquestrador_alucinou=False)
    imprimir_linha("Interceptar", "Aprovado", st, wr, tc, dr)

    print("\n--- CENÁRIO 3 (BORDA DO INTERCEPTAR): Aprovado na entrada, mas Orquestrador alucina no final ---")
    st, wr, tc, dr = simular_interceptar(eh_valido_na_entrada=True, orquestrador_alucinou=True)
    imprimir_linha("Interceptar", "Alucinação", st, wr, tc, dr)
    print("=" * 95)


if __name__ == "__main__":
    executar_laboratorio()
