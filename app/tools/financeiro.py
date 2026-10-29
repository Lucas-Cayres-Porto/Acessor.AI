import os
import psycopg2
from typing import Optional
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from zoneinfo import ZoneInfo
from app.tools.staging import registrar_operacao
from app.tools.db import get_conn




# Criei essa função para pegar todas as categorias que exitema no banco para ele escolher qual vai utilizar
def categoriasDisponiveis():
    categorias = {}
    try:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, name FROM categories")
            resultado = cur.fetchall()
            for linha in resultado:
                categorias[linha[0]] = linha[1]
            return categorias
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"[warning] Não foi possível conectar ao Postgres para carregar categorias: {e}")
        return {}

# Variavel que vai ter todas as categorias do banco
CATEGORYS = categoriasDisponiveis()            



CATEGORY_ALIASES = {
    "comida": "COMIDA", "alimentação": "COMIDA", "alimento": "COMIDA",
    "supermercado": "COMIDA", "mercado": "COMIDA", "mercearia": "COMIDA",
    "feira": "COMIDA", "açougue": "COMIDA", "peixaria": "COMIDA",
    "padaria": "COMIDA", "hortifruti": "COMIDA", "sacolão": "COMIDA",
    "quitanda": "COMIDA", "empório": "COMIDA", "refeição": "COMIDA",
    "marmita": "COMIDA", "rancho": "COMIDA", "mantimentos": "COMIDA",

    "besteira": "BESTEIRA", "ifood": "BESTEIRA", "rappi": "BESTEIRA",
    "ubereats": "BESTEIRA", "aiqfome": "BESTEIRA", "delivery": "BESTEIRA",
    "restaurante": "BESTEIRA", "lanche": "BESTEIRA", "doce": "BESTEIRA",
    "pizza": "BESTEIRA", "hamburguer": "BESTEIRA", "hamburger": "BESTEIRA",
    "mc donalds": "BESTEIRA", "mcdonalds": "BESTEIRA", "burger king": "BESTEIRA",
    "subway": "BESTEIRA", "kfc": "BESTEIRA", "bk": "BESTEIRA",
    "sorvete": "BESTEIRA", "açaí": "BESTEIRA", "salgado": "BESTEIRA",
    "café": "BESTEIRA", "cafeteria": "BESTEIRA", "bolo": "BESTEIRA",
    "chocolate": "BESTEIRA", "biscoito": "BESTEIRA", "snack": "BESTEIRA",
    "pipoca": "BESTEIRA", "junk food": "BESTEIRA",

    "estudo": "ESTUDO", "educação": "ESTUDO", "curso": "ESTUDO",
    "faculdade": "ESTUDO", "universidade": "ESTUDO", "escola": "ESTUDO",
    "livro": "ESTUDO", "livros": "ESTUDO", "apostila": "ESTUDO",
    "mensalidade escolar": "ESTUDO", "mensalidade": "ESTUDO",
    "udemy": "ESTUDO", "alura": "ESTUDO", "coursera": "ESTUDO",
    "duolingo": "ESTUDO", "material escolar": "ESTUDO", "formação": "ESTUDO",
    "pós": "ESTUDO", "pós-graduação": "ESTUDO", "graduação": "ESTUDO",
    "workshop": "ESTUDO", "treinamento": "ESTUDO", "certificação": "ESTUDO",
    "bootcamp": "ESTUDO", "idioma": "ESTUDO", "inglês": "ESTUDO",

    "férias": "FÉRIAS", "viagem": "FÉRIAS", "passagem": "FÉRIAS",
    "hotel": "FÉRIAS", "hospedagem": "FÉRIAS", "turismo": "FÉRIAS",
    "airbnb": "FÉRIAS", "hostel": "FÉRIAS", "pousada": "FÉRIAS",
    "resort": "FÉRIAS", "cruzeiro": "FÉRIAS", "excursão": "FÉRIAS",
    "passeio": "FÉRIAS", "ingresso": "FÉRIAS", "mala": "FÉRIAS",
    "mochila de viagem": "FÉRIAS", "seguro viagem": "FÉRIAS",
    "câmbio": "FÉRIAS", "dólar": "FÉRIAS", "euro": "FÉRIAS",

    "transporte": "TRANSPORTE", "uber": "TRANSPORTE", "99": "TRANSPORTE",
    "99app": "TRANSPORTE", "99pop": "TRANSPORTE", "cabify": "TRANSPORTE",
    "taxi": "TRANSPORTE", "táxi": "TRANSPORTE", "combustível": "TRANSPORTE",
    "gasolina": "TRANSPORTE", "etanol": "TRANSPORTE", "diesel": "TRANSPORTE",
    "estacionamento": "TRANSPORTE", "pedágio": "TRANSPORTE",
    "ônibus": "TRANSPORTE", "metro": "TRANSPORTE", "metrô": "TRANSPORTE",
    "trem": "TRANSPORTE", "barca": "TRANSPORTE", "van": "TRANSPORTE",
    "mototaxi": "TRANSPORTE", "bicicleta": "TRANSPORTE", "patinete": "TRANSPORTE",
    "bilhete único": "TRANSPORTE", "cartão transporte": "TRANSPORTE",
    "ipva": "TRANSPORTE", "seguro auto": "TRANSPORTE", "revisão carro": "TRANSPORTE",
    "oficina": "TRANSPORTE", "borracharia": "TRANSPORTE", "lavagem": "TRANSPORTE",

    "moradia": "MORADIA", "aluguel": "MORADIA", "condomínio": "MORADIA",
    "reforma": "MORADIA", "móveis": "MORADIA", "iptu": "MORADIA",
    "casa": "MORADIA", "apartamento": "MORADIA", "kitnet": "MORADIA",
    "quarto": "MORADIA", "decoração": "MORADIA", "eletrodoméstico": "MORADIA",
    "utensílio": "MORADIA", "limpeza": "MORADIA", "produto de limpeza": "MORADIA",
    "material de construção": "MORADIA", "pintura": "MORADIA",
    "encanador": "MORADIA", "eletricista": "MORADIA", "marceneiro": "MORADIA",
    "zelador": "MORADIA", "portaria": "MORADIA", "taxa condominial": "MORADIA",

    "saúde": "SAÚDE", "farmácia": "SAÚDE", "médico": "SAÚDE",
    "exame": "SAÚDE", "plano de saúde": "SAÚDE", "dentista": "SAÚDE",
    "hospital": "SAÚDE", "clínica": "SAÚDE", "consulta": "SAÚDE",
    "remédio": "SAÚDE", "medicamento": "SAÚDE", "droga": "SAÚDE",
    "drogaria": "SAÚDE", "laboratório": "SAÚDE", "psicólogo": "SAÚDE",
    "psiquiatra": "SAÚDE", "terapeuta": "SAÚDE", "terapia": "SAÚDE",
    "fisioterapia": "SAÚDE", "fisioterapeuta": "SAÚDE", "nutricionista": "SAÚDE",
    "academia": "SAÚDE", "personal": "SAÚDE", "suplemento": "SAÚDE",
    "vitamina": "SAÚDE", "vacina": "SAÚDE", "ótica": "SAÚDE", "óculos": "SAÚDE",

    "lazer": "LAZER", "cinema": "LAZER", "show": "LAZER",
    "streaming": "LAZER", "netflix": "LAZER", "spotify": "LAZER",
    "amazon prime": "LAZER", "disney plus": "LAZER", "disney+": "LAZER",
    "hbo": "LAZER", "paramount": "LAZER", "apple tv": "LAZER",
    "jogos": "LAZER", "videogame": "LAZER", "steam": "LAZER",
    "playstation": "LAZER", "xbox": "LAZER", "nintendo": "LAZER",
    "bar": "LAZER", "balada": "LAZER", "festa": "LAZER", "clube": "LAZER",
    "teatro": "LAZER", "museu": "LAZER", "parque": "LAZER",
    "show musical": "LAZER", "evento": "LAZER", "ingresso show": "LAZER",
    "passeio lazer": "LAZER", "diversão": "LAZER", "entretenimento": "LAZER",
    "barzinho": "LAZER", "pub": "LAZER", "happy hour": "LAZER",

    "contas": "CONTAS", "boleto": "CONTAS", "luz": "CONTAS",
    "energia": "CONTAS", "água": "CONTAS", "internet": "CONTAS",
    "celular": "CONTAS", "gás": "CONTAS", "telefone": "CONTAS",
    "conta de luz": "CONTAS", "conta de água": "CONTAS",
    "conta de gás": "CONTAS", "fatura": "CONTAS", "mensalidade internet": "CONTAS",
    "plano celular": "CONTAS", "tim": "CONTAS", "claro": "CONTAS",
    "vivo": "CONTAS", "oi": "CONTAS", "net": "CONTAS",
    "tv por assinatura": "CONTAS", "sky": "CONTAS", "iptv": "CONTAS",
    "seguro": "CONTAS", "seguro de vida": "CONTAS", "previdência": "CONTAS",

    "investimento": "INVESTIMENTO", "aplicação": "INVESTIMENTO",
    "corretora": "INVESTIMENTO", "ações": "INVESTIMENTO",
    "tesouro": "INVESTIMENTO", "tesouro direto": "INVESTIMENTO",
    "reserva": "INVESTIMENTO", "poupança": "INVESTIMENTO",
    "cdb": "INVESTIMENTO", "lci": "INVESTIMENTO", "lca": "INVESTIMENTO",
    "fii": "INVESTIMENTO", "fundo": "INVESTIMENTO", "fundo de investimento": "INVESTIMENTO",
    "renda fixa": "INVESTIMENTO", "renda variável": "INVESTIMENTO",
    "cripto": "INVESTIMENTO", "bitcoin": "INVESTIMENTO", "ethereum": "INVESTIMENTO",
    "nubank": "INVESTIMENTO", "xp": "INVESTIMENTO", "rico": "INVESTIMENTO",
    "clear": "INVESTIMENTO", "inter": "INVESTIMENTO",

    "presente": "PRESENTE", "doação": "PRESENTE", "aniversário": "PRESENTE",
    "mimo": "PRESENTE", "gift": "PRESENTE", "lembrança": "PRESENTE",
    "natal": "PRESENTE", "dia das mães": "PRESENTE", "dia dos pais": "PRESENTE",
    "casamento": "PRESENTE", "chá de bebê": "PRESENTE", "amigo secreto": "PRESENTE",
    "vaquinha": "PRESENTE", "contribuição": "PRESENTE",

    "roupa": "OUTROS", "vestuário": "OUTROS", "calçado": "OUTROS",
    "tênis": "OUTROS", "sapato": "OUTROS", "bolsa": "OUTROS",
    "acessório": "OUTROS", "beleza": "OUTROS", "cabelo": "OUTROS",
    "salão": "OUTROS", "barbearia": "OUTROS", "manicure": "OUTROS",
    "perfume": "OUTROS", "maquiagem": "OUTROS", "skincare": "OUTROS",
    "shampoo": "OUTROS", "creme": "OUTROS",

    "outros": "OUTROS", "diversos": "OUTROS", "tarifa": "OUTROS",
    "taxa": "OUTROS", "serviço": "OUTROS", "assinatura": "OUTROS",
    "pet": "OUTROS", "veterinário": "OUTROS", "ração": "OUTROS",
    "papelaria": "OUTROS", "impressão": "OUTROS", "cartório": "OUTROS",
    "multa": "OUTROS", "juros": "OUTROS", "iof": "OUTROS",
    "saque": "OUTROS", "transferência": "OUTROS",
}

TYPE_ALIASES = {
    "INCOME":"INCOME","ENTRADA":"INCOME","RECEITA":"INCOME","SALÁRIO":"INCOME",
    "EXPENSE":"EXPENSES","EXPENSES":"EXPENSES","DESPESA":"EXPENSES","GASTO":"EXPENSES",
    'TRANSFER':"TRANSFER","TRANSFERÊNCIA":"TRANSFER","TRANFERENCIA":"TRANSFER"
}



# Essa classe garante que o objeto de Python passe todos esses campos
class AddTransactionArgs(BaseModel):
    amount: float = Field(..., description="Valor da transação (use positivo e NÃO USE ASPAS).")
    source_text: str = Field(..., description="Coloque o texto original do usuario que ele enviou.")
    occurred_at: Optional[str] = Field(
        default=None,
        description="Procure a data que ocorreu a transação em que o usuario informou Timestamp ISO 8601; se ausente, usa NOW() no banco."
    )
    type_id: Optional[int] = Field(default=None, description="ID em transaction_types (1=INCOME, 2=EXPENSES, 3=TRANSFER). (NÃO use aspas)")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER.")
    
    # Para achar a melhor categoria falei para escolher uma das categorias do campo e usar como inspiração a alises para fazer a melhor escolha.
    category_id: Optional[int] = Field(default=None, description=f"Procure o id da categoria que melhor se encaixa no {CATEGORYS} da transação realizada, use o {CATEGORY_ALIASES} como inspiração.")
    description: Optional[str] = Field(default=None, description="Uma descrição da transação (opcional).")
    payment_method: Optional[str] = Field(default=None, description="Forma de pagamento (opcional).")
    
class QueryTransactionsArgs(BaseModel):
    palavra_chave:  Optional[str] = Field(default=None, description="Crie uma palavra chave para descrever as transações procuradas.")
    date_from_local: Optional[str] = Field(
        default=None,
        description=(
            "Datetime de início do filtro no fuso America/Sao_Paulo. "
            "Formato: YYYY-MM-DDTHH:MM:SS-03:00. "
            "Se o usuário informou só a data sem hora, use T00:00:00-03:00. "
            "Se informou hora, use-a. Ex: 'depois das 15h do dia 24' → '2026-03-24T15:00:00-03:00'."
        )
    )
    date_to_local: Optional[str] = Field(
        default=None,
        description=(
            "Datetime de fim do filtro no fuso America/Sao_Paulo. "
            "Formato: YYYY-MM-DDTHH:MM:SS-03:00. "
            "Se o usuário informou só a data sem hora, use T23:59:59-03:00. "
            "Se informou hora, use-a."
        )
    )
    type_id: Optional[int] = Field(default=None, description="ID em transaction_types (1=INCOME, 2=EXPENSES, 3=TRANSFER). (NÃO use aspas)")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo de transação procurada: INCOME | EXPENSES | TRANSFER.")
    



#Garante que o campo type da tabela transactions receba um id válido (1=INCOME, 2=EXPENSES, 3=TRANSFER
def _resolve_type_id(cur, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if type_name:
        t = type_name.strip().upper()
        if t in TYPE_ALIASES:
            t = TYPE_ALIASES[t]
        cur.execute("SELECT id FROM transaction_types WHERE UPPER(type)=%s LIMIT 1;", (t,))
        row = cur.fetchone()
        return row[0] if row else None
    if type_id:
        return int(type_id)
    return 2


# Não estou utilizando esse método mais pois ele nunca acertava o id correto, retornando sempre como outros

def _get_category_id(cur, category_name: Optional[str]) -> Optional[int]:
    if not category_name:
        return None
    cur.execute(
        "SELECT id FROM categories WHERE LOWER(name) = LOWER(%s) LIMIT 1;",
        (category_name,)
    )
    row = cur.fetchone()
    return row[0] if row else None

# def _get_category_id(cur, category_id: Optional[int], category_name: Optional[str]) -> Optional[int]:
#     if category_name:
#         t = category_name.strip().lower()
#         if t in CATEGORY_ALIASES:
#             t = CATEGORY_ALIASES[t]
#         cur.execute("SELECT id FROM categories WHERE LOWER(name)=%s LIMIT 1;", (t,))
#         row = cur.fetchone()
#         return row[0] if row else None
#     if category_id:
#         return int(category_id)
#     return 12

def _local_date_filter_sql(field: str = "occurred_at") -> str:
    """
    Retorna um trecho SQL para filtragem por dia local em America/Sao_Paulo.
    Ex.: (occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date
    """
    return f"(({field} AT TIME ZONE 'America/Sao_Paulo')::date = %s::date)"


# Tool: add_transaction
@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transação financeira no banco de dados Postgres."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    if not resolved_type_id:
        return {"status": "error", "message": "Tipo inválido (use type_id ou type_name: INCOME/EXPENSES/TRANSFER)."}
    elif not category_id:
        return {"status": "error", "message": "Categoria inválida."}

    data_hora = occurred_at or datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()

    sql = """
        INSERT INTO transactions
            (amount, type, category_id, description, payment_method, occurred_at, source_text)
        VALUES
            (%s, %s, %s, %s, %s, %s::timestamptz, %s);
    """
    params = (amount, resolved_type_id, category_id, description, payment_method, data_hora, source_text)

    # Registra no buffer de staging do turno (zero escrita no banco antes do Juiz)
    registrar_operacao(
        tipo_entidade="transactions:insert",
        sql=sql,
        params=params,
        dados_evidencia={
            "amount": amount,
            "type": resolved_type_id,
            "category_id": category_id,
            "description": description,
            "payment_method": payment_method,
            "occurred_at": str(data_hora),
            "source_text": source_text,
        },
    )

    return {
        "status": "ok",
        "staging": True,
        "id": "(pendente_confirmacao)",
        "amount": amount,
        "type": resolved_type_id,
        "occurred_at": str(data_hora),
    }


# Toll: search_transactions
@tool("search_transactions",args_schema=QueryTransactionsArgs)
def search_transactions(
    palavra_chave:  Optional[str],
    date_from_local: Optional[str],
    date_to_local: Optional[str],
    type_id: Optional[int],
    type_name: Optional[str],
) -> dict:
    """
    Consulta transações com filtros por texto (source_text/description), tipo e datas locais(America/Sao_Paulo).
    Os dados dever vir na deguinte ordem:
     - Intervalo(date_from_local/date_to_local): ASC (cronológico).
     - Caso contrário: DESC (mais recentes primeiro).
    """
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
        
        if not resolved_type_id:
            return {"status": "error", "message": "Tipo inválido (use type_id ou type_name: INCOME/EXPENSES/TRANSFER)."}
        
        
        query = "SELECT amount,type,category_id,description,payment_method,occurred_at,source_text FROM transactions WHERE 1=1"
        parametros=[]
        
        if palavra_chave:
            query+=" AND (description ILIKE %s OR source_text ILIKE %s)"
            parametros.extend([f"%{palavra_chave.lower()}%",f"%{palavra_chave.lower()}%"])
        
        if resolved_type_id:
            query+=" AND type = %s"
            parametros.append(resolved_type_id)
        
        if date_from_local:
            query+=" AND occurred_at >= %s::timestamptz"
            parametros.append(date_from_local)
            
        if date_to_local:
            query+=" AND occurred_at <= %s::timestamptz"
            parametros.append(date_to_local)
            
        if date_from_local and date_to_local:
            query += " ORDER BY occurred_at ASC"
        else:
            query += " ORDER BY occurred_at DESC"
            
            
        cur.execute(query,tuple(parametros))
        
        resultado = cur.fetchall()
        
        
        if not resultado:
            return {"status": "ok", "transacoes": "Não foi retornado nenhuma transação com esses filtros."} 
        
        return {"status": "ok", "transacoes": resultado}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
    
# Toll: saldo_total
@tool("saldo_total")
def saldo_total() -> dict:
    """
    Retorna o saldo total (INCOME - EXPENSES) em todo o histórico (ignora TRASFER).
    """   
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 
            SUM(
                CASE 
                    WHEN type = 1 THEN amount  
                    WHEN type = 2 THEN -amount  
                ELSE 0 
                END
            )
            FROM transactions
            WHERE type != 3;
            """
        )
        valor = cur.fetchone()[0]
        
        
        if not valor:
           return {"status": "ok", "saldo": "Você não tem nenhuma transação salva."} 
        
        return {"status": "ok", "saldo": valor}
    
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
   
    
# Toll: saldo_diario
@tool("saldo_diario")
def saldo_diario(date_local: str) -> dict:
    """
    Retorna o saldo total (INCOME - EXPENSES) do dia local informado (YYYY-MM-DD) em America/São Paulo.
    Ignora TRANFER (type=3).
    """         
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 
            SUM(
                CASE 
                    WHEN type = 1 THEN amount  
                    WHEN type = 2 THEN -amount  
                ELSE 0 
                END
            )
            FROM transactions
            WHERE type != 3 AND (occurred_at AT TIME ZONE 'America/Sao_Paulo')::DATE = %s;
            """,
            (date_local,)
        )
        valor = cur.fetchone()[0]
        
        if not valor:
           return {"status": "ok", "saldo": "Não há nenhuma transação registrado hoje"} 
        
        return {"status": "ok", "saldo": valor}
    
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

class UpdateTransactionArgs(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="ID da transação a atualizar. Se ausente, será feita uma busca por (match_text + date_local)."
    )
    match_text: Optional[str] = Field(
        default=None,
        description="Texto para localizar transação quando id não for informado (busca em source_text/description)."
    )
    date_local: Optional[str] = Field(
        default=None,
        description="Data local (YYYY-MM-DD) em America/Sao_Paulo; usado em conjunto com match_text quando id ausente."
    )
    amount: Optional[float] = Field(default=None, description="Novo valor.")
    type_id: Optional[int] = Field(default=None, description="Novo type_id (1/2/3).")
    type_name: Optional[str] = Field(default=None, description="Novo type_name: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="Nova categoria (id).")
    category_name: Optional[str] = Field(default=None, description="Nova categoria (nome).")
    description: Optional[str] = Field(default=None, description="Nova descrição.")
    payment_method: Optional[str] = Field(default=None, description="Novo meio de pagamento.")
    occurred_at: Optional[str] = Field(default=None, description="Novo timestamp ISO 8601.")

@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    id: Optional[int] = None,
    match_text: Optional[str] = None,
    date_local: Optional[str] = None,
    amount: Optional[float] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> dict:
    """
    Atualiza uma transação existente.
    Estratégias:
      - Se 'id' for informado: atualiza diretamente por ID.
      - Caso contrário: localiza a transação mais recente que combine (match_text em source_text/description)
        E (date_local em America/Sao_Paulo).
    Retorna: status, rows_affected, id, e o registro atualizado (em staging).
    """
    if not any([amount, type_id, type_name, category_id, category_name, description, payment_method, occurred_at]):
        return {"status": "error", "message": "Nada para atualizar: forneça pelo menos um campo (amount, type, category, description, payment_method, occurred_at)."}

    conn = get_conn()
    cur = conn.cursor()
    try:
        target_id = id
        if target_id is None:
            if not match_text or not date_local:
                return {"status": "error", "message": "Sem 'id': informe match_text E date_local para localizar o registro."}

            cur.execute(
                f"""
                SELECT t.id
                FROM transactions t
                WHERE (t.source_text ILIKE %s OR t.description ILIKE %s)
                  AND {_local_date_filter_sql("t.occurred_at")}
                ORDER BY t.occurred_at DESC
                LIMIT 1;
                """,
                (f"%{match_text}%", f"%{match_text}%", date_local)
            )
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": "Nenhuma transação encontrada para os filtros fornecidos."}
            target_id = row[0]

        resolved_type_id = _resolve_type_id(cur, type_id, type_name) if (type_id or type_name) else None
        resolved_category_id = category_id
        if category_name and not category_id:
            resolved_category_id = _get_category_id(cur, category_name)

        cur.execute(
            """
            SELECT
              t.id, t.occurred_at, t.amount, tt.type AS type_name,
              c.name AS category_name, t.description, t.payment_method, t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s;
            """,
            (target_id,)
        )
        r = cur.fetchone()
        if not r:
            return {"status": "error", "message": f"Transação id={target_id} não encontrada."}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    sets = []
    params: List[object] = []
    if amount is not None:
        sets.append("amount = %s")
        params.append(amount)
    if resolved_type_id is not None:
        sets.append("type = %s")
        params.append(resolved_type_id)
    if resolved_category_id is not None:
        sets.append("category_id = %s")
        params.append(resolved_category_id)
    if description is not None:
        sets.append("description = %s")
        params.append(description)
    if payment_method is not None:
        sets.append("payment_method = %s")
        params.append(payment_method)
    if occurred_at is not None:
        sets.append("occurred_at = %s::timestamptz")
        params.append(occurred_at)

    if not sets:
        return {"status": "error", "message": "Nenhum campo válido para atualizar."}

    params.append(target_id)
    sql = f"UPDATE transactions SET {', '.join(sets)} WHERE id = %s;"

    updated = {
        "id": r[0],
        "occurred_at": str(occurred_at or r[1]),
        "amount": float(amount if amount is not None else r[2]),
        "type": type_name or r[3],
        "category": category_name or r[4],
        "description": description if description is not None else r[5],
        "payment_method": payment_method if payment_method is not None else r[6],
        "source_text": r[7],
    }

    registrar_operacao(
        tipo_entidade="transactions:update",
        sql=sql,
        params=params,
        dados_evidencia=updated,
    )

    return {
        "status": "ok",
        "staging": True,
        "rows_affected": 1,
        "id": target_id,
        "updated": updated
    }


TOOLS_FINANCEIRO = [add_transaction,search_transactions,saldo_total,saldo_diario,update_transaction]
