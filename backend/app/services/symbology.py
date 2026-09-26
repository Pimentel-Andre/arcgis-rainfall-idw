"""Classes de chuva e a imagem colorida da superfície.

A mesma lista de classes pinta o PNG da superfície, as estações no mapa e a
legenda: o front-end recebe as classes na resposta da API em vez de repeti-las,
então as três leituras nunca discordam.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

# Limite SUPERIOR de cada classe, fechado à direita — como no renderer de
# classes do ArcGIS, onde 10 mm exatos caem em "0–10". Com isso o pixel e a
# estação de mesmo valor recebem sempre a mesma cor.
BREAKS = [10, 20, 30, 40, 60, 80]

# Rampa sequencial de um só matiz, clara -> escura, em passos iguais de uma
# escala validada para luminosidade monotônica. Chuva é magnitude: mais chuva,
# mais escuro. Arco-íris pareceria bonito e atrapalharia a leitura.
COLORS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# Índice da paleta reservado para "sem dado" (fora da área de estudo).
TRANSPARENT = len(COLORS)


def legend() -> list[dict]:
    lows = [0, *BREAKS]
    highs = [*BREAKS, None]
    return [
        {
            "min": low,
            "max": high,
            "color": color,
            "label": f"{low}–{high}" if high is not None else f"> {low}",
        }
        for low, high, color in zip(lows, highs, COLORS)
    ]


def classify(values: np.ndarray) -> np.ndarray:
    """Índice da classe de cada valor; NaN vira o índice transparente."""
    values = np.asarray(values, dtype=float)
    index = np.digitize(values, BREAKS, right=True).astype(np.uint8)
    index[np.isnan(values)] = TRANSPARENT
    return index


def _hex_to_rgb(color: str) -> list[int]:
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def save_png(values: np.ndarray, path: Path) -> Path:
    """Grava a superfície classificada como PNG de paleta.

    Oito cores (sete classes + transparente) cabem num PNG de paleta, que sai
    várias vezes menor que um RGBA — importa para o site estático, que guarda
    dezenas desses arquivos.
    """
    index = classify(values)
    height, width = index.shape
    image = Image.frombytes("P", (width, height), np.ascontiguousarray(index).tobytes())
    palette = [channel for color in COLORS for channel in _hex_to_rgb(color)]
    image.putpalette(palette + [0, 0, 0])
    image.save(path, transparency=TRANSPARENT, optimize=True)
    return Path(path)
