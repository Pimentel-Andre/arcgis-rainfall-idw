import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import idw_service

cliente = TestClient(app)


def test_health():
    resposta = cliente.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_dias_disponiveis():
    corpo = cliente.get("/api/dates").json()
    assert corpo["default"] == "2026-01-20"
    assert len(corpo["dates"]) == 243


def test_estacoes_do_dia_com_legenda():
    corpo = cliente.get("/api/stations", params={"date": "2026-01-20"}).json()
    assert len(corpo["stations"]) == 143
    assert corpo["dataset"]["date"] == "2026-01-20"
    assert len(corpo["legend"]) == 7


def test_estacoes_de_dia_fora_do_arquivo_404():
    assert cliente.get("/api/stations", params={"date": "2026-09-15"}).status_code == 404


def test_area_de_estudo_e_geojson():
    resposta = cliente.get("/api/study-area")
    assert resposta.headers["content-type"].startswith("application/geo+json")
    assert resposta.json()["type"] == "FeatureCollection"


@pytest.mark.parametrize(
    "parametros",
    [
        {"power": 0}, {"power": 7}, {"cell_size": 10}, {"neighbors": 1},
        {"neighbors": 2.5}, {"date": "20/01/2026"}, {"date": "2026-09-15"},
    ],
)
def test_pedido_invalido_volta_422(parametros):
    resposta = cliente.post("/api/interpolations/idw", json=parametros)
    assert resposta.status_code == 422


@pytest.mark.skipif(idw_service.arcpy is None, reason="ArcPy indisponível (sem ArcGIS Pro ou sem licença)")
def test_idw_de_ponta_a_ponta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path)

    resposta = cliente.post(
        "/api/interpolations/idw",
        json={"date": "2026-02-27", "power": 2, "cell_size": 5000, "neighbors": 12},
    )
    assert resposta.status_code == 200, resposta.text
    r = resposta.json()
    assert r["status"] == "success"
    assert r["run_id"] == "idw_2026-02-27_p2_c5000_n12"
    assert r["date"] == "2026-02-27"
    assert 0 <= r["min_precipitation"] <= r["mean_precipitation"] <= r["max_precipitation"]
    assert len(r["validation"]["stations"]) == r["station_count"]
    assert r["image_extent"]["wkid"] == 3857
    pasta = tmp_path / r["run_id"]
    for arquivo in r["files"].values():
        assert (pasta / arquivo).exists()
