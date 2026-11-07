# Spec 08: Consulta ao regulamento

## Objetivo
Responder dúvidas com base em `dados/regulamento.md` sem carregar o texto na sessão do morador (Garantia 4).

## Decisões
- `aurora/agents/regulamento.py`: na importação, lê o arquivo e divide em capítulos pelas linhas `## Capítulo ...`. Cada capítulo tem `titulo` e `texto`.
- Tool `consultar_regulamento(assunto: str)`:
  - normaliza o assunto e os capítulos (minúsculas, sem acentos);
  - remove stopwords (lista curta em português: "de", "da", "que", "aos", "até", "horas", "pode", "posso", "qual", "quais", "como", "funciona" etc.) e palavras com menos de 3 letras;
  - casa por **prefixo** (os 5 primeiros caracteres da palavra, ou a palavra inteira se menor): "domingo" casa "domingos", "piscina" casa "piscinas";
  - pontua cada capítulo por ocorrências, com peso 3 quando a palavra aparece no título;
  - devolve `{"capitulo": {"titulo", "texto"}}` só do capítulo de maior pontuação. Se a pontuação for zero, devolve `{"capitulos_disponiveis": [titulos]}` para o agente pedir mais detalhes.
- A tool pertence apenas ao agente `regulamento`, acionado como `AgentTool` (spec 05). O capítulo entra só na sessão interna do `AgentTool`; na sessão do morador fica a chamada `regulamento(request=...)` e a resposta textual curta.
- Nenhum agente recebe o regulamento nas instruções.

## Critérios de aceite
- `consultar_regulamento("piscina domingo")`, `("horário de funcionamento da piscina aos domingos")` e `("até que horas a piscina funciona no domingo")` devolvem o Capítulo IV, cujo texto contém "9h às 20h".
- `consultar_regulamento("cachorro")` devolve o Capítulo VIII (animais) ou a lista de títulos, nunca outro capítulo.
