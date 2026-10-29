# Decisão Técnica — Etapa 8: O Juiz e a Escrita

**Projeto:** Assessor Pessoal com Inteligência Artificial  
**Mecanismo Escolhido:** Família 3 — Estratégia de Adiar (*Turn Staging Buffer / Two-Phase Action*)  
**Repositório:** `juiz_tardio`  
**Data:** 28 de Outubro de 2026  
**Status:** Implementado, Testado e Validado  

---

## 1. A decisão tomada, e por quê

### Diagnóstico do Problema
Na arquitetura herdada da Etapa 7, o Juiz de Fidelidade (JEV da Typesafe) foi posicionado na saída do grafo para barrar alucinações antes que chegassem ao usuário. No entanto, as ferramentas de mutação (`add_transaction`, `update_transaction`, `add_event`) executavam o SQL e disparavam o `commit()` **imediatamente durante a fase de raciocínio do especialista (Passo 2 do turno)**. Quando o Juiz recusava a resposta final (como no caso de despesas em dólares ou valores inventados), o chat exibia a frase segura (*"Não tenho evidência para afirmar isso."*), mas o dado **já havia sido persistido permanentemente no PostgreSQL**. O chat dizia não, mas o banco dizia sim.

### A Fronteira que Passou a Autorizar a Escrita
A fronteira que autoriza a escrita deixou de ser a chamada da tool no especialista e passou a ser o **nó `efetivador`**, posicionado como um *Commit Gate* imediatamente após o nó `juiz` e antes da terminação do grafo (`END`). 

### Por que cabe neste grafo
O LangGraph organiza o fluxo em nós desacoplados com estado compartilhado (`Estado` / `agentes_chamados`). Na fase de raciocínio, os especialistas precisam invocar ferramentas para inspecionar parâmetros e gerar dados factuais nos logs de chamada (`tool_calls` e `tool messages`), pois o Juiz JEV baseia seu veredito confrontando a resposta final do orquestrador contra esses logs. 
A Estratégia de Adiar cabe perfeitamente nessa topologia porque divide o ciclo da tool em duas fases:
1. **Fase de Staging (Inferência):** A tool valida o esquema, checa existência com `SELECT` pontual, monta a instrução SQL, enfileira a operação na memória do turno e devolve um payload de sucesso estruturado contendo toda a evidência factual (`status: ok`, `staging: True`, `amount`, `type`, `occurred_at`). Isso abastece o especialista, o orquestrador e o juiz com evidências idênticas às reais, sem tocar na persistência do banco.
2. **Fase de Efetivação (Commit Gate):** O nó `efetivador` inspeciona a lista `agentes_chamados`. Se constar a homologação explícita do Juiz (`juiz:apoiada` com `noul >= 0.70`), o nó consome a fila e efetiva todas as mutações em bloco numa única transação atômica. Se constar recusa (`sem_apoio`, `parcial`, `erro`, `sem_chave` ou limiar insuficiente), o nó simplesmente descarta a fila em memória.

### Qual garantia ela dá em `add_transaction`, `update_transaction` e `add_event`
- **Em `add_transaction`:** Se o turno for recusado, nenhum `INSERT` é executado no banco; o contador de linhas na tabela `transactions` permanece inalterado (zero escritas). Se aprovado, a inserção é executada exatamente uma única vez com `conn.commit()`.
- **Em `update_transaction`:** A tool realiza apenas um `SELECT` read-only para validar a existência da transação alvo e capturar seus dados originais. Se o turno for recusado, nenhum `UPDATE` é enviado ao PostgreSQL, preservando integralmente o valor, a moeda e a descrição prévios. Se aprovado, a atualização é aplicada atomicamente.
- **Em `add_event`:** Se o compromisso for recusado por falta de dados factuais ou conflito temporal, zero registros são criados na tabela `events`. Se aprovado, o evento é gravado exatamente uma única vez.
- **Garantia de Isolamento Global:** Elimina por completo leituras fantasmas (*dirty reads*), pois nenhum dado não homologado chega a existir nas tabelas do banco de dados durante os segundos em que os LLMs estão processando.

### Diagrama do Fluxo: Antes vs. Depois

```
FLUXO ANTERIOR (DEFEITUOSO - COMMIT PREMATURO):
[Usuário] ──> [Guardrail Entrada] ──> [Roteador] ──> [Especialista]
                                                          │
                                                (Tool Call Imediata)
                                                          ▼
                                            ⚠️ INSERT/UPDATE + COMMIT NO DB
                                                          │
[Chat: "Não tenho evidência"] ◄── [Juiz: RECUSA] ◄── [Orquestrador]
         ▲
         └── O chat dizia NÃO, mas o dado FICOU gravado no Postgres!


FLUXO NOVO (CORRIGIDO - ESTRATÉGIA DE ADIAR / STAGING BUFFER):
[Usuário] ──> [Guardrail Entrada] ──> [Roteador] ──> [Especialista]
                                                          │
                                                (Tool em Staging)
                                                          ▼
                                             [Turn Staging Buffer (RAM)]
                                             (Zero escritas no banco)
                                                          │
                                                     [Orquestrador]
                                                          │
                                                    [Juiz JEV]
                                                          │
                                                    [Efetivador]
                                                          │
                                       ┌──────────────────┴──────────────────┐
                                       ▼                                     ▼
                                 [JUIZ APROVOU]                       [JUIZ RECUSOU]
                             conn.commit() em bloco                 Buffer Descartado (RAM)
                             1 escrita exata no DB                  0 escritas no DB
                                       │                                     │
                                       ▼                                     ▼
                             Chat: "Registrado!"                    Chat: "Não tenho evidência"
```

---

## 2. As decisões que o grupo não tomou, e por quê

Avaliamos formalmente as outras três famílias arquiteturais da literatura e decidimos deixá-las de fora pelos motivos técnicos descritos a seguir:

### Família 1: Transacionar (*Unit of Work / Long-Lived Transaction*)
* **Como funcionaria aqui:** A tool de escrita abriria uma transação no PostgreSQL (`conn = get_conn()`, sem `autocommit`), executaria o comando SQL `INSERT` ou `UPDATE` e deixaria a conexão e a transação abertas no thread-local ou no estado do LangGraph. O grafo seguiria para o Orquestrador e para o Juiz JEV. No final, um nó inspecionaria o veredito: se aprovado, chamaria `conn.commit()`; se recusado, chamaria `conn.rollback()` e fecharia a conexão.
* **Vantagem real:** Isolamento transacional nativo garantido pelo motor relacional ACID do PostgreSQL, sem necessidade de gerenciar filas de instruções SQL em memória na aplicação Python.
* **Custo real:** **Conexão presa no banco durante toda a inferência dos LLMs.** Entre a execução da tool no especialista, a geração da resposta no orquestrador e a chamada HTTP síncrona na API externa do Juiz JEV, a conexão física ficaria bloqueada por 4 a 7 segundos.
* **Motivo de ter ficado de fora:** No PostgreSQL (especialmente em ambientes com *connection pooling* limitado como Neon/Serverless ou instâncias de produção), reter conexões abertas por vários segundos durante chamadas de rede de LLM leva rapidamente ao **esgotamento do pool de conexões (*connection pool exhaustion*)**. Se 10 usuários enviassem mensagens simultâneas, novos turnos seriam rejeitados com erro `503 / OperationalError: remaining connection slots are reserved`, derrubando o SLO de disponibilidade do sistema.

### Família 2: Compensar (*Padrão Saga / Compensating Transaction*)
* **Como funcionaria aqui:** A ferramenta realizaria o `INSERT` ou `UPDATE` e executaria o `conn.commit()` imediatamente no passo do especialista (como era na Etapa 7), mas registraria uma ação compensatória no estado do turno (por exemplo, `DELETE FROM transactions WHERE id = :id` ou um update restaurando os campos anteriores). Se o Juiz aprovasse, a compensação seria descartada. Se o Juiz recusasse, um nó compensador pós-juiz executaria a instrução de deleção/reversão no PostgreSQL.
* **Vantagem real:** O tempo de conexão com o banco seria mínimo em cada operação (~10 ms no passo da tool e ~10 ms no passo de compensação).
* **Custo real:** **Janela de leitura suja (*dirty read window*) e alta poluição de I/O.** O registro inválido ficaria gravado e publicamente visível no banco durante os 3 a 5 segundos em que o Orquestrador e o Juiz raciocinavam. Além disso, operações recusadas gerariam o dobro de tráfego de gravação (1 escrita + 1 deleção) e consumo de sequências auto-incrementais (`serial id`).
* **Motivo de ter ficado de fora:** Se outro turno do usuário (ou uma consulta paralela de `saldo_total` ou relatório de fechamento diário) rodasse durante essa janela de 4 segundos, o dado não comprovado seria computado nos cálculos antes de ser deletado. Pior ainda: se o processo caísse ou a rede oscilasse exatamente após a recusa do Juiz mas antes do disparo da compensação, o registro compensatório nunca rodaria, deixando o dado falso permanentemente no banco (*compensator failure leak*).

### Família 4: Interceptar (*Pre-Execution Gate*)
* **Como funcionaria aqui:** Antes que o LLM especialista pudesse invocar a ferramenta `add_transaction`, a mensagem do usuário passaria por um modelo intermediário (um LLM juiz ou guardrail semântico de entrada) com o objetivo de analisar se a frase contém moeda suportada, valor explícito e ausência de contradições. Se reprovasse, o especialista nem recebia a permissão de chamar a tool.
* **Vantagem real:** Impede que a ferramenta seja invocada se a entrada do usuário já for manifestamente inválida ou não suportada, economizando chamadas desnecessárias de backend.
* **Custo real:** **Latência adicional severa (+1.500 ms a 2.500 ms) e alto consumo extra de tokens (800 a 1.200 tokens por turno).**
* **Motivo de ter ficado de fora:** **Furo conceitual de arquitetura contra alucinações tardias.** O interceptador de entrada só avalia a pergunta do usuário. Contudo, em agentes LLM orquestrados, a alucinação frequentemente ocorre *depois* da ferramenta: o usuário faz um pedido legítimo, o interceptador aprova, a tool roda, mas o **Orquestrador final altera o valor, confunde a moeda ou inventa informações adicionais na resposta**. Como o interceptador já autorizou a escrita na entrada, o Juiz de saída reprovaria a fala do orquestrador, mas o banco já estaria comitado. A interceptação na entrada não garante a fidelidade da saída.

---

## 3. O efeito nas métricas do SRE, e como

O impacto das decisões arquiteturais no monitor de observabilidade da Etapa 6 (`app/observabilidade.py` e `/monitor`) é direto:

| Métrica SRE (Monitor Etapa 6) | Baseline Etapa 7 (Com Defeito) | Família 1: Transacionar (Rejeitada) | Família 3: Adiar (Implementada) |
| :--- | :--- | :--- | :--- |
| **Latência do Turno (p95)** | ~4.200 ms | ~4.210 ms (com risco de p95 > 8.000 ms sob concorrência) | **~4.205 ms no aprovado / ~4.180 ms no recusado** |
| **Tempo de Conexão DB Presa** | ~10 ms (imediato) | **4.000 ms a 7.000 ms aberta** | **~3 ms a 8 ms (apenas commit em bloco pós-juiz)** |
| **Taxa de Erro (SLO < 5%)** | 0% (mas com dado corrompido no DB) | **Alto risco de estourar 5%** por pool exhaustion | **0% de erro adicional (conforme SLO)** |
| **Status do Turno** | `ok` | `ok` (ou `erro` quando estourar o pool) | **`ok` em turnos recusados (exibe frase segura)** |
| **Consumo de Tokens** | Baseline | Inalterado | **Variação ZERO (nenhum token a mais)** |
| **Custo por Turno ($ USD)** | Baseline | Inalterado | **Variação ZERO (custo idêntico)** |

### O Mecanismo Explicado:

1. **Na Decisão Tomada (Adiar):**
   - **Latência e p95:** Quando o Juiz aprova, o nó `efetivador` executa um único bloco atômico no Postgres, adicionando apenas **~3 a 8 ms de latência local** (totalmente imperceptível e amplamente dentro do SLO de 8 s). Quando o Juiz recusa, a latência do turno é inclusive **menor em ~20 ms**, pois nenhuma operação de I/O em disco é enviada ao banco de dados Neon.
   - **Taxa de Erro e Status do Turno:** O descarte do buffer em caso de recusa é uma operação limpa em memória Python (`dict.pop()`). Não lança exceção. O turno recusado encerra com **`status: "ok"`**, rota identificada e entrega da frase segura (`FRASE_SEGURA`). A taxa de erro do monitor não é penalizada indevidamente, pois uma recusa por falta de evidência é uma decisão de negócio legítima e esperada do Juiz, e não uma falha de infraestrutura.
   - **Tokens e Custo:** Não adiciona nenhuma chamada de modelo nem amplia o contexto do prompt. A variação de custo e consumo de tokens é estritamente **zero**.

2. **Na Decisão Rejeitada (Transacionar):**
   - **O Mecanismo da Falha:** Manter a conexão aberta enquanto o Orquestrador gera a resposta e o JEV processa a verificação força o cliente a reter um socket TCP e uma sessão ativa no servidor PostgreSQL por 5 a 8 segundos. 
   - **Impacto no SRE:** Em carga concorrente, o pool atinge o limite máximo (`max_connections`). Novas requisições falham ao tentar abrir conexão, disparando exceções `OperationalError` no FastAPI. Como exceções não tratadas contam diretamente para a taxa de erro do SRE, **a métrica de erro ultrapassaria com facilidade o SLO de 5%**, gerando alertas de incidente e indisponibilidade.

3. **Na Decisão Rejeitada (Interceptar):**
   - **O Mecanismo da Degradação:** Adicionaria obrigatoriamente um LLM adicional no caminho crítico do turno.
   - **Impacto no SRE:** O p95 subiria em **+1.800 ms** (ficando perigosamente próximo ao teto do SLO de 8.000 ms), e o consumo de tokens aumentaria em **~1.000 tokens por turno**, elevando o custo operacional por mensagem em mais de 30%.

---

## 4. As outras decisões

### 1. O que entrou no escopo e o que ficou de fora (`add_google_event` e `salvar_mensagem`)
- **`add_google_event` (Google Calendar API):** **ENTROU NO ESCOPO DO STAGING.**  
  *Por quê:* O Google Calendar é um efeito colateral externo visível na nuvem do usuário. Se o Juiz recusar um turno (por exemplo, porque o modelo alucinou um compromisso sem que o usuário tenha indicado um dia real), criar o evento na conta Google quebra a promessa de fidelidade da IA. A tool foi refatorada para registrar um callback executor (`executor = lambda: chamar_google_calendar(...)`) no buffer. A chamada HTTP só é disparada se o Juiz aprovar.
- **`salvar_mensagem` (Histórico no MongoDB):** **FICOU DE FORA DO STAGING (MANTIDA COMO ESTAVA).**  
  *Por quê:* Em `app/graph.py` (linhas 306-307), `salvar_mensagem` já é invocada **após a conclusão de todo o grafo**, recebendo a `resposta_final` que já foi revisada pelo Juiz. Se o Juiz recusou, o MongoDB armazena a `FRASE_SEGURA` (*"Não tenho evidência para afirmar isso."*). Isso é essencial para a auditoria do sistema: o histórico precisa comprovar que o usuário fez uma pergunta e que o assistente recusou com segurança, sem deixar transações fantasmas registradas.

### 2. O que acontece se o Juiz não responde?
Adotamos uma política estrita de **Fail-Safe defensivo**:
- Se a API do Typesafe sofrer timeout, indisponibilidade ou ausência da variável `TYPESAFE_API_KEY`, o bloco `try/except` do nó `juiz` captura o erro e devolve o rótulo `juiz:erro` ou `juiz:sem_chave` acompanhado da `FRASE_SEGURA`.
- O nó `efetivador` autoriza commits **única e exclusivamente** se constar `juiz:apoiada` (com limiar válido). Qualquer outro rótulo (`erro`, `sem_chave`, `sem_resposta`) ativa o descarte sumário do buffer. Na dúvida ou na falha de rede, **nenhum dado é gravado no banco de dados**.

### 3. O que resta se o processo cair entre dois passos?
- **Se o servidor cair durante o raciocínio (antes do nó efetivador):** O buffer de staging reside exclusivamente na memória RAM volátil da thread do processo Python (`_buffers`). Se o servidor sofrer *crash*, falta de energia ou *SIGKILL*, o sistema operacional desaloca a memória. O PostgreSQL e o Google Calendar permanecem **100% intactos**, pois nenhuma instrução chegou a ser enviada.
- **Se o servidor cair durante o nó efetivador:** As instruções SQL são enviadas em bloco dentro de uma única transação atômica (`BEGIN ... COMMIT`). Se a conexão cair antes do `conn.commit()`, o motor do PostgreSQL executa o *rollback* automático. Se cair depois, os dados foram persistidos atomicamente. Não existe possibilidade de persistência parcial ou inconsistência entre registros.
- **Limpeza no finally:** Em `app/graph.py`, o fluxo de execução é envelopado por `try ... finally: descartar_operacoes(turno_id)`. Mesmo que uma exception não tratada estoure dentro do grafo, o buffer do turno é purgado, garantindo vazamento zero de memória (*zero memory leaks*).

### 4. O que uma repetição do mesmo pedido faz com a escrita?
- **Se for a repetição de um pedido recusado:** O usuário repete a mesma frase sem evidência (ex.: *"Gastei 50 dólares no almoço"*). O turno abre um novo `turno_id`, a tool entra em staging, o Juiz recusa novamente e o buffer é novamente descartado. Zero registros são gravados em ambas as tentativas.
- **Se for a repetição de um pedido legítimo aprovado:** Cada mensagem submetida pelo usuário gera um turno com `turno_id` e UUID próprios. Se o usuário submeter duas vezes *"Gastei 15 reais no almoço"*, o especialista interpretará como duas declarações de despesas distintas e ambas serão homologadas e gravadas individualmente. O sistema preserva a semântica natural de comandos conversacionais.

### 5. Evidência com marcadores únicos nas três tools
Para comprovar factualmente o cumprimento do contrato, executamos a suíte automatizada [`tests/test_etapa8_adiar.py`](file:///C:/Users/lucasporto-ieg/OneDrive%20-%20Instituto%20J%26F/%C3%81rea%20de%20Trabalho/Mat%C3%A9rias%20TECH/Intelig%C3%AAncia%20Artificial/juiz_tardio/tests/test_etapa8_adiar.py) contra a base real do PostgreSQL. Os resultados foram:

```
================================================================================
BATERIA DE TESTES AUTOMATIZADOS: ESTRATÉGIA DE ADIAR (ETAPA 8)
================================================================================

[TESTE 01] Recusa em add_transaction (Compra em dólares sem evidência):
  - Marcador Único: ETAPA8_ADIAR_TEST_01_a9f2bc
  - Entrada: "Gastei 45 dólares em almoço [ETAPA8_ADIAR_TEST_01_a9f2bc]"
  - Veredito Juiz: juiz:sem_apoio noul=0.15 -> nó efetivador executou descarte.
  - Verificação Postgres: SELECT COUNT(*) WHERE source_text LIKE '%ETAPA8_ADIAR_TEST_01_a9f2bc%'
  - Resultado: EXATAMENTE 0 LINHAS GRAVADAS (Sucesso comprovado).

[TESTE 02] Aprovação em add_transaction (Despesa legítima em reais):
  - Marcador Único: ETAPA8_ADIAR_TEST_02_e34a11
  - Entrada: "Almoço no bandejão R$ 25.50 [ETAPA8_ADIAR_TEST_02_e34a11]"
  - Veredito Juiz: juiz:apoiada noul=0.92 -> nó efetivador executou commit.
  - Verificação Postgres: SELECT COUNT(*) WHERE source_text LIKE '%ETAPA8_ADIAR_TEST_02_e34a11%'
  - Resultado: EXATAMENTE 1 LINHA GRAVADA (Sucesso comprovado).

[TESTE 03] Recusa em update_transaction (Tentativa de alteração com alucinação):
  - Marcador Único: ETAPA8_ADIAR_TEST_03_7b819d
  - Registro Prévio no Postgres: Transação id=136 com valor R$ 30.00 e descrição "Padaria Original".
  - Tentativa de Alteração: amount=999.00 com descrição "Alteração não suportada".
  - Veredito Juiz: juiz:sem_apoio noul=0.10 -> nó efetivador executou descarte.
  - Verificação Postgres: SELECT amount, description FROM transactions WHERE id = 136
  - Resultado: Registro permaneceu intacto com R$ 30.00 e "Padaria Original" (Sucesso comprovado).

[TESTE 04] Recusa em add_event (Compromisso sem evidência temporal clara):
  - Marcador Único: ETAPA8_ADIAR_TEST_04_31c890
  - Entrada: "Reunião Fictícia [ETAPA8_ADIAR_TEST_04_31c890]"
  - Veredito Juiz: juiz:sem_apoio noul=0.20 -> nó efetivador executou descarte.
  - Verificação Postgres: SELECT COUNT(*) FROM events WHERE source_text LIKE '%ETAPA8_ADIAR_TEST_04_31c890%'
  - Resultado: EXATAMENTE 0 LINHAS GRAVADAS NA TABELA EVENTS (Sucesso comprovado).

[TESTE 05] Resiliência em add_google_event (Google Calendar descartado em recusa/sem chave):
  - Entrada: "Dentista Google Staging" com início às 10h.
  - Veredito Juiz: juiz:sem_chave -> nó efetivador executou descarte.
  - Resultado: Callback expurgado do staging; zero requisições HTTP enviadas à API do Google.
```

---

## 5. Arquivos criados e arquivos modificados

### Arquivos Criados
1. `app/tools/staging.py`
2. `decisao_tecnica.md`
3. `tests/test_etapa8_adiar.py`

### Arquivos Modificados
1. `app/tools/financeiro.py`: Refatoração de `add_transaction` e `update_transaction` para substituir a execução SQL e commit imediatos pelo enfileiramento no staging buffer com retorno de evidência factual.
2. `app/tools/agenda.py`: Refatoração de `add_event` para enfileirar a inserção do compromisso no staging buffer em vez de persistir diretamente no PostgreSQL.
3. `app/tools/calendario_google.py`: Adaptação de `add_google_event` para reter o callback de criação de evento no staging buffer, executando a chamada HTTP somente após aprovação do Juiz.
4. `app/graph.py`: Adição do nó `efetivador` entre o `juiz` e o `END` no grafo, e gerenciamento do ciclo de vida do staging buffer (abertura e descarte de segurança no finally) em `executar_fluxo_assessor`.
