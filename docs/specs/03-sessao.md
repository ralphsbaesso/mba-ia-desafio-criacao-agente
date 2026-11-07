# Spec 03: Sessão amarrada ao apartamento

## Objetivo
Cada sessão pertence a um apartamento definido uma única vez na criação e persistido fora do prompt (Garantias 2 e 3).

## Decisões
- Serviço de sessão do ADK: `SqliteSessionService(db_path=str(config.db_sessoes()))` (`google.adk.sessions.sqlite_session_service`). Persiste eventos e state entre reinícios.
- `app_name = "aurora"`; `user_id = apartamento`; `session_id` gerado por `uuid4`.
- Na criação: `create_session(app_name, user_id=apartamento, session_id=..., state={"apartamento": apartamento})`. O state é a fonte de verdade que as tools leem (`tool_context.state["apartamento"]`).
- A tabela `sessoes` do banco do condomínio (spec 02) guarda `session_id -> apartamento`, porque o `get_session` do ADK exige `user_id`. A API resolve o apartamento por essa tabela e só então busca a sessão no ADK.
- Sessão inexistente em qualquer uma das duas fontes: `404`.
- Apartamento ausente em `dados/apartamentos.json`: `POST /sessoes` responde `422` com mensagem (comportamento livre pelo enunciado; escolhemos recusar).

## Garantia no código
- Nenhuma tool declara parâmetro `apartamento`. O valor vem de `tool_context.state`, gravado pela API na criação da sessão; o modelo não tem como alterá-lo (state só muda por `state_delta` das tools, e nenhuma tool escreve nessa chave).

## Critérios de aceite
- Criar sessão, reiniciar o processo, `GET /sessoes/{id}/eventos` devolve os mesmos eventos.
- Teste unitário: tool chamada com state de `101` nunca retorna dados de `302`.
