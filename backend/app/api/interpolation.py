"""Rotas REST. O Vue só conhece estes endereços — nunca o ArcPy."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config
from app.schemas.interpolation import (
    HealthResponse, IdwParams, IdwResult, StationsResponse,
)
from app.services import idw_service, symbology
from app.services.stations import dataset_info, load_stations

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    """Diz se o ArcPy e o Spatial Analyst estão disponíveis nesta máquina."""
    return {"status": "ok", "engine": idw_service.engine_info()}


@router.get("/stations", response_model=StationsResponse)
def stations():
    """As estações de entrada, com a chuva observada e as classes da legenda."""
    data = load_stations(config.STATIONS_CSV)
    return {"dataset": dataset_info(data), "legend": symbology.legend(), "stations": data}


@router.get("/study-area")
def study_area():
    """O limite do estado, em GeoJSON, para o mapa desenhar o contorno."""
    return FileResponse(config.STUDY_AREA, media_type="application/geo+json")


# `def`, e não `async def`: o ArcPy bloqueia, e o FastAPI roda rotas síncronas
# numa thread à parte, sem travar o servidor enquanto o IDW calcula.
@router.post("/interpolations/idw", response_model=IdwResult)
def run_idw(params: IdwParams):
    """Executa o IDW com ArcPy e devolve estatísticas, validação e a imagem."""
    try:
        return idw_service.run_idw(params.power, params.cell_size, params.neighbors)
    except idw_service.ArcPyUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:  # CSV de entrada inválido
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # arcpy.ExecuteError e afins
        raise HTTPException(status_code=500, detail=f"Falha no processamento: {exc}") from exc
