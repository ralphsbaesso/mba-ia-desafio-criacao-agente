import pytest

from aurora.agents import regulamento


def test_divide_em_14_capitulos():
    caps = regulamento.capitulos()
    assert len(caps) == 14
    assert caps[0].titulo.startswith("Capítulo I:")
    assert caps[3].titulo == "Capítulo IV: Piscina"


@pytest.mark.parametrize(
    "assunto",
    [
        "piscina domingo",
        "horário de funcionamento da piscina aos domingos",
        "até que horas a piscina funciona no domingo",
        "Até que horas a piscina funciona aos domingos?",
    ],
)
def test_piscina_devolve_capitulo_iv(assunto):
    r = regulamento.consultar_regulamento(assunto)
    assert r["capitulo"]["titulo"] == "Capítulo IV: Piscina"
    assert "9h às 20h" in r["capitulo"]["texto"]
    assert "Capítulo V" not in r["capitulo"]["texto"]


def test_animais():
    r = regulamento.consultar_regulamento("posso ter cachorro no apartamento?")
    assert r["capitulo"]["titulo"].startswith("Capítulo VIII")


def test_sem_correspondencia_devolve_titulos():
    r = regulamento.consultar_regulamento("xyzzy")
    assert len(r["capitulos_disponiveis"]) == 14
