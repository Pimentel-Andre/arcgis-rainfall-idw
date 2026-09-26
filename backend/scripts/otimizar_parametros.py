"""Escolhe os parâmetros do IDW pelos dados, e não pelo valor de fábrica.

Potência e vizinhos: validação cruzada leave-one-out nos 243 dias do arquivo.
Para cada combinação, cada estação de cada dia é estimada sem ela mesma, e os
resíduos de todas as estações em todos os dias entram num RMSE só. Vence o
menor. É o critério da otimização de potência do ArcGIS Geostatistical
Analyst, aplicado ao arquivo inteiro para não ajustar os parâmetros a um dia.

    "The default value is p = 2, although there is no theoretical
    justification to prefer this value over others." — Esri, documentação
    do IDW no ArcGIS Pro

Resolução: Hengl (2006), "Finding the right pixel size". Para dados de ponto,
a célula deve ter no máximo metade da distância média entre cada ponto e o
vizinho mais próximo. Mais fina que isso, o raster mostra detalhe que a rede
de estações não mede.

A conta de IDW é a de app/services/validation.py, a mesma que o teste
test_arcpy_consistency prova ser idêntica à do Spatial Analyst. As estações
são projetadas para SIRGAS 2000 / UTM 23S com o pyproj, como o ArcPy faz.

Saída: data/idw_parameters.json, lido pela API, pelo gerador do site e pela
página de método do site.

Uso (precisa de numpy e pyproj; não precisa de ArcPy):
    python backend/scripts/otimizar_parametros.py
"""

import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyproj import Geod, Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.services.stations import available_dates, stations_for_date  # noqa: E402
from app.services.validation import leave_one_out  # noqa: E402

POTENCIAS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
VIZINHOS = [4, 6, 8, 10, 12, 15, 20, 25, 30]
# Resoluções "redondas" candidatas; vale a maior que respeita a regra de Hengl.
RESOLUCOES = [500, 1000, 1500, 2000, 2500, 3000, 4000, 5000]


def area_do_estudo_km2() -> float:
    """Área geodésica do polígono do estado (anéis externos menos buracos)."""
    geod = Geod(ellps="GRS80")
    area = 0.0
    gj = json.loads(config.STUDY_AREA.read_text(encoding="utf-8"))
    for feature in gj["features"]:
        geom = feature["geometry"]
        poligonos = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poligono in poligonos:
            for i, anel in enumerate(poligono):
                lons, lats = zip(*anel)
                a, _ = geod.polygon_area_perimeter(lons, lats)
                area += abs(a) if i == 0 else -abs(a)
    return area / 1e6


def metricas(soma_q, soma_abs, soma, n) -> dict:
    return {"rmse": (soma_q / n) ** 0.5, "mae": soma_abs / n, "bias": soma / n}


def main() -> None:
    inicio = time.perf_counter()
    projetar = Transformer.from_crs(config.WGS84, config.ANALYSIS_WKID, always_xy=True)

    # Acumuladores: (potência, vizinhos) -> [Σe², Σ|e|, Σe, n], no total e por mês.
    total = defaultdict(lambda: np.zeros(4))
    por_mes = defaultdict(lambda: defaultdict(lambda: np.zeros(4)))
    base_total = np.zeros(4)
    base_mes = defaultdict(lambda: np.zeros(4))
    dist_vizinho, n_por_dia = [], []

    dias = [d["date"] for d in available_dates()]
    for dia in dias:
        linhas = stations_for_date(dia)
        x, y = projetar.transform([r["longitude"] for r in linhas], [r["latitude"] for r in linhas])
        xy = np.column_stack([x, y])
        z = np.array([r["precip_mm"] for r in linhas], dtype=float)
        mes = dia[:7]
        n_por_dia.append(len(z))

        # Densidade da rede no dia: distância de cada estação à mais próxima.
        d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
        np.fill_diagonal(d, np.inf)
        dist_vizinho.append(float(d.min(axis=1).mean()))

        # Referência ingênua: a média das demais estações do dia, sem olhar
        # distância nenhuma. Um IDW que não bate isso não está ajudando.
        erro = (z.sum() - z) / (len(z) - 1) - z
        parcela = np.array([np.sum(erro**2), np.sum(np.abs(erro)), np.sum(erro), erro.size])
        base_total += parcela
        base_mes[mes] += parcela

        for p in POTENCIAS:
            for k in VIZINHOS:
                erro = leave_one_out(xy, z, p, k) - z
                parcela = np.array([np.sum(erro**2), np.sum(np.abs(erro)), np.sum(erro), erro.size])
                total[(p, k)] += parcela
                por_mes[mes][(p, k)] += parcela

    tabela = [
        {"power": p, "neighbors": k, **{m: round(v, 3) for m, v in metricas(*total[(p, k)]).items()}}
        for p in POTENCIAS for k in VIZINHOS
    ]
    melhor = min(tabela, key=lambda linha: linha["rmse"])
    base = metricas(*base_total)
    ganho = 1 - (melhor["rmse"] / base["rmse"]) ** 2

    # Estabilidade: em cada mês, quanto a escolha global perde para a melhor do mês.
    estabilidade = []
    for mes in sorted(por_mes):
        rmse = {pk: metricas(*acc)["rmse"] for pk, acc in por_mes[mes].items()}
        pk_mes = min(rmse, key=rmse.get)
        escolhido = rmse[(melhor["power"], melhor["neighbors"])]
        estabilidade.append({
            "month": mes,
            "best_power": pk_mes[0],
            "best_neighbors": pk_mes[1],
            "best_rmse": round(rmse[pk_mes], 3),
            "chosen_rmse": round(escolhido, 3),
            "penalty_pct": round(100 * (escolhido / rmse[pk_mes] - 1), 2),
            "baseline_rmse": round(metricas(*base_mes[mes])["rmse"], 3),
        })

    # Resolução pela regra de Hengl (2006): p <= h/2, com h a distância média
    # ao vizinho mais próximo. Para comparar: a mesma regra para pontos
    # espalhados ao acaso dá 0,25·√(A/N), porque o h esperado é 0,5·√(A/N)
    # (Clark & Evans, 1954). R < 1 indica rede agrupada.
    area = area_do_estudo_km2()
    n_mediano = float(np.median(n_por_dia))
    h = float(np.median(dist_vizinho))
    h_aleatorio = 0.5 * (area * 1e6 / n_mediano) ** 0.5
    limite = h / 2
    celula = max((r for r in RESOLUCOES if r <= limite), default=RESOLUCOES[0])

    saida = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "days": len(dias),
        "residuals": int(base_total[3]),
        "method": (
            "Validação cruzada leave-one-out em todos os dias; RMSE agregado dos "
            "resíduos de todas as estações. Resolução pela regra de Hengl (2006): "
            "célula de no máximo metade da distância média ao vizinho mais próximo."
        ),
        "grid": {"power": POTENCIAS, "neighbors": VIZINHOS},
        "table": tabela,
        "chosen": {
            "power": melhor["power"],
            "neighbors": melhor["neighbors"],
            "cell_size": celula,
            "rmse": melhor["rmse"],
            "mae": melhor["mae"],
            "bias": melhor["bias"],
            "skill_vs_mean": round(ganho, 3),
        },
        "classic": next(t for t in tabela if t["power"] == 2.0 and t["neighbors"] == 12),
        "baseline": {
            "name": "média das demais estações do dia",
            **{m: round(v, 3) for m, v in base.items()},
        },
        "resolution": {
            "area_km2": round(area),
            "median_stations_per_day": n_mediano,
            "mean_nearest_neighbor_m": round(h),
            "max_cell_m": round(limite),
            "random_pattern_cell_m": round(h_aleatorio / 2),
            "clark_evans_r": round(h / h_aleatorio, 2),
            "chosen_cell_m": celula,
        },
        "stability_by_month": estabilidade,
        "references": [
            "Shepard, D. (1968). A two-dimensional interpolation function for irregularly-spaced "
            "data. Proceedings of the 23rd ACM National Conference, 517–524.",
            "Clark, P. J.; Evans, F. C. (1954). Distance to nearest neighbor as a measure of "
            "spatial relationships in populations. Ecology, 35(4), 445–453.",
            "Hengl, T. (2006). Finding the right pixel size. Computers & Geosciences, 32(9), "
            "1283–1298. doi:10.1016/j.cageo.2005.11.008",
            "Chen, F.-W.; Liu, C.-W. (2012). Estimation of the spatial rainfall distribution "
            "using inverse distance weighting (IDW) in the middle of Taiwan. Paddy and Water "
            "Environment, 10, 209–222. doi:10.1007/s10333-012-0319-1",
            "Li, J.; Heap, A. D. (2014). Spatial interpolation methods applied in the "
            "environmental sciences: A review. Environmental Modelling & Software, 53, 173–189.",
            "Esri. How inverse distance weighted interpolation works. ArcGIS Pro documentation.",
        ],
    }
    config.PARAMETERS_JSON.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{len(dias)} dias, {int(base_total[3]):,} resíduos por combinação "
          f"({time.perf_counter() - inicio:.0f} s)\n")
    print("RMSE (mm) — linhas: potência; colunas: vizinhos")
    print("       " + "".join(f"{k:>7}" for k in VIZINHOS))
    for p in POTENCIAS:
        print(f"{p:>5}  " + "".join(f"{metricas(*total[(p, k)])['rmse']:7.2f}" for k in VIZINHOS))
    c = saida["chosen"]
    print(
        f"\nescolha: potência {c['power']:g}, {c['neighbors']} vizinhos -> "
        f"RMSE {c['rmse']:.2f} · MAE {c['mae']:.2f} · viés {c['bias']:+.2f} mm\n"
        f"clássico (2, 12): RMSE {saida['classic']['rmse']:.2f} mm\n"
        f"média simples das estações: RMSE {base['rmse']:.2f} mm -> o IDW explica "
        f"{100 * ganho:.0f}% do erro quadrático que sobra na média\n"
        f"resolução: h = {h:,.0f} m, limite h/2 = {limite:,.0f} m -> célula de {celula} m "
        f"(pontos ao acaso dariam {h_aleatorio / 2:,.0f} m; R de Clark-Evans = {h / h_aleatorio:.2f})\n"
        f"-> {config.PARAMETERS_JSON}"
    )
    print("\nestabilidade por mês (melhor do mês × escolha global):")
    for e in estabilidade:
        print(f"  {e['month']}: melhor p={e['best_power']:g}, k={e['best_neighbors']:>2} "
              f"RMSE {e['best_rmse']:6.2f} | escolha {e['chosen_rmse']:6.2f} "
              f"(+{e['penalty_pct']:.1f}%) | média simples {e['baseline_rmse']:6.2f}")


if __name__ == "__main__":
    main()
