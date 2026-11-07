# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este repositório

Desafio do MBA (Full Cycle): assistente virtual do "Residencial Aurora", construído com Google ADK e exposto por uma API Python em `http://localhost:8000`. O enunciado completo, o contrato da API, o fluxo do avaliador e os critérios de aceite estão em `docs/challenge.md`. Leia-o antes de qualquer implementação: a correção é feita exatamente pelo contrato descrito ali.

Ainda não há código. A entrega (agentes, tools, sessão, API, persistência) deve ser criada do zero.

## Stack obrigatória

- Python >= 3.12, gerenciado por `uv` (`pyproject.toml` e `uv.lock` versionados).
- Google ADK série 2, versão >= 2.2.0, com a versão exata fixada (pin) no projeto.
- Modelos Gemini via chave do Google AI Studio. `.env` fica fora do git; `.env.example` versionado só com nomes das variáveis.
- Framework web e armazenamento livres (o curso usa FastAPI; SQLite para sessão persistida é conhecido por funcionar com confirmação de tools).

Comandos esperados pelo avaliador (defina-os e documente no README quando existirem): `uv sync`, um comando para subir a API e um comando para restaurar os dados iniciais.

## Restrições invioláveis

- `dados/*.json` e `dados/regulamento.md` são o estado inicial e **não podem ser alterados**. Mudanças feitas pelo assistente vão para outro armazenamento; o comando de restauração volta reservas e visitantes ao conteúdo desses arquivos.
- As cinco garantias (confirmação de cobrança/acesso, sessão amarrada ao apartamento, persistência após reinício, regulamento consultado sob demanda, exclusividade de reserva no instante da gravação) devem estar **no código**, nunca só no prompt. Nenhuma tool pode aceitar um apartamento escolhido pelo modelo sem validar contra o da sessão. O agente principal não recebe o regulamento nas instruções.
- Rota de confirmações: `id` desconhecido ou já respondido devolve `409` e nada executa.

## Fluxo de trabalho do projeto

- Especificações ficam em `docs/`, quebradas em arquivos pequenos por etapa/assunto. `docs/INDEX.md` é o índice da documentação.
- Cada spec gera ao menos uma task em `docs/tasks/`; task concluída vai para `docs/tasks/done/`.
- Ciclo por task: implementar → validar com a skill `qa-panel` → corrigir até passar → mover para `done` → commit.
- Dúvidas ou pontos em aberto são anotados em um arquivo novo em `docs/` em vez de interromper o trabalho.
- Commits **sem** linha de co-autor.
- Ao final, o `README.md` deve ter as seções Arquitetura, Garantias (apontando arquivo e trecho de cada uma) e Como rodar, mais uma nota de que é um desafio de curso com link para `docs/INDEX.md`.
