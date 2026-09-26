import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

cliente = TestClient(app)


def test_health():
    resposta = cliente.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_estacoes_com_legenda():
    corpo = cliente.get("/api/stations").json()
    assert len(corpo["stations"]) == 143
    assert corpo["dataset"]["date"] == "2026-01-20"
    assert len(corpo["legend"]) == 7


def test_area_de_estudo_e_geojson():
    resposta = cliente.get("/api/study-area")
    assert resposta.headers["content-type"].startswith("application/geo+json")
    assert resposta.json()["type"] == "FeatureCollection"


@pytest.mark.parametrize(
    "parametros",
    [{"power": 0}, {"power": 7}, {"cell_size": 10}, {"neighbors": 1}, {"neighbors": 2.5}],
)
def test_parametros_fora_dos_limites_voltam_422(parametros):
    resposta = cliente.post("/api/interpolations/idw", json=parametros)
    assert resposta.status_code == 422


def test_idw_de_ponta_a_ponta(tmp_path, monkeypatch):
    pytest.importorskip("arcpy")
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path)

    resposta = cliente.post(
        "/api/interpolations/idw", json={"power": 2, "cell_size": 5000, "neighbors": 12}
    )
    assert resposta.status_code == 200, resposta.text
    r = resposta.json()
    assert r["status"] == "success"
    assert r["run_id"] == "idw_p2_c5000_n12"
    assert r["station_count"] == 143
    assert 0 <= r["min_precipitation"] <= r["mean_precipitation"] <= r["max_precipitation"]
    assert len(r["validation"]["stations"]) == 143
    assert r["image_extent"]["wkid"] == 3857
    assert (tmp_path / r["run_id"] / r["files"]["png"]).exists()
    assert (tmp_path / r["run_id"] / r["files"]["geotiff"]).exists()
