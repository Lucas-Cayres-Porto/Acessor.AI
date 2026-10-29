import sys
from pathlib import Path
from typing import Annotated, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.tools.financeiro import (
    add_transaction as _add_transaction,
    saldo_diario as _saldo_diario,
    saldo_total as _saldo_total,
    search_transactions as _search_transactions,
    update_transaction as _update_transaction,
)

mcp = MCPServer(
    name="assessor-financeiro",
    version="1.0.0",
    instructions="Ferramentas financeiras do Assessor.AI para consulta e registro de transações.",
)

LEITURA = ToolAnnotations(readOnlyHint=True)
ESCRITA = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


@mcp.tool(
    name="query_transactions",
    title="Buscar transações",
    description="Busca histórico de transações financeiras no banco de dados com filtros opcionais.",
    annotations=LEITURA,
)
def query_transactions(
    q: Annotated[Optional[str], Field(description="Busca por palavra-chave na descrição (ex: 'Aluguel').")] = None,
    type_name: Annotated[Optional[str], Field(description="Filtrar por tipo: 'INCOME', 'EXPENSES' ou 'TRANSFER'.")] = None,
    date_local: Annotated[Optional[str], Field(description="Data específica YYYY-MM-DD.")] = None,
    start_date_local: Annotated[Optional[str], Field(description="Data inicial no formato YYYY-MM-DD.")] = None,
    end_date_local: Annotated[Optional[str], Field(description="Data final no formato YYYY-MM-DD.")] = None,
    limit: Annotated[int, Field(description="Quantidade máxima de registros a retornar.")] = 10,
) -> Any:
    return _search_transactions.invoke({
        "q": q,
        "type_name": type_name,
        "date_local": date_local,
        "start_date_local": start_date_local,
        "end_date_local": end_date_local,
        "limit": limit,
    })


@mcp.tool(
    name="daily_balance",
    title="Saldo do dia",
    description="Calcula o resumo financeiro (receitas, despesas e saldo) para uma data específica.",
    annotations=LEITURA,
)
def daily_balance(
    target_date: Annotated[str, Field(description="Data para cálculo do saldo no formato YYYY-MM-DD.")],
) -> Any:
    return _saldo_diario.invoke({"date_local": target_date})


@mcp.tool(
    name="total_balance",
    title="Saldo total",
    description="Calcula o saldo acumulado total de todo o histórico registrado (receitas - despesas).",
    annotations=LEITURA,
)
def total_balance() -> Any:
    return _saldo_total.invoke({})


@mcp.tool(
    name="add_transaction",
    title="Registrar transação",
    description="Registra uma nova transação financeira no banco de dados.",
    annotations=ESCRITA,
)
def add_transaction(
    source_text: Annotated[str, Field(description="Descrição completa da transação.")],
    amount: Annotated[Optional[float], Field(description="Valor numérico da transação (positivo).")] = None,
    type_name: Annotated[Optional[str], Field(description="Tipo: 'INCOME', 'EXPENSES' ou 'TRANSFER'.")] = None,
    category_name: Annotated[Optional[str], Field(description="Nome da categoria em português.")] = None,
    description: Annotated[Optional[str], Field(description="Descrição detalhada.")] = None,
    payment_method: Annotated[Optional[str], Field(description="Meio de pagamento.")] = None,
    occurred_at: Annotated[Optional[str], Field(description="Data e hora ISO 8601.")] = None,
) -> Any:
    return _add_transaction.invoke({
        "source_text": source_text,
        "amount": amount,
        "type_name": type_name,
        "category_name": category_name,
        "description": description,
        "payment_method": payment_method,
        "occurred_at": occurred_at,
    })


@mcp.tool(
    name="update_transaction",
    title="Atualizar transação",
    description="Atualiza uma transação existente no banco de dados.",
    annotations=ESCRITA,
)
def update_transaction(
    id: Annotated[Optional[int], Field(description="ID exato da transação.")] = None,
    match_text: Annotated[Optional[str], Field(description="Texto para buscar a transação.")] = None,
    date_local: Annotated[Optional[str], Field(description="Data YYYY-MM-DD.")] = None,
    amount: Annotated[Optional[float], Field(description="Novo valor.")] = None,
    type_name: Annotated[Optional[str], Field(description="Novo tipo.")] = None,
    category_name: Annotated[Optional[str], Field(description="Nova categoria.")] = None,
    description: Annotated[Optional[str], Field(description="Nova descrição.")] = None,
    payment_method: Annotated[Optional[str], Field(description="Novo meio de pagamento.")] = None,
    occurred_at: Annotated[Optional[str], Field(description="Nova data ISO 8601.")] = None,
) -> Any:
    return _update_transaction.invoke({
        "id": id,
        "match_text": match_text,
        "date_local": date_local,
        "amount": amount,
        "type_name": type_name,
        "category_name": category_name,
        "description": description,
        "payment_method": payment_method,
        "occurred_at": occurred_at,
    })


if __name__ == "__main__":
    from app.config import DATABASE_URL

    if not DATABASE_URL:
        print("[assessor-financeiro] DATABASE_URL ausente no .env", file=sys.stderr)

    mcp.run(transport="stdio")
