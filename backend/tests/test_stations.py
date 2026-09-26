import pytest

from app import config
from app.services.stations import dataset_info, load_stations

CABECALHO = "station_id,longitude,latitude,precip_mm\n"


def test_csv_de_exemplo():
    estacoes = load_stations(config.STATIONS_CSV)
    info = dataset_info(estacoes)
    assert len(estacoes) == 143
    assert info["date"] == "2026-01-20"
    assert info["source"] == "CEMADEN"
    assert info["observed_max"] == 182.8


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
