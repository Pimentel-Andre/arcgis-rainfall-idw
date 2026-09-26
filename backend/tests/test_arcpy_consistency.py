"""Confere que a conta em NumPy da validação é a mesma do Idw do ArcPy.

A validação leave-one-out é feita em NumPy por velocidade, e só vale se for a
mesma conta do Spatial Analyst. O teste sorteia células do raster gerado pelo
ArcPy e recalcula cada uma em NumPy. Sem ArcPy disponível (no CI, ou sem a
licença do ArcGIS Pro ativa), é pulado.
"""

import numpy as np
import pytest

from app import config
from app.services import idw_service as s
from app.services.stations import stations_for_date, write_event_csv
from app.services.validation import idw_points

if s.arcpy is None:
    pytest.skip(f"ArcPy indisponível: {s.ARCPY_ERROR}", allow_module_level=True)

arcpy = s.arcpy


@pytest.mark.parametrize(
    "dia, power, neighbors",
    [("2026-01-20", 2, 12), ("2026-02-27", 1, 6), ("2026-05-20", 3, 24)],
)
def test_idw_em_numpy_bate_com_o_arcpy(tmp_path, dia, power, neighbors):
    csv_do_dia = write_event_csv(stations_for_date(dia), tmp_path / "estacoes.csv")
    arcpy.CheckOutExtension("Spatial")
    try:
        with arcpy.EnvManager(overwriteOutput=True):
            pontos = s.project(
                s.create_points(csv_do_dia, r"memory\t_pontos"),
                r"memory\t_pontos_utm", config.ANALYSIS_WKID,
            )
            area = s.project(
                s.load_study_area(config.STUDY_AREA, r"memory\t_area"),
                r"memory\t_area_utm", config.ANALYSIS_WKID,
            )
            raster = s.interpolate(pontos, area, config.VALUE_FIELD, 2000, power, neighbors)
            grade = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan)
            extensao, celula = raster.extent, raster.meanCellWidth
            _, xy, z = s.read_points(pontos, config.VALUE_FIELD)
    finally:
        arcpy.management.Delete("memory")
        arcpy.CheckInExtension("Spatial")

    linhas, colunas = np.nonzero(np.isfinite(grade))
    sorteio = np.random.default_rng(0).choice(len(linhas), 300, replace=False)
    lin, col = linhas[sorteio], colunas[sorteio]
    # Linha 0 do array é a do topo (norte); o valor vale no centro da célula.
    centros = np.column_stack([
        extensao.XMin + (col + 0.5) * celula,
        extensao.YMax - (lin + 0.5) * celula,
    ])
    esperado = idw_points(xy, z, centros, power, neighbors)
    np.testing.assert_allclose(grade[lin, col], esperado, atol=0.01)
