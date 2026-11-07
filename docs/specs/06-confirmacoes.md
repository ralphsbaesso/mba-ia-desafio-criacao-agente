# Spec 06: Confirmações pendentes e retomada

## Objetivo
Cobrança e acesso só executam depois que o sistema recebe a aprovação pela rota de confirmações (Garantia 1), com `409` para id desconhecido ou já respondido.

## Como o ADK representa a pendência
- Quando uma tool chama `request_confirmation`, o ADK grava um evento do agente com uma `function_call` de nome `adk_request_confirmation`, `id` novo, `args={"originalFunctionCall": {...}, "toolConfirmation": {hint, confirmed, payload}}`; o `id` entra em `event.long_running_tool_ids` e o turno termina (`flows/llm_flows/tools/_functions.py::generate_request_confirmation_event`).
- A resposta do cliente é uma `Content(role="user")` com `FunctionResponse(id=<id do pedido>, name="adk_request_confirmation", response={"confirmed": bool})`, enviada como `new_message` ao `Runner.run_async`. O processador `request_confirmation` (`flows/llm_flows/tools/_confirmation.py`) reexecuta a tool original com `tool_context.tool_confirmation` preenchido e grava a `function_response` da tool original.

## Pendências derivadas dos eventos (`aurora/confirmacoes.py`)
Módulo neutro (fora de `api/` e de `agents/`) porque é usado pela API e pelas tools, sem importação circular.
- `pendentes(events) -> list[Pendencia]`: percorre os eventos em ordem; coleta toda `function_call` `adk_request_confirmation` (`id`, `originalFunctionCall.id`, payload). Uma pendência está **fechada** quando existe, depois do pedido, uma `function_response` de autor `user` com o `id` do pedido **e**, depois dela, uma `function_response` com o `id` da chamada original (a tool rodou, confirmada ou rejeitada). Caso contrário continua pendente.
- `Pendencia -> {"id": fc.id, "acao": payload["acao"] (fallback: originalFunctionCall.name), "detalhes": payload sem "acao" (fallback: args da chamada original)}`. `detalhes.area` é sempre o `id` da área e `detalhes.data` está em AAAA-MM-DD (spec 04).
- Derivado da sessão persistida: sobrevive a reinício e não há estado em memória. O mesmo módulo é usado pelas tools para evitar pendência duplicada (spec 04).

## Rota `POST /sessoes/{id}/confirmacoes`
Tudo dentro do lock da sessão (spec 07):
1. Resolve a sessão (404 se não existe) e recarrega os eventos.
2. Calcula `pendentes`. Se `id` não está na lista → `409 {"detail": "Não existe confirmação pendente com esse id nesta sessão."}`. Nada roda.
3. Monta a `FunctionResponse` e executa o runner (`execucao.executar`).
4. Responde `200` no mesmo formato da rota de mensagens, com as pendências recalculadas.
- Reenvio do mesmo `id` após execução: há resposta do `user` e resposta da tool original → fechada → `409`. O ADK também descarta confirmações já consumidas, como segunda defesa.
- Falha do modelo **depois** de a tool original ter rodado (ex.: quota): a rota recarrega a sessão; se existe `function_response` da tool original **posterior** à resposta do `user` com esse id (mesmo critério de `pendentes`; o placeholder emitido junto com o pedido não conta), responde `200` com `resposta` montada do resultado da tool (ex.: "Reserva RSV-… confirmada." ou o `motivo`) e as pendências recalculadas. Se a falha veio antes da tool, `502` e a pendência continua aberta. A mesma regra vale para a rota de mensagens (spec 07).
- Reenvio simultâneo do mesmo id: serializado pelo lock por sessão; o segundo recebe `409`.

## Critérios de aceite
- Teste unitário de `pendentes` com eventos sintéticos (pedido sem resposta; pedido respondido sem execução da tool; pedido respondido e executado; dois pedidos).
- Teste da rota com runner dublê: falha do modelo antes da tool → `502` e pendência aberta; depois da tool → `200` com o resultado.
- Teste de integração (spec 11) cobre a retomada real com `Runner` e `SqliteSessionService`.
