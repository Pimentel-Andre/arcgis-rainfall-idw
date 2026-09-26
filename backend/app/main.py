"""API REST do projeto: FastAPI na frente, ArcPy atrás.

Rodar, de dentro de backend/, no ambiente clonado do ArcGIS Pro:
    uvicorn app.main:app --reload
Documentação interativa em http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.api.interpolation import router

app = FastAPI(
    title="Rainfall IDW API",
    description=(
        "Interpolação IDW de precipitação com ArcPy (Spatial Analyst) sobre os "
        "pluviômetros do CEMADEN no estado do Rio de Janeiro."
    ),
    version="1.0.0",
)

app.include_router(router, prefix="/api")

# Os GeoTIFFs e PNGs gerados ficam acessíveis por URL: é por aqui que o mapa
# baixa a imagem da superfície e o usuário baixa o raster.
config.OUTPUTS_DIR.mkdir(exist_ok=True)
app.mount("/outputs", StaticFiles(directory=config.OUTPUTS_DIR), name="outputs")
