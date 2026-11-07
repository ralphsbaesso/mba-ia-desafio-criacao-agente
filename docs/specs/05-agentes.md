# Spec 05: Agentes

## Objetivo
Um agente principal que conduz a conversa e distribui o trabalho entre três especialistas, com a topologia que permite retomar confirmações pendentes.

## Topologia (`aurora/agents/`)
- `principal` (`LlmAgent`, raiz): recebe o morador, responde saudações e dúvidas simples, e delega. Não tem tools de dados. `sub_agents=[reservas, visitantes]`, `tools=[AgentTool(regulamento)]`.
- `reservas` (`LlmAgent`, sub-agente via transferência): tools `listar_minhas_reservas`, `verificar_disponibilidade`, `reservar_area`, `cancelar_reserva` e também `AgentTool(regulamento)`. `disallow_transfer_to_peers=True`.
- `visitantes` (`LlmAgent`, sub-agente via transferência): tools `listar_meus_visitantes`, `autorizar_visitante` e `AgentTool(regulamento)`. `disallow_transfer_to_peers=True`.
- `regulamento` (`LlmAgent`, acionado como `AgentTool`): tool `consultar_regulamento(assunto)` (spec 08). Roda em sessão isolada em memória: o texto do capítulo fica na sessão interna e só a resposta final entra na sessão do morador (Garantia 4). A instância do `AgentTool` é compartilhada pelos três agentes.
- **Fábrica**: `aurora/agents/fabrica.py::criar_agentes(model: str | BaseLlm) -> LlmAgent` constrói a árvore inteira (principal, reservas, visitantes, regulamento e o `AgentTool`) a cada chamada, porque o ADK não permite reutilizar um sub-agente que já tem pai (`base_agent.py`). `aurora/agents/__init__.py` fica vazio (nenhuma árvore é montada na importação; submódulos não importam `aurora.agents`); `aurora/agents/app.py::criar_app(model=None) -> App` chama a fábrica com `model or config.modelo()`. A API e os testes de integração usam `criar_app`.

## Por que assim
- Reservas e visitantes pedem confirmação. O ADK retoma uma confirmação entregando a resposta ao **autor** do pedido (`agents/_agent_router.py::find_agent_to_run`, rota `ROUTE_TO_AUTHOR`). Com sub-agentes por transferência o autor é o próprio especialista; `AgentTool` descarta a sessão interna e não consegue retomar (`tools/agent_tool.py`: "AgentTool cannot resume").
- Regulamento não grava nada, então `AgentTool` serve e ainda isola o texto longo.
- O roteador entrega a próxima mensagem ao último agente que respondeu ("pegajoso"). Por isso os especialistas também têm o `AgentTool(regulamento)`: uma dúvida de regra logo após uma reserva é respondida corretamente sem depender de o modelo transferir de volta. A Garantia 4 continua: nenhum agente tem o regulamento nas instruções.
- `App` sem `ResumabilityConfig` (modo padrão): a retomada acontece pela resposta `adk_request_confirmation` enviada como `new_message`, como faz o `adk run` (`cli/cli.py`).

## Instruções (resumo do conteúdo)
- `principal`: identidade (assistente do Residencial Aurora), responder em português, delegar reservas/cancelamentos/disponibilidade para `reservas`, visitantes para `visitantes`, dúvidas de regras para a tool `regulamento`. Nunca inventar dados; só o que as tools devolvem. Só atende o apartamento da sessão; se o morador disser ser de outro apartamento, explicar que a sessão está vinculada ao apartamento autenticado, sem citar dados de outros. **Não contém o regulamento.**
- `reservas`: usar as tools; nunca inventar código; se, em uma mensagem seguinte, a tool indicar `aguardando_confirmacao` com `repetida`, explicar que já existe um pedido aguardando confirmação e **não** chamar a tool de novo; data ocupada → informar apenas que está ocupada; qualquer assunto fora de reservas (exceto regulamento, que tem tool própria) → `transfer_to_agent` para `principal`.
- `visitantes`: idem, para autorizações.
- `regulamento`: usar `consultar_regulamento`, responder de forma curta citando o artigo, sem reproduzir capítulos inteiros.
- Modelo de todos: `config.modelo()`.

## Critérios de aceite
- `uv run python -c "from aurora.agents.app import criar_app; criar_app()"` sem erro.
- Teste: `criar_app(model=falso)` duas vezes e `criar_app()` uma vez no mesmo processo, sem exceção; na árvore com modelo falso nenhum `LlmAgent` usa o modelo real.
- Instrução de nenhum agente contém linhas de `dados/regulamento.md` (teste automatizado).
