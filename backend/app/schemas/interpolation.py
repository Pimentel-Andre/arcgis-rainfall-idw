"""Contratos da API: o que entra e o que sai, validado pelo Pydantic.

Estes modelos são a documentação viva da API — o FastAPI os transforma na
página /docs — e a primeira barreira: um pedido fora dos limites volta com
422 antes de chegar perto do ArcPy.
"""

import datetime as dt

from pydantic import BaseModel, Field

from app.config import DEFAULT_DATE, DEFAULT_PARAMS


class IdwParams(BaseModel):
    """Parâmetros do IDW.

    Os padrões não são os de fábrica: saem da validação cruzada nos 243 dias
    (scripts/otimizar_parametros.py). Os limites existem por dois motivos:
    evitar pedidos que travariam o servidor (célula de 10 m no estado inteiro
    são 440 milhões de células) e recusar os que não têm sentido (potência zero
    pesa todas as estações igual).
    """

    # `dt.date`, e não `date` importado solto: um campo chamado date com o
    # tipo date confunde o Pydantic.
    date: dt.date = Field(
        dt.date.fromisoformat(DEFAULT_DATE),
        description="Dia da chuva de 24 h (janela UTC), de 2026-01-01 a 2026-08-31.",
    )
    power: float = Field(
        DEFAULT_PARAMS["power"], gt=0, le=6,
        description="Potência: quanto uma estação próxima pesa mais que uma distante.",
    )
    cell_size: float = Field(
        DEFAULT_PARAMS["cell_size"], ge=250, le=5000,
        description="Resolução da célula do raster, em metros.",
    )
    neighbors: int = Field(
        DEFAULT_PARAMS["neighbors"], ge=3, le=50,
        description="Estações usadas no cálculo de cada célula (raio variável).",
    )

    model_config = {
        "json_schema_extra": {"examples": [{"date": DEFAULT_DATE, **DEFAULT_PARAMS}]}
    }


class Extent(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    wkid: int


class LegendClass(BaseModel):
    min: float
    max: float | None
    color: str
    label: str


class RasterInfo(BaseModel):
    columns: int
    rows: int
    cell_size: float
    valid_cells: int
    area_km2: float
    wkid: int
    spatial_reference: str


class StationValidation(BaseModel):
    station_id: str
    observed: float
    estimated: float
    error: float


class Validation(BaseModel):
    method: str
    mae: float
    rmse: float
    bias: float
    stations: list[StationValidation]


class DatasetInfo(BaseModel):
    date: str
    window: str
    source: str
    station_count: int
    observed_min: float
    observed_mean: float
    observed_max: float


class IdwResult(BaseModel):
    status: str
    method: str
    engine: str
    run_id: str
    date: str
    power: float
    cell_size: float
    neighbors: int
    station_count: int
    min_precipitation: float
    max_precipitation: float
    mean_precipitation: float
    output: str
    files: dict[str, str]
    raster: RasterInfo
    image_extent: Extent
    legend: list[LegendClass]
    validation: Validation
    dataset: DatasetInfo
    elapsed_seconds: float
    created_at: str


class Station(BaseModel):
    station_id: str
    name: str
    municipality: str
    longitude: float
    latitude: float
    precip_mm: float


class StationsResponse(BaseModel):
    dataset: DatasetInfo
    legend: list[LegendClass]
    stations: list[Station]


class DaySummary(BaseModel):
    date: str
    station_count: int
    mean: float
    max: float


class DatesResponse(BaseModel):
    default: str
    dates: list[DaySummary]


class EngineInfo(BaseModel):
    available: bool
    arcpy_version: str | None = None
    product: str | None = None
    spatial_analyst: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    engine: EngineInfo
