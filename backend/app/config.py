"""Caminhos e constantes do projeto, num lugar só."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"

STATIONS_CSV = DATA_DIR / "stations.csv"
DAILY_CSV = DATA_DIR / "precipitation_daily.csv"
STUDY_AREA = DATA_DIR / "study_area.geojson"
VALUE_FIELD = "precip_mm"

# O arquivo é fechado: 1º de janeiro a 31 de agosto de 2026. O mapa abre no
# dia mais chuvoso (média de 47,5 mm), que mostra bem o que o IDW faz.
DEFAULT_DATE = "2026-01-20"

# Parâmetros do IDW escolhidos pelos dados (backend/scripts/otimizar_parametros.py):
# potência e vizinhos por validação cruzada nos 243 dias, resolução pela
# densidade da rede. Sem o arquivo, os valores clássicos da literatura.
PARAMETERS_JSON = DATA_DIR / "idw_parameters.json"


def _default_params() -> dict:
    try:
        escolha = json.loads(PARAMETERS_JSON.read_text(encoding="utf-8"))["chosen"]
        return {
            "power": float(escolha["power"]),
            "cell_size": float(escolha["cell_size"]),
            "neighbors": int(escolha["neighbors"]),
        }
    except (OSError, KeyError, ValueError):
        return {"power": 2.0, "cell_size": 1000.0, "neighbors": 12}


DEFAULT_PARAMS = _default_params()

# Os dados chegam em graus (WGS 84), mas o IDW pondera por distância e precisa
# de um sistema em metros. O SIRGAS 2000 / UTM 23S serve ao estado inteiro: o
# RJ vai de 44,9°W a 40,9°W e a zona 23 cobre de 48°W a 42°W. A faixa leste
# (Norte Fluminense e Região dos Lagos) passa da borda, onde a escala erra
# cerca de 0,2% — pouco para um método que usa distâncias relativas.
WGS84 = 4326
ANALYSIS_WKID = 31983
WEB_MERCATOR = 3857
