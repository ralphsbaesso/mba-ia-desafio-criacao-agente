import re

from aurora import config

PATH = r"(?:aurora|tests|dados|scripts)/[\w/.-]+\.(?:py|md|json|sh)"


def _secao_garantias() -> str:
    texto = (config.RAIZ / "README.md").read_text(encoding="utf-8")
    return texto.split("## Garantias", 1)[1].split("## Como rodar", 1)[0]


def test_caminhos_citados_no_readme_existem():
    caminhos = set(re.findall(rf"`({PATH})`", _secao_garantias()))
    assert len(caminhos) >= 8
    for caminho in caminhos:
        assert (config.RAIZ / caminho).exists(), caminho


def test_trechos_citados_existem_nos_arquivos():
    """Cada função/classe/rota/teste citada numa linha existe em um dos arquivos citados na mesma linha."""
    conferidos = 0
    for linha in _secao_garantias().splitlines():
        arquivos = [a for a in re.findall(rf"`({PATH})`", linha) if a.endswith(".py")]
        nomes = re.findall(r"(?:funç(?:ão|ões)|classe|rota|teste)s? `(\w+)`", linha)
        if not arquivos or not nomes:
            continue
        conteudos = [(config.RAIZ / a).read_text(encoding="utf-8") for a in arquivos]
        for nome in nomes:
            padrao = re.compile(rf"^\s*(?:async def|def|class) {re.escape(nome)}\b", re.M)
            assert any(padrao.search(c) for c in conteudos), (nome, arquivos)
            conferidos += 1
    assert conferidos >= 10


