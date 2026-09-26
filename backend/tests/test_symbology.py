import numpy as np
from PIL import Image

from app.services import symbology


def test_classes_fechadas_a_direita_como_no_arcgis():
    # 10 mm exatos ficam em "0–10", igual ao renderer de classes do ArcGIS,
    # para o pixel e a estação de mesmo valor terem a mesma cor.
    classes = symbology.classify(np.array([0, 10, 10.1, 80, 80.1, 500]))
    assert classes.tolist() == [0, 0, 1, 5, 6, 6]


def test_sem_dado_vira_transparente():
    assert symbology.classify(np.array([np.nan]))[0] == symbology.TRANSPARENT


def test_legenda_acompanha_as_cores():
    legenda = symbology.legend()
    assert len(legenda) == len(symbology.COLORS)
    assert legenda[0] == {"min": 0, "max": 10, "color": "#cde2fb", "label": "0–10"}
    assert legenda[-1]["max"] is None
    assert legenda[-1]["label"] == "> 80"


def test_png_de_paleta_com_transparencia(tmp_path):
    valores = np.array([[5.0, np.nan], [45.0, 200.0]])
    imagem = Image.open(symbology.save_png(valores, tmp_path / "superficie.png"))
    assert imagem.mode == "P"
    assert imagem.size == (2, 2)
    assert imagem.info["transparency"] == symbology.TRANSPARENT
    # Em modo paleta, o array da imagem são os índices das classes.
    assert np.array(imagem).ravel().tolist() == [0, symbology.TRANSPARENT, 4, 6]
