import pytest

from app.services.stations import (
    DateNotAvailable, available_dates, dataset_info, load_stations,
    stations_for_date, write_event_csv,
)

CABECALHO = "station_id,longitude,latitude,precip_mm\n"


def test_arquivo_cobre_janeiro_a_agosto():
    dias = available_dates()
    assert len(dias) == 243
    assert dias[0]["date"] == "2026-01-01"
    assert dias[-1]["date"] == "2026-08-31"


def test_dia_mais_chuvoso_do_arquivo():
    dias = available_dates()
    mais_chuvoso = max(dias, key=lambda d: d["mean"])
    assert mais_chuvoso == {"date": "2026-01-20", "station_count": 143, "mean": 47.5, "max": 182.8}


def test_dia_vira_csv_de_evento_valido(tmp_path):
    linhas = stations_for_date("2026-01-20")
    caminho = write_event_csv(linhas, tmp_path / "estacoes.csv")
    estacoes = load_stations(caminho)
    info = dataset_info(estacoes)
    assert len(estacoes) == 143
    assert info["date"] == "2026-01-20"
    assert info["source"] == "CEMADEN"
    assert info["observed_max"] == 182.8


def test_dia_fora_do_arquivo():
    with pytest.raises(DateNotAvailable, match="2026-01-01 a 2026-08-31"):
        stations_for_date("2026-09-15")


@pytest.mark.parametrize(
    "conteudo, mensagem",
    [
        ("station_id,longitude,latitude\nA,-43,-22\n", "colunas obrigatórias"),
        (CABECALHO + "A,-43,-22,abc\n", "números"),
        (CABECALHO + "A,-43,-22,\n", "números"),
        (CABECALHO + "A,-43,-22,nan\n", "ausente"),
        (CABECALHO + "A,-43,-22,-1\n", "negativa"),
        (CABECALHO + "A,-43,-95,1\n", "fora do intervalo"),
        (CABECALHO + "A,-43,-22,1\nA,-42,-22,2\nB,-41,-22,3\n", "repetido"),
        (CABECALHO + "A,-43,-22,1\nB,-42,-22,2\n", "pelo menos"),
    ],
)
def test_csv_invalido_e_recusado_com_o_motivo(tmp_path, conteudo, mensagem):
    caminho = tmp_path / "estacoes.csv"
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ValueError, match=mensagem):
        load_stations(caminho)
