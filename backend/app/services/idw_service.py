"""Pipeline IDW com ArcPy: CSV -> pontos -> projeção -> IDW com máscara -> GeoTIFF.

Cada etapa é uma função pequena, que recebe e devolve caminhos de dados — o
mesmo encadeamento que se faria à mão no ArcGIS Pro, na mesma ordem. Os
intermediários ficam no workspace `memory`, que não toca o disco.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app import config
from app.services import symbology, validation
from app.services.stations import (
    dataset_info, load_stations, stations_for_date, write_event_csv,
)

try:
    import arcpy
    from arcpy.sa import ExtractByMask, Idw, RadiusVariable

    # Sem isto cada ferramenta grava o próprio histórico num .xml ao lado
    # das saídas. Nada aqui precisa desse histórico.
    arcpy.SetLogHistory(False)
    ARCPY_ERROR = None
except Exception as exc:  # sem ArcGIS Pro instalado, ou sem licença
    arcpy = None
    ARCPY_ERROR = f"{type(exc).__name__}: {exc}"

WORKSPACE = "memory"
STATIONS = "stations.csv"
GEOTIFF = "precipitation_idw.tif"
PNG = "precipitation_idw.png"

# Os pontos chegam em WGS 84 e a análise é em SIRGAS 2000. Na prática os dois
# datums coincidem (diferença de centímetros), e a transformação que diz isso
# ao ArcGIS é esta, de parâmetros nulos. Explicitá-la evita que o Project
# escolha outra por conta própria.
DATUM_TRANSFORMATION = "SIRGAS_2000_To_WGS_1984_1"

# O ArcPy guarda estado global (arcpy.env, workspace memory) e não é seguro
# entre threads — e o FastAPI atende requisições em paralelo. Uma
# interpolação por vez.
_LOCK = threading.Lock()


class ArcPyUnavailable(RuntimeError):
    """ArcPy ou a extensão Spatial Analyst não estão disponíveis."""


def engine_info() -> dict:
    if arcpy is None:
        return {"available": False, "detail": ARCPY_ERROR}
    return {
        "available": True,
        "arcpy_version": arcpy.GetInstallInfo()["Version"],
        "product": arcpy.ProductInfo(),
        "spatial_analyst": arcpy.CheckExtension("Spatial"),
    }


def run_id(date: str, power: float, cell_size: float, neighbors: int) -> str:
    """Nome estável da rodada: o mesmo dia e parâmetros caem na mesma pasta."""
    return f"idw_{date}_p{power:g}_c{cell_size:g}_n{neighbors}"


# --- Etapas ----------------------------------------------------------------

def create_points(csv_path: Path, out_fc: str) -> str:
    """Etapa 2 — longitude + latitude do CSV viram uma feature class de pontos."""
    arcpy.management.XYTableToPoint(
        str(csv_path), out_fc, "longitude", "latitude",
        coordinate_system=arcpy.SpatialReference(config.WGS84),
    )
    return out_fc


def load_study_area(geojson_path: Path, out_fc: str) -> str:
    """O polígono do estado, que vira a máscara da interpolação."""
    arcpy.conversion.JSONToFeatures(str(geojson_path), out_fc, "POLYGON")
    return out_fc


def project(in_fc: str, out_fc: str, wkid: int) -> str:
    """Etapa 3 — de graus para metros, antes de qualquer conta de distância."""
    arcpy.management.Project(
        in_fc, out_fc, arcpy.SpatialReference(wkid), DATUM_TRANSFORMATION
    )
    return out_fc


def snapped_extent(fc: str, cell_size: float):
    """Extensão da feature class alinhada a múltiplos do tamanho da célula.

    Assim rodadas com a mesma resolução geram grades que se sobrepõem célula
    a célula, e os centros caem em coordenadas redondas.
    """
    e = arcpy.Describe(fc).extent
    return arcpy.Extent(
        np.floor(e.XMin / cell_size) * cell_size,
        np.floor(e.YMin / cell_size) * cell_size,
        np.ceil(e.XMax / cell_size) * cell_size,
        np.ceil(e.YMax / cell_size) * cell_size,
        spatial_reference=e.spatialReference,
    )


def interpolate(points_fc: str, mask_fc: str, value_field: str,
                cell_size: float, power: float, neighbors: int):
    """Etapas 4 e 5 — IDW com raio variável, recortado pela área de estudo.

    O IDW cobre o retângulo envolvente do estado; o ExtractByMask apaga (vira
    NoData) o que cai fora do polígono — mar e estados vizinhos, onde não há
    estação e a superfície seria pura extrapolação.
    """
    with arcpy.EnvManager(
        outputCoordinateSystem=arcpy.Describe(points_fc).spatialReference,
        extent=snapped_extent(mask_fc, cell_size),
        cellSize=cell_size,
    ):
        surface = Idw(
            in_point_features=points_fc,
            z_field=value_field,
            cell_size=cell_size,
            power=power,
            search_radius=RadiusVariable(neighbors),
        )
        return ExtractByMask(surface, mask_fc)


def save_geotiff(raster, path: Path) -> Path:
    """Etapa 6 — o resultado analítico: GeoTIFF float32, na projeção da análise.

    As estatísticas saem junto com a gravação (rasterStatistics), para o
    ArcGIS Pro abrir o arquivo com o histograma certo. Calculá-las depois com
    CalculateStatistics custava 25 s por rodada; aqui custa milissegundos.
    """
    with arcpy.EnvManager(compression="LZW", pyramid="NONE",
                          rasterStatistics="STATISTICS 1 1"):
        raster.save(str(path))
    return path


def raster_summary(path: Path) -> dict:
    raster = arcpy.Raster(str(path))
    values = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan)
    valid = values[np.isfinite(values)]
    cell_size = raster.meanCellWidth
    summary = {
        "min": float(valid.min()),
        "max": float(valid.max()),
        "mean": float(valid.mean()),
        "columns": raster.width,
        "rows": raster.height,
        "valid_cells": int(valid.size),
        "area_km2": round(valid.size * cell_size * cell_size / 1e6),
        "wkid": raster.spatialReference.factoryCode,
        "spatial_reference": raster.spatialReference.name,
    }
    del raster  # solta o arquivo antes das próximas etapas
    return summary


def export_web_image(tif_path: Path, png_path: Path) -> dict:
    """Uma cópia para o mapa web: reprojetada para Web Mercator e colorida.

    O basemap está em Web Mercator (EPSG:3857). Projetar o raster para o
    mesmo sistema é o que deixa o PNG cair no lugar certo quando o
    front-end o ancora pela extensão.

    É a etapa mais lenta (~3 s, quase tudo custo fixo da ferramenta). A
    função raster arcpy.ia.Reproject faz o mesmo em ~0,1 s, mas exige a
    extensão Image Analyst — e o projeto pede só o Spatial Analyst.
    """
    web_tif = png_path.with_name("_web_mercator.tif")
    arcpy.management.ProjectRaster(
        str(tif_path), str(web_tif), arcpy.SpatialReference(config.WEB_MERCATOR),
        "BILINEAR", geographic_transform=DATUM_TRANSFORMATION,
    )
    raster = arcpy.Raster(str(web_tif))
    values = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan)
    extent = raster.extent
    del raster
    arcpy.management.Delete(str(web_tif))

    symbology.save_png(values, png_path)
    return {
        "xmin": extent.XMin, "ymin": extent.YMin,
        "xmax": extent.XMax, "ymax": extent.YMax,
        "wkid": config.WEB_MERCATOR,
    }


def read_points(points_fc: str, value_field: str):
    """IDs, coordenadas projetadas e valores das estações, para a validação."""
    rows = [
        (str(sid), x, y, value)
        for sid, (x, y), value in arcpy.da.SearchCursor(
            points_fc, ["station_id", "SHAPE@XY", value_field]
        )
    ]
    ids = [r[0] for r in rows]
    xy = np.array([(r[1], r[2]) for r in rows])
    z = np.array([r[3] for r in rows], dtype=float)
    return ids, xy, z


# --- Orquestração ----------------------------------------------------------

def run_idw(
    date: str = config.DEFAULT_DATE,
    power: float = 2,
    cell_size: float = 1000,
    neighbors: int = 12,
    study_area: Path | None = None,
    outputs_dir: Path | None = None,
) -> dict:
    """Roda o pipeline inteiro para um dia e devolve o resultado que a API publica."""
    # O dia é conferido antes do ArcPy: um erro de data é do pedido, e deve
    # voltar como tal mesmo numa máquina sem licença.
    rows = stations_for_date(date)
    if arcpy is None:
        raise ArcPyUnavailable(f"ArcPy indisponível ({ARCPY_ERROR})")
    study_area = study_area or config.STUDY_AREA
    outputs_dir = outputs_dir or config.OUTPUTS_DIR

    rid = run_id(date, power, cell_size, neighbors)
    out_dir = Path(outputs_dir) / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    tif_path, png_path = out_dir / GEOTIFF, out_dir / PNG

    # O dia vira um CSV de evento dentro da pasta da rodada: fica registrado
    # exatamente o que entrou no IDW, ao lado do que saiu dele.
    stations_csv = write_event_csv(rows, out_dir / STATIONS)
    stations = load_stations(stations_csv)

    with _LOCK:
        started = time.perf_counter()
        if arcpy.CheckOutExtension("Spatial") != "CheckedOut":
            raise ArcPyUnavailable("extensão Spatial Analyst indisponível")
        try:
            with arcpy.EnvManager(overwriteOutput=True):
                points = create_points(stations_csv, rf"{WORKSPACE}\stations")
                points_utm = project(points, rf"{WORKSPACE}\stations_utm", config.ANALYSIS_WKID)
                area = load_study_area(study_area, rf"{WORKSPACE}\study_area")
                area_utm = project(area, rf"{WORKSPACE}\study_area_utm", config.ANALYSIS_WKID)

                raster = interpolate(points_utm, area_utm, config.VALUE_FIELD,
                                     cell_size, power, neighbors)
                save_geotiff(raster, tif_path)
                del raster

                summary = raster_summary(tif_path)
                image_extent = export_web_image(tif_path, png_path)
                ids, xy, z = read_points(points_utm, config.VALUE_FIELD)
        finally:
            arcpy.management.Delete(WORKSPACE)
            arcpy.CheckInExtension("Spatial")
        elapsed = time.perf_counter() - started

    estimated = validation.leave_one_out(xy, z, power, neighbors)
    metrics = validation.error_metrics(z, estimated)

    result = {
        "status": "success",
        "method": "IDW",
        "engine": f"ArcPy {arcpy.GetInstallInfo()['Version']} · Spatial Analyst",
        "run_id": rid,
        "date": date,
        "power": power,
        "cell_size": cell_size,
        "neighbors": neighbors,
        "station_count": len(ids),
        "min_precipitation": round(summary["min"], 1),
        "max_precipitation": round(summary["max"], 1),
        "mean_precipitation": round(summary["mean"], 1),
        "output": GEOTIFF,
        "files": {"geotiff": GEOTIFF, "png": PNG, "stations": STATIONS},
        "raster": {
            "columns": summary["columns"],
            "rows": summary["rows"],
            "cell_size": cell_size,
            "valid_cells": summary["valid_cells"],
            "area_km2": summary["area_km2"],
            "wkid": summary["wkid"],
            "spatial_reference": summary["spatial_reference"],
        },
        "image_extent": image_extent,
        "legend": symbology.legend(),
        "validation": {
            "method": "leave-one-out",
            "mae": round(metrics["mae"], 2),
            "rmse": round(metrics["rmse"], 2),
            "bias": round(metrics["bias"], 2),
            "stations": [
                {
                    "station_id": sid,
                    "observed": round(float(obs), 1),
                    "estimated": round(float(est), 1),
                    "error": round(float(est - obs), 1),
                }
                for sid, obs, est in zip(ids, z, estimated)
            ],
        },
        "dataset": dataset_info(stations),
        "elapsed_seconds": round(elapsed, 2),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
