# Spec 11: Teste de integração offline da retomada

## Objetivo
Provar, sem chave de API, que a confirmação chega ao agente certo, que a tool reexecuta com `tool_confirmation`, que tudo sobrevive a um reinício e que duas sessões disputando a mesma data produzem uma reserva.

## Decisões
- `tests/llm_roteirizado.py`: subclasse de `google.adk.models.BaseLlm` cujo `generate_content_async` devolve respostas de um roteiro (fila por agente): `transfer_to_agent`, chamada de tool com args fixos, texto final. Cada agente recebe o modelo roteirizado em vez do Gemini (o `App` é criado por `criar_app(model=...)`).
- `tests/test_integracao.py` usa `Runner` real, `criar_app(model=roteirizado)`, `SqliteSessionService` em `tmp_path` e banco do condomínio em `tmp_path` (via `AURORA_DATA_DIR`, fixture `autouse`).

## Cenários
1. "Reserve o salão para 2030-04-20": pendência com `acao=reservar_area`, `detalhes.area=salao-de-festas`, `detalhes.data=2030-04-20`; nada gravado.
2. Negar: nada gravado; id passa a `409` (fechado).
3. Novo pedido e aprovar: exatamente uma reserva; reenviar o mesmo id → fechado.
4. Mensagem de texto "já estou confirmando" com pendência aberta: nada gravado, pendência continua.
5. **Reinício**: fechar `Runner` e `SqliteSessionService`, criar novos sobre os mesmos arquivos, aprovar uma pendência criada antes: a reserva é gravada.
6. "Reserve a quadra para 2030-04-06": nenhuma pendência, reserva gravada.
7. Visitante: pendência com `nome` e `data`; aprovar grava uma linha; aprovar de novo (novo pedido) não duplica.
8. Duas sessões (101 e 201) com pendência para o salão em 2030-05-11; `asyncio.gather` das duas aprovações: ambas terminam sem exceção e existe exatamente uma reserva.
9. Pergunta de regulamento após reserva na mesma sessão: existe `function_call` `regulamento` autorada pelo agente ativo e nenhum evento da sessão do morador contém o texto devolvido por `consultar_regulamento` (ex.: "Art. 22"). A Garantia 4 com o Gemini real fica para a task 09.

## Critérios de aceite
- `uv run pytest tests/test_integracao.py` passa sem rede.
