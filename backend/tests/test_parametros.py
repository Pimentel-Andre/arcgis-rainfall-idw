"""O estudo que escolhe os parâmetros tem que ser coerente com o que o projeto usa."""

import json

from app import config
from app.schemas.interpolation import IdwParams

estudo = json.loads(config.PARAMETERS_JSON.read_text(encoding="utf-8"))
escolha = estudo["chosen"]


def test_escolha_e_o_menor_rmse_da_tabela():
    melhor = min(estudo["table"], key=lambda linha: linha["rmse"])
    assert (escolha["power"], escolha["neighbors"]) == (melhor["power"], melhor["neighbors"])
    assert escolha["rmse"] == melhor["rmse"]


def test_tabela_cobre_a_grade_inteira():
    grade = estudo["grid"]
    assert len(estudo["table"]) == len(grade["power"]) * len(grade["neighbors"])


def test_idw_bate_a_media_simples():
    assert escolha["rmse"] < estudo["baseline"]["rmse"]
    assert escolha["rmse"] <= estudo["classic"]["rmse"]


def test_celula_respeita_a_regra_de_hengl():
    # Hengl (2006): no máximo metade da distância média ao vizinho mais próximo.
    resolucao = estudo["resolution"]
    assert escolha["cell_size"] <= resolucao["mean_nearest_neighbor_m"] / 2


def test_api_e_scripts_usam_a_escolha():
    assert config.DEFAULT_PARAMS == {
        "power": escolha["power"],
        "cell_size": escolha["cell_size"],
        "neighbors": escolha["neighbors"],
    }
    padrao = IdwParams()
    assert (padrao.power, padrao.cell_size, padrao.neighbors) == (
        escolha["power"], escolha["cell_size"], escolha["neighbors"],
    )
