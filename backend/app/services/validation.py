"""Validação cruzada leave-one-out do IDW, em NumPy.

Tira uma estação, estima a chuva no lugar dela com as demais e compara com o
que ela mediu. Repetido para todas, dá o erro típico do método nesta rede.

A conta é a mesma do Idw do Spatial Analyst com raio variável: os `neighbors`
pontos mais próximos, com peso 1/d^power. Com ArcPy seria um IDW inteiro por
estação — 143 rodadas de alguns segundos; em NumPy são milissegundos. O teste
test_arcpy_consistency confere que as duas contas batem.
"""

from __future__ import annotations

import numpy as np


def _weighted_mean(distances: np.ndarray, values: np.ndarray, power: float) -> np.ndarray:
    """Média ponderada por 1/d^power, linha a linha.

    Se algum vizinho está exatamente no ponto (d = 0), o peso seria infinito:
    o IDW é um interpolador exato e devolve o valor medido ali.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        weights = 1.0 / distances**power
        estimate = (weights * values).sum(axis=1) / weights.sum(axis=1)

    coincident = distances == 0
    rows = coincident.any(axis=1)
    if rows.any():
        hits = coincident[rows]
        estimate[rows] = np.where(hits, values[rows], 0.0).sum(axis=1) / hits.sum(axis=1)
    return estimate


def _nearest(distances: np.ndarray, k: int) -> np.ndarray:
    """Índices dos k menores valores de cada linha (sem ordenar a linha toda)."""
    return np.argpartition(distances, k - 1, axis=1)[:, :k]


def idw_points(
    xy_known: np.ndarray,
    z_known: np.ndarray,
    xy_target: np.ndarray,
    power: float,
    neighbors: int,
) -> np.ndarray:
    """IDW em pontos quaisquer, com raio variável de `neighbors` pontos."""
    xy_known = np.asarray(xy_known, dtype=float)
    xy_target = np.asarray(xy_target, dtype=float)
    z_known = np.asarray(z_known, dtype=float)

    diff = xy_target[:, None, :] - xy_known[None, :, :]
    distances = np.hypot(diff[..., 0], diff[..., 1])
    k = min(neighbors, len(z_known))
    index = _nearest(distances, k)
    return _weighted_mean(
        np.take_along_axis(distances, index, axis=1), z_known[index], power
    )


def leave_one_out(xy: np.ndarray, z: np.ndarray, power: float, neighbors: int) -> np.ndarray:
    """Estimativa de cada estação feita sem ela."""
    xy = np.asarray(xy, dtype=float)
    z = np.asarray(z, dtype=float)
    if len(z) < 2:
        raise ValueError("leave-one-out precisa de pelo menos 2 estações")

    diff = xy[:, None, :] - xy[None, :, :]
    distances = np.hypot(diff[..., 0], diff[..., 1])
    # A diagonal é a distância da estação a ela mesma. Infinito a tira da
    # lista de vizinhos — é exatamente o "leave one out".
    np.fill_diagonal(distances, np.inf)

    k = min(neighbors, len(z) - 1)
    index = _nearest(distances, k)
    return _weighted_mean(np.take_along_axis(distances, index, axis=1), z[index], power)


def error_metrics(observed: np.ndarray, estimated: np.ndarray) -> dict:
    """MAE, RMSE e viés, com erro = estimado - observado.

    Viés negativo quer dizer que o IDW subestima — o que se espera nos picos:
    uma média ponderada nunca passa do maior valor medido ao redor.
    """
    error = np.asarray(estimated, dtype=float) - np.asarray(observed, dtype=float)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(np.mean(error)),
    }
