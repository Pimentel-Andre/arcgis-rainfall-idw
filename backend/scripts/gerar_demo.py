"""Congela respostas da API em arquivos, para o site estático (GitHub Pages).

O GitHub Pages só serve arquivos: não roda Python, muito menos ArcPy. Então o
backend processa aqui todos os dias do arquivo e grava cada resposta
exatamente como a API a devolveria. No "modo demonstração", o front-end lê
esses arquivos com o mesmo código que usa para falar com a API.

É a mesma ideia do serie.json do monitor-chuva-rj: o dado viaja congelado do
Python até o navegador. Cada arquivo gerado é uma resposta da API:

    dates.json                  GET  /api/dates (+ os parâmetros do modo demo)
    study_area.geojson          GET  /api/study-area
    stations/<dia>.json         GET  /api/stations?date=<dia>
    idw/<rodada>/result.json    POST /api/interpolations/idw, com o PNG ao lado

Uso, no ambiente do ArcGIS Pro com a licença ativa:
    python backend/scripts/gerar_demo.py             # reaproveita o que já existe em outputs/
    python backend/scripts/gerar_demo.py --refazer   # reprocessa todos os dias
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.services import symbology  # noqa: E402
from app.services.idw_service import (  # noqa: E402
    GEOTIFF, PNG, ArcPyUnavailable, run_id, run_idw,
)
from app.services.stations import (  # noqa: E402
    available_dates, dataset_info, stations_for_date,
)

DESTINO = config.ROOT / "frontend" / "public" / "demo"

# No site estático os parâmetros ficam fixos: 243 dias × uma combinação. Variar
# potência, resolução e vizinhos é trabalho da API local, com o ArcPy.
PADRAO = {"power": 2, "cell_size": 1000, "neighbors": 12}
CAMPOS_ESTACAO = ("station_id", "name", "municipality", "longitude", "latitude", "precip_mm")


def gravar_json(caminho: Path, dados) -> None:
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def resultado_do_dia(dia: str, refazer: bool):
    """Reaproveita a rodada gravada em outputs/, ou processa com o ArcPy."""
    pasta = config.OUTPUTS_DIR / run_id(dia, **PADRAO)
    gravado = pasta / "result.json"
    if gravado.exists() and (pasta / PNG).exists() and not refazer:
        return json.loads(gravado.read_text(encoding="utf-8")), pasta
    return run_idw(dia, **PADRAO), pasta


def main() -> None:
    p = argparse.ArgumentParser(description="Gera os arquivos do modo demonstração")
    p.add_argument("--refazer", action="store_true", help="reprocessa mesmo o que já existe")
    args = p.parse_args()

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    (DESTINO / "stations").mkdir(parents=True)
    (DESTINO / "idw").mkdir()
    shutil.copyfile(config.STUDY_AREA, DESTINO / "study_area.geojson")

    legenda = symbology.legend()
    resumos = available_dates()
    dias, faltando = [], []
    inicio = time.perf_counter()
    for n, resumo in enumerate(resumos, start=1):
        dia = resumo["date"]
        linhas = stations_for_date(dia)
        gravar_json(DESTINO / "stations" / f"{dia}.json", {
            "dataset": dataset_info(linhas),
            "legend": legenda,
            "stations": [{k: s[k] for k in CAMPOS_ESTACAO} for s in linhas],
        })

        try:
            resultado, pasta = resultado_do_dia(dia, args.refazer)
        except ArcPyUnavailable:
            faltando.append(dia)
            continue

        saida = DESTINO / "idw" / resultado["run_id"]
        saida.mkdir()
        shutil.copyfile(pasta / PNG, saida / PNG)
        arquivos = {"png": PNG}
        # O GeoTIFF só vai no dia padrão: 243 rasters pesariam no
        # repositório, e um basta para quem quiser abri-lo no ArcGIS Pro.
        if dia == config.DEFAULT_DATE:
            shutil.copyfile(pasta / GEOTIFF, saida / GEOTIFF)
            arquivos["geotiff"] = GEOTIFF
        gravar_json(saida / "result.json", {**resultado, "files": arquivos})
        dias.append({**resumo, "run_id": resultado["run_id"]})
        print(f"  {n:3}/{len(resumos)} {dia} · {time.perf_counter() - inicio:6.0f} s", flush=True)

    gravar_json(DESTINO / "dates.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "default": config.DEFAULT_DATE,
        "params": PADRAO,
        "dates": dias,
    })

    tamanho = sum(f.stat().st_size for f in DESTINO.rglob("*") if f.is_file()) / 1024**2
    print(f"{len(dias)} dias em {DESTINO} ({tamanho:.1f} MB)")
    if faltando:
        print(f"{len(faltando)} dias sem ArcPy disponível — abra o ArcGIS Pro e rode de novo.")


if __name__ == "__main__":
    main()
