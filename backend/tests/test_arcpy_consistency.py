"""Confere que a conta em NumPy da validação é a mesma do Idw do ArcPy.

A validação leave-one-out é feita em NumPy por velocidade, e só vale se for a
mesma conta do Spatial Analyst. O teste sorteia células do raster gerado pelo
ArcPy e recalcula cada uma em NumPy. Sem ArcGIS Pro (no CI, por exemplo), é
pulado.
"""

import numpy as np
import pytest

arcpy = pytest.importorskip("arcpy")

from app import config  # noqa: E402
from app.services import idw_service as s  # noqa: E402
from app.services.validation import idw_points  # noqa: E402


@pytest.mark.parametrize("power, neighbors", [(2, 12), (1, 6), (3, 24)])
def test_idw_em_numpy_bate_com_o_arcpy(power, neighbors):
    arcpy.CheckOutExtension("Spatial")
    try:
        with arcpy.EnvManager(overwriteOutput=True):
            pontos = s.project(
                s.create_points(config.STATIONS_CSV, r"memory\t_pontos"),
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
