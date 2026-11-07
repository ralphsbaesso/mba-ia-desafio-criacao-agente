# Task 03: Tools de reservas e visitantes
Spec: `docs/specs/04-tools.md`, `docs/specs/03-sessao.md`
- [x] `aurora/agents/tools.py` com as 6 tools, apartamento de `tool_context.state`, data e área canônicas, skip_summarization e dedup de pendência
- [x] confirmação dinâmica em `reservar_area` (taxa>0 e data livre) e `autorizar_visitante`
- [x] testes unitários com ToolContext falso cobrindo todas as regras
