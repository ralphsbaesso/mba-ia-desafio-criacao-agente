# Assistente virtual do Residencial Aurora

## Detalhes do projeto

Assistente de chat para o aplicativo dos moradores do Residencial Aurora. Pelo chat, cada morador
reserva o salão de festas, a churrasqueira e a quadra, cancela as próprias reservas, autoriza a
entrada de visitantes e tira dúvidas sobre o regulamento interno. O modelo conduz a conversa, mas
as regras críticas do condomínio estão no código e continuam valendo não importa o que o morador escreva.

Stack:

- Python 3.12+, gerenciado por [uv](https://docs.astral.sh/uv/).
- [Google ADK](https://google.github.io/adk-docs/) `2.14.0` (versão exata fixada em `pyproject.toml`) com modelos Gemini via chave do Google AI Studio.
- FastAPI + Uvicorn para a API HTTP em `http://localhost:8000`.
- SQLite (biblioteca padrão) para reservas, visitantes e sessões; `SqliteSessionService` do ADK para o histórico das conversas.

## Arquitetura

```
morador ──HTTP──▶ FastAPI (aurora/api/app.py)
                     │  lock por sessão · pendências derivadas dos eventos
                     ▼
                  Runner do ADK ──▶ SqliteSessionService (var/sessoes.db)
                     │
                     ▼
              principal (LlmAgent raiz)
               ├─ transfer_to_agent ──▶ reservas   ──▶ tools ──▶ var/aurora.db
               ├─ transfer_to_agent ──▶ visitantes ──▶ tools ──▶ var/aurora.db
               └─ AgentTool ────────▶ regulamento ──▶ consultar_regulamento ──▶ dados/regulamento.md
                                      (reservas e visitantes também têm o AgentTool regulamento)
```

Os agentes são montados em `aurora/agents/fabrica.py` (função `criar_agentes`):

| Agente | Responsabilidade | Como é acionado | Por quê |
|---|---|---|---|
| `principal` | Recebe o morador, responde saudações e distribui o trabalho. Não tem tools de dados. | Raiz do `Runner`. | Mantém a conversa num único ponto de entrada e sem o regulamento nas instruções. |
| `reservas` | Lista, verifica disponibilidade, reserva e cancela áreas comuns. | Sub-agente por transferência (`transfer_to_agent`). | Reservar área com taxa pede confirmação. O ADK devolve a resposta da confirmação ao **autor** do pedido (`find_agent_to_run`), e um sub-agente por transferência continua na árvore para retomar. Um `AgentTool` descarta a sessão interna e não consegue retomar. |
| `visitantes` | Lista e autoriza visitantes. | Sub-agente por transferência. | Mesmo motivo: liberar acesso sempre pede confirmação. |
| `regulamento` | Responde dúvidas de regras consultando `dados/regulamento.md` por capítulo. | `AgentTool` disponível para o principal e para os dois especialistas. | Roda em sessão isolada em memória: o texto do capítulo fica fora dos eventos do morador. Está nos três agentes porque o roteador do ADK entrega a próxima mensagem ao último agente que respondeu. |

Toda leitura e gravação de reservas e visitantes passa pelas tools de `aurora/agents/tools.py`, que
chamam `aurora/storage/repositorio.py`. Os arquivos de `dados/` nunca são alterados: eles são o estado
inicial, carregado para `var/aurora.db` pelo comando de restauração.

## Garantias

Todas as cinco garantias estão no código. O modelo decide o caminho da conversa; o código decide o que é permitido.

### Garantia 1: cobrança ou acesso só com confirmação

- `aurora/agents/tools.py`, funções `reservar_area` e `autorizar_visitante`: quando a ação gera cobrança (`taxa > 0`) ou libera acesso, a tool chama `tool_context.request_confirmation(...)` (função `_pedir_confirmacao`) e retorna sem gravar. A gravação só acontece no ramo em que `tool_context.tool_confirmation.confirmed` é verdadeiro, valor que o ADK preenche apenas ao reexecutar a tool com uma `FunctionResponse` de confirmação (`_RequestConfirmationLlmRequestProcessor` em `google/adk/flows/llm_flows/tools/_confirmation.py`). Área sem taxa não passa por esse ramo e grava direto.
- `aurora/api/app.py`, rota `responder_confirmacao`: só a rota monta essa `FunctionResponse` (`aurora/confirmacoes.py`, função `resposta_do_usuario`). Texto do morador entra sempre como texto puro, então "já estou confirmando aqui" não executa nada.
- `aurora/confirmacoes.py`, função `pendentes`: a lista de pendências é derivada dos eventos persistidos. Uma pendência fecha só quando existe a resposta do morador e, depois dela, a resposta da tool original. A rota responde `409` para qualquer `id` fora dessa lista, inclusive um já respondido, e nada executa.

### Garantia 2: cada sessão pertence a um apartamento

- `aurora/api/app.py`, rota `criar_sessao`: o apartamento é gravado uma única vez no `state` da sessão do ADK (`state={"apartamento": ...}`) e na tabela `sessoes` de `var/aurora.db`.
- `aurora/agents/tools.py`, função `_apartamento`: toda tool lê o apartamento de `tool_context.state`. Nenhuma tool declara um parâmetro `apartamento` (o teste `test_nenhuma_tool_aceita_apartamento` em `tests/test_tools.py` garante isso), então o modelo não tem como escolher outro.
- `aurora/storage/repositorio.py`: `listar_reservas`, `cancelar_reserva` e `listar_visitantes` filtram por apartamento no SQL; `situacao_data` e `data_disponivel` informam apenas se a data está livre, nunca de quem é a reserva.

### Garantia 3: nada se perde no reinício

- `aurora/api/app.py`, função `criar_infra`: o `Runner` usa `SqliteSessionService` em `var/sessoes.db`; eventos e `state` ficam em disco.
- `aurora/storage/db.py`: reservas, visitantes e o mapeamento de sessões ficam em `var/aurora.db`. O seed só é carregado quando o marcador `meta.seed` não existe (função `inicializar`), então subir a API de novo não recarrega os dados.
- As pendências não vivem em memória: `aurora/confirmacoes.py` as recalcula a partir dos eventos a cada requisição. O teste `test_reinicio_mantem_eventos_e_retoma_pendencia` em `tests/test_integracao.py` recria `Runner` e serviço de sessão sobre os mesmos arquivos e aprova uma pendência criada antes.

### Garantia 4: o regulamento é consultado, não carregado

- `aurora/agents/fabrica.py`: nenhuma instrução contém o regulamento (teste `test_nenhum_agente_recebe_o_regulamento` em `tests/test_agentes.py`).
- `aurora/agents/regulamento.py`, função `consultar_regulamento`: divide o arquivo em capítulos e devolve apenas o capítulo mais relacionado ao assunto.
- O agente `regulamento` é um `AgentTool` (`aurora/agents/fabrica.py`): o ADK o executa em uma sessão isolada em memória (`google/adk/tools/agent_tool.py`), então o capítulo consultado nunca entra nos eventos da sessão do morador, só a resposta final curta.

### Garantia 5: dois moradores, uma reserva

- `aurora/storage/db.py`: índice único parcial `reservas_area_data_ativa ON reservas(area, data) WHERE status = 'ativa'`. A exclusividade vale no instante do `INSERT`.
- `aurora/storage/repositorio.py`, função `criar_reserva`: dentro de `BEGIN IMMEDIATE` (que serializa os escritores do SQLite) faz um `SELECT` apenas para idempotência da própria unidade e em seguida o `INSERT`. O árbitro final é o índice único: um `IntegrityError` vira `Resultado(ok=False, motivo="ocupada")`, que a tool converte em resposta normal ao morador. Mesmo que dois processos checassem a data ao mesmo tempo, só um `INSERT` passa.
- `aurora/api/app.py`, classe `_LockDaSessao`: o lock é por sessão, então sessões diferentes aprovam em paralelo. Testes: `test_concorrencia_uma_unica_reserva` (10 threads) em `tests/test_repositorio.py` e `test_disputa_passo_14` em `tests/test_api.py`.

## Como rodar

Pré-requisitos: Python 3.12+ e `uv`.

```bash
cp .env.example .env     # preencha GOOGLE_API_KEY
uv sync                  # instala dependências (google-adk==2.14.0)
uv run aurora-restaurar  # restaura reservas e visitantes de dados/ e limpa as sessões (com a API parada)
uv run aurora-api        # sobe a API em http://localhost:8000
```

Variáveis do `.env` (`.env.example` traz só os nomes; vazio usa o padrão):

| Variável | Uso | Padrão |
|---|---|---|
| `GOOGLE_API_KEY` | Chave do Google AI Studio. Obrigatória. | – |
| `GOOGLE_GENAI_USE_VERTEXAI` | Mantido `FALSE` para usar a chave do AI Studio. | `FALSE` |
| `GEMINI_MODEL` | Modelo Gemini de todos os agentes. Troque se a sua quota for em outro modelo. | `gemini-3.5-flash` |
| `AURORA_DATA_DIR` | Pasta dos bancos SQLite (relativa à raiz do repositório). | `var` |
| `AURORA_HOST` / `AURORA_PORT` | Endereço da API. | `127.0.0.1` / `8000` |

Testes (sem chave de API; usam um modelo roteirizado com o `Runner` real do ADK):

```bash
uv run pytest
```

Roteiro do fluxo do avaliador contra uma API em execução: `scripts/fluxo_avaliador.sh`.

Observações de operação:

- Rode `aurora-restaurar` com a API parada.
- A API sobe com um único worker: o lock por sessão vive em memória. A exclusividade de reserva não depende disso, pois está no índice do banco.
- Se o modelo falhar (quota, rede) antes de qualquer ação, a rota responde `502` e a mensagem pode ser reenviada; se falhar depois de uma tool gravar, a rota responde `200` com o resultado da ação.

---

Este repositório é a entrega de um desafio do curso MBA em Engenharia de Software com IA (Full Cycle).
O enunciado, as especificações, as tasks e os pontos em aberto estão em [docs/INDEX.md](docs/INDEX.md).
