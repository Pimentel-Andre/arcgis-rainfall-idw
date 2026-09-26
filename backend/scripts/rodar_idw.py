"""V0.1 do projeto: roda o IDW com ArcPy direto do terminal, sem API.

É o jeito mais curto de ver o processamento GIS funcionando — e de depurá-lo
— antes de pôr uma API e um mapa na frente.

Uso, no ambiente clonado do ArcGIS Pro:
    python backend/scripts/rodar_idw.py
    python backend/scripts/rodar_idw.py --date 2026-02-27 --power 3 --cell-size 500
"""

import argparse
import sys
from pathlib import Path

# Deixa `import app` funcionar rodando o script de qualquer pasta.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import DEFAULT_DATE, DEFAULT_PARAMS, OUTPUTS_DIR  # noqa: E402
from app.services.idw_service import run_idw  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="IDW de precipitação com ArcPy")
    p.add_argument("--date", default=DEFAULT_DATE, help="dia, de 2026-01-01 a 2026-08-31")
    # Padrões escolhidos por validação cruzada (scripts/otimizar_parametros.py).
    p.add_argument("--power", type=float, default=DEFAULT_PARAMS["power"])
    p.add_argument("--cell-size", type=float, default=DEFAULT_PARAMS["cell_size"], help="em metros")
    p.add_argument("--neighbors", type=int, default=DEFAULT_PARAMS["neighbors"])
    args = p.parse_args()

    r = run_idw(args.date, args.power, args.cell_size, args.neighbors)
    v = r["validation"]
    print(
        f"{r['date']} · {r['engine']} · {r['elapsed_seconds']} s\n"
        f"{r['station_count']} estações -> {r['raster']['columns']} × "
        f"{r['raster']['rows']} células de {r['cell_size']:g} m "
        f"({r['raster']['spatial_reference']})\n"
        f"superfície: mín {r['min_precipitation']} · média {r['mean_precipitation']} "
        f"· máx {r['max_precipitation']} mm\n"
        f"leave-one-out: RMSE {v['rmse']} · MAE {v['mae']} · viés {v['bias']} mm\n"
        f"-> {OUTPUTS_DIR / r['run_id'] / r['output']}"
    )


if __name__ == "__main__":
    main()
