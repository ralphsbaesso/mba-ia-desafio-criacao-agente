# Spec 07: API HTTP

## Objetivo
Expor o contrato exato do enunciado em `http://localhost:8000` com FastAPI (`aurora/api/app.py`).

## Infra
- `lifespan`: `config.garantir_diretorios()`, `db.inicializar()` (cria tabelas; carrega o seed apenas se o marcador `meta.seed` não existir), cria `SqliteSessionService(config.db_sessoes())`, `criar_app()` e `Runner`. Guarda tudo em `app.state`.
- Um `asyncio.Lock` por `session_id` serializa mensagens e confirmações da mesma sessão. O lock envolve: recarregar a sessão, calcular pendências, decidir `409`, executar o runner e montar a resposta. Sessões diferentes rodam em paralelo (passo 14). Entrada `(lock, contador)` por sessão: incrementa antes de esperar o lock, decrementa no `finally`, remove só quando chega a zero (evita a corrida entre `release` e a retomada de quem esperava).
- `aurora/api/execucao.py`: `executar(runner, session_service, apartamento, session_id, new_message) -> RespostaMensagem`. Itera `runner.run_async(user_id=apartamento, session_id, new_message)`; a `resposta` é o texto do **último** evento final (`event.is_final_response()`) que tenha `parts` com `text` e sem `thought`; se não houver, `""`. Depois recarrega a sessão e calcula `confirmacoes_pendentes`.
- Erros do modelo (quota, rede), nas duas rotas de conversa: a rota recarrega a sessão; se nesta invocação alguma tool de escrita gravou (há `function_response` nova de `reservar_area`, `cancelar_reserva` ou `autorizar_visitante` após a mensagem do usuário, excluindo o placeholder `aguardando_confirmacao`, mesmo critério da spec 06), responde `200` com `resposta` montada do resultado da tool; senão `502 {"detail": "Falha ao consultar o modelo. Tente novamente em instantes."}` sem repassar o erro bruto. O cliente Gemini é configurado com retry (`HttpRetryOptions`, 3 tentativas com backoff) via `generate_content_config`/`http_options` do modelo.
- `resposta` vazia com pendência criada nesta invocação: a API preenche `"Seu pedido aguarda confirmação pelo aplicativo."` (o contrato permite vazio; o texto só melhora a leitura).
- `texto` limitado a 4000 caracteres (`422` acima disso).

## Rotas
| Rota | Corpo | Resposta |
|---|---|---|
| `POST /sessoes` | `{"apartamento": "101"}` | `201 {"session_id"}`; `422` se apartamento não existe em `dados/apartamentos.json` |
| `POST /sessoes/{id}/mensagens` | `{"texto"}` | `200 {"resposta", "confirmacoes_pendentes": [{"id","acao","detalhes"}]}` |
| `POST /sessoes/{id}/confirmacoes` | `{"id", "confirmado"}` | `200` idem; `409` (spec 06) |
| `GET /sessoes/{id}/eventos` | – | `200 [event.model_dump(mode="json", exclude_none=True)]` na ordem gravada |
| `GET /apartamentos/{n}/reservas` | – | `200 [{"codigo","area","data"}]` direto do banco |
| `GET /apartamentos/{n}/visitantes` | – | `200 [{"nome","data"}]` direto do banco |
- Toda rota com `{id}` responde `404 {"detail": "Sessão não encontrada."}` quando a sessão não existe na tabela `sessoes` ou no serviço do ADK.
- `POST /sessoes`: cria primeiro no ADK (`create_session(state={"apartamento"})`), depois `registrar_sessao`; só então devolve o id.
- Rotas de verificação não passam pelo modelo. Apartamento inexistente devolve lista vazia.
- Mensagem nova com confirmação pendente: aceita normalmente; a pendência continua na lista e nada executa sem a rota de confirmações. O teste de integração (spec 11) cobre esse caso.

## Modelos Pydantic (`aurora/api/schemas.py`)
`CriarSessao`, `SessaoCriada`, `Mensagem`, `RespostaConfirmacao` (entrada da rota de confirmações), `Pendencia`, `RespostaMensagem` (saída das duas rotas).

## Critérios de aceite
- Testes com `TestClient` e runner substituído por um dublê: todos os códigos de status da tabela.
- Teste: 20 requisições simultâneas na mesma sessão com runner dublê lento têm concorrência máxima 1.
- Passo 1 do avaliador: `GET /apartamentos/101/reservas` lista `RSV-1377`.
