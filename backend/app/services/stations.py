"""Leitura e validação do CSV de estações."""

from __future__ import annotations

import csv
import math
from pathlib import Path

REQUIRED = ("station_id", "longitude", "latitude", "precip_mm")
MIN_STATIONS = 3


def load_stations(path: Path) -> list[dict]:
    """Lê o CSV e devolve as estações validadas.

    Falha cedo e aponta a linha do problema: um erro claro aqui é melhor do
    que um raster estranho no fim de um processamento de vários segundos.
    """
    with Path(path).open(encoding="utf-8-sig", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV sem as colunas obrigatórias: {', '.join(missing)}")

        stations: list[dict] = []
        seen: set[str] = set()
        for line, row in enumerate(reader, start=2):
            try:
                lon, lat, value = (
                    float(row[c]) for c in ("longitude", "latitude", "precip_mm")
                )
            except (TypeError, ValueError):
                raise ValueError(
                    f"linha {line}: longitude, latitude e precip_mm precisam ser números"
                ) from None
            if not all(math.isfinite(v) for v in (lon, lat, value)):
                raise ValueError(f"linha {line}: valor ausente ou infinito")
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError(f"linha {line}: coordenada fora do intervalo ({lon}, {lat})")
            if value < 0:
                raise ValueError(f"linha {line}: precipitação negativa ({value})")

            station_id = row["station_id"].strip()
            if station_id in seen:
                raise ValueError(f"linha {line}: station_id repetido ({station_id})")
            seen.add(station_id)

            stations.append({
                "station_id": station_id,
                "name": (row.get("name") or station_id).strip(),
                "municipality": (row.get("municipality") or "").strip(),
                "longitude": lon,
                "latitude": lat,
                "precip_mm": value,
                "date": (row.get("date") or "").strip(),
                "source": (row.get("source") or "").strip(),
            })

    if len(stations) < MIN_STATIONS:
        raise ValueError(
            f"o IDW precisa de pelo menos {MIN_STATIONS} estações; o CSV tem {len(stations)}"
        )
    return stations


def dataset_info(stations: list[dict]) -> dict:
    """Resumo do conjunto de entrada: data, fonte e a chuva observada."""
    values = [s["precip_mm"] for s in stations]
    dates = sorted({s["date"] for s in stations if s["date"]})
    sources = sorted({s["source"] for s in stations if s["source"]})
    return {
        "date": " a ".join(dict.fromkeys([dates[0], dates[-1]])) if dates else "",
        "window": "24 h",
        "source": ", ".join(sources),
        "station_count": len(stations),
        "observed_min": round(min(values), 1),
        "observed_mean": round(sum(values) / len(values), 1),
        "observed_max": round(max(values), 1),
    }
