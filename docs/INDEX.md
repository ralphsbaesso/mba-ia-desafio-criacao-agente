# Documentação do assistente do Residencial Aurora

## Enunciado
- [challenge.md](challenge.md): o desafio completo, contrato da API, fluxo do avaliador e critérios de aceite.

## Especificações (`docs/specs/`)
1. [Projeto e stack](specs/01-projeto-e-stack.md)
2. [Armazenamento](specs/02-armazenamento.md)
3. [Sessão amarrada ao apartamento](specs/03-sessao.md)
4. [Tools de reservas e visitantes](specs/04-tools.md)
5. [Agentes](specs/05-agentes.md)
6. [Confirmações pendentes e retomada](specs/06-confirmacoes.md)
7. [API HTTP](specs/07-api.md)
8. [Consulta ao regulamento](specs/08-regulamento.md)
9. [Concorrência na gravação de reservas](specs/09-concorrencia.md)
10. [Comandos, testes e README](specs/10-comandos-e-readme.md)
11. [Teste de integração offline](specs/11-teste-integracao.md)

## Tasks
- Pendentes: `docs/tasks/` (a task 09, validação com chave real, depende de uma `GOOGLE_API_KEY`)
- Concluídas: `docs/tasks/done/`

## Validação
- `uv run pytest`: testes unitários, de integração (Runner real + modelo roteirizado) e de contrato da API.
- `scripts/fluxo_avaliador.sh`: reproduz os 14 passos do avaliador contra uma API em execução.

## Pontos em aberto
- [duvidas.md](duvidas.md): dúvidas e decisões tomadas sem confirmação durante a execução.
