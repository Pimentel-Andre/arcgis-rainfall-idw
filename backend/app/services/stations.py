"""Estações e chuva diária: leitura, validação e o recorte de um dia.

Os dados ficam em duas tabelas, como num banco: o catálogo de estações
(data/stations.csv, uma linha por estação) e a chuva diária
(data/precipitation_daily.csv, uma linha por estação e dia com leitura). O IDW
de um dia junta as duas num CSV de evento, no formato do plano do projeto:
station_id, name, longitude, latitude, precip_mm.
"""

from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

from app import config

REQUIRED = ("station_id", "longitude", "latitude", "precip_mm")
EVENT_FIELDS = [
    "station_id", "name", "municipality", "longitude", "latitude",
    "precip_mm", "date", "source",
]
MIN_STATIONS = 3


class DateNotAvailable(ValueError):
    """Dia fora do arquivo, ou com estações de menos para interpolar."""


# lru_cache: os CSVs são lidos uma vez por processo, não a cada requisição.
@lru_cache
def _read_catalog(path: Path) -> dict[str, dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as arquivo:
        return {
            row["station_id"]: {
                "station_id": row["station_id"],
                "name": row["name"],
                "municipality": row["municipality"],
                "longitude": float(row["longitude"]),
                "latitude": float(row["latitude"]),
                "source": row["source"],
            }
            for row in csv.DictReader(arquivo)
        }


@lru_cache
def _read_daily(path: Path) -> dict[str, list[tuple[str, float]]]:
    days: dict[str, list[tuple[str, float]]] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as arquivo:
        for row in csv.DictReader(arquivo):
            days.setdefault(row["date"], []).append((row["station_id"], float(row["precip_mm"])))
    return days


def available_dates() -> list[dict]:
    """Os dias do arquivo, com um resumo da chuva — o que o seletor de data mostra."""
    resumo = []
    for date, readings in sorted(_read_daily(config.DAILY_CSV).items()):
        values = [value for _, value in readings]
        resumo.append({
            "date": date,
            "station_count": len(values),
            "mean": round(sum(values) / len(values), 1),
            "max": round(max(values), 1),
        })
    return resumo


def stations_for_date(date: str) -> list[dict]:
    """As estações com leitura no dia, já com a chuva, no formato do CSV de evento.

    Estação sem leitura no dia simplesmente não aparece — "não mediu" não é
    "não choveu".
    """
    days = _read_daily(config.DAILY_CSV)
    readings = days.get(date)
    if readings is None:
        first, last = min(days), max(days)
        raise DateNotAvailable(f"sem dados para {date}; o arquivo vai de {first} a {last}")
    if len(readings) < MIN_STATIONS:
        raise DateNotAvailable(f"{date} tem só {len(readings)} estações com leitura")

    catalog = _read_catalog(config.STATIONS_CSV)
    return [{**catalog[sid], "precip_mm": value, "date": date} for sid, value in readings]


def write_event_csv(rows: list[dict], path: Path) -> Path:
    """Grava o CSV de um dia — a entrada do XYTableToPoint."""
    with Path(path).open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=EVENT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return Path(path)


def load_stations(path: Path) -> list[dict]:
    """Lê um CSV de evento e devolve as estações validadas.

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
