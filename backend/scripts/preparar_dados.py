"""Prepara os dados de entrada: as estações do dia e a área de estudo.

As duas fontes são públicas e o script usa só a biblioteca padrão do Python —
não precisa de ArcPy nem de credenciais:

1. Estações: o acumulado de 24 h de um dia, tirado da série que o
   monitor-chuva-rj publica (pluviômetros do CEMADEN no estado do RJ).
2. Área de estudo: o limite do estado do RJ, da API de malhas do IBGE.

Uso:
    python backend/scripts/preparar_dados.py
    python backend/scripts/preparar_dados.py --dia 2026-02-27
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data"

URL_SERIE = (
    "https://raw.githubusercontent.com/Pimentel-Andre/monitor-chuva-rj/"
    "main/web/public/data/serie.json"
)
URL_LIMITE = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/33"
    "?formato=application/vnd.geo%2Bjson&qualidade=maxima"
)

# O dia mais chuvoso do arquivo: média de 47,5 mm nas 143 estações com leitura
# e máximo de 182,8 mm. Um dia seco daria uma superfície chapada, sem nada
# para a interpolação mostrar.
DIA_PADRAO = "2026-01-20"

CAMPOS = [
    "station_id", "name", "municipality", "longitude", "latitude",
    "precip_mm", "date", "source",
]

PARTICULAS = {"de", "da", "do", "das", "dos", "e"}


def nome_proprio(texto: str) -> str:
    """'SÃO JOÃO DE MERITI' -> 'São João de Meriti'."""
    palavras = texto.strip().lower().split()
    return " ".join(
        p if i and p in PARTICULAS else p.capitalize()
        for i, p in enumerate(palavras)
    )


def estacoes_do_dia(serie: dict, dia: str) -> list[dict]:
    """Linhas do CSV para um dia da série, só com estações confiáveis."""
    if dia not in serie["datas"]:
        inicio, fim = serie["datas"][0], serie["datas"][-1]
        raise ValueError(f"{dia} fora da série ({inicio} a {fim})")
    i = serie["datas"].index(dia)

    linhas = []
    for estacao in serie["estacoes"]:
        # Sem leitura no dia não é 0 mm. Entrar no IDW como zero pintaria de
        # "seco" o entorno de uma estação que simplesmente não mediu.
        if estacao["presenca"][i] != "1":
            continue
        # Pluviômetro travado, pelo critério do monitor-chuva-rj: mediria
        # 0 mm onde choveu e cavaria um falso buraco seco na superfície.
        if estacao["suspeita"]:
            continue
        linhas.append({
            "station_id": estacao["codestacao"],
            "name": estacao["nome"],
            "municipality": nome_proprio(estacao["municipio"]),
            "longitude": round(estacao["lon"], 6),
            "latitude": round(estacao["lat"], 6),
            "precip_mm": round(estacao["acum_24h"][i], 1),
            "date": dia,
            "source": "CEMADEN",
        })
    return sorted(linhas, key=lambda linha: linha["station_id"])


def baixar_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resposta:
        corpo = resposta.read()
    # A API do IBGE responde comprimida mesmo sem o cliente pedir, e o urllib
    # não descomprime sozinho. Os dois primeiros bytes denunciam o gzip.
    if corpo[:2] == b"\x1f\x8b":
        corpo = gzip.decompress(corpo)
    return json.loads(corpo)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dia", default=DIA_PADRAO, help="dia da série (AAAA-MM-DD)")
    p.add_argument("--serie", default=URL_SERIE,
                   help="URL ou caminho local do serie.json do monitor-chuva-rj")
    p.add_argument("--saida", type=Path, default=PASTA_DADOS)
    args = p.parse_args()

    if args.serie.startswith("http"):
        serie = baixar_json(args.serie)
    else:
        serie = json.loads(Path(args.serie).read_text(encoding="utf-8"))

    linhas = estacoes_do_dia(serie, args.dia)
    args.saida.mkdir(parents=True, exist_ok=True)
    caminho_csv = args.saida / "stations_sample.csv"
    with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)

    limite = baixar_json(URL_LIMITE)
    limite["features"][0]["properties"] = {
        "codarea": "33",
        "nome": "Rio de Janeiro",
        "fonte": "IBGE, API de malhas territoriais v3 (qualidade máxima)",
    }
    caminho_limite = args.saida / "study_area.geojson"
    caminho_limite.write_text(
        json.dumps(limite, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    valores = [linha["precip_mm"] for linha in linhas]
    print(
        f"{len(linhas)} estações em {args.dia} -> {caminho_csv}\n"
        f"chuva de 24 h: mín {min(valores):.1f} · "
        f"média {sum(valores) / len(valores):.1f} · máx {max(valores):.1f} mm\n"
        f"área de estudo -> {caminho_limite}"
    )


if __name__ == "__main__":
    main()
