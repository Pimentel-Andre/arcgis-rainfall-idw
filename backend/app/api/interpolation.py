"""Rotas REST. O Vue só conhece estes endereços — nunca o ArcPy."""

import datetime as dt

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app import config
from app.schemas.interpolation import (
    DatesResponse, HealthResponse, IdwParams, IdwResult, StationsResponse,
)
from app.services import idw_service, symbology
from app.services.stations import (
    DateNotAvailable, available_dates, dataset_info, stations_for_date,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    """Diz se o ArcPy e o Spatial Analyst estão disponíveis nesta máquina."""
    return {"status": "ok", "engine": idw_service.engine_info()}


@router.get("/dates", response_model=DatesResponse)
def dates():
    """Os dias do arquivo (jan–ago/2026), cada um com o resumo da chuva."""
    return {"default": config.DEFAULT_DATE, "dates": available_dates()}


@router.get("/stations", response_model=StationsResponse)
def stations(date: dt.date = Query(dt.date.fromisoformat(config.DEFAULT_DATE))):
    """As estações com leitura no dia, com a chuva medida e as classes da legenda."""
    try:
        rows = stations_for_date(date.isoformat())
    except DateNotAvailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"dataset": dataset_info(rows), "legend": symbology.legend(), "stations": rows}


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
        return idw_service.run_idw(
            params.date.isoformat(), params.power, params.cell_size, params.neighbors
        )
    except idw_service.ArcPyUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:  # dia fora do arquivo, CSV de evento inválido
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # arcpy.ExecuteError e afins
        raise HTTPException(status_code=500, detail=f"Falha no processamento: {exc}") from exc
