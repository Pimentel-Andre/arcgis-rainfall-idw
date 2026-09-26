"""Contratos da API: o que entra e o que sai, validado pelo Pydantic.

Estes modelos são a documentação viva da API — o FastAPI os transforma na
página /docs — e a primeira barreira: um pedido fora dos limites volta com
422 antes de chegar perto do ArcPy.
"""

from pydantic import BaseModel, Field


class IdwParams(BaseModel):
    """Parâmetros do IDW.

    Os limites existem por dois motivos: evitar pedidos que travariam o
    servidor (célula de 10 m no estado inteiro são 440 milhões de células) e
    recusar os que não têm sentido (potência zero pesa todas as estações igual).
    """

    power: float = Field(
        2, gt=0, le=6,
        description="Potência: quanto uma estação próxima pesa mais que uma distante.",
    )
    cell_size: float = Field(
        1000, ge=250, le=5000,
        description="Resolução da célula do raster, em metros.",
    )
    neighbors: int = Field(
        12, ge=3, le=50,
        description="Estações usadas no cálculo de cada célula (raio variável).",
    )

    model_config = {
        "json_schema_extra": {"examples": [{"power": 2, "cell_size": 1000, "neighbors": 12}]}
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


class EngineInfo(BaseModel):
    available: bool
    arcpy_version: str | None = None
    product: str | None = None
    spatial_analyst: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    engine: EngineInfo
