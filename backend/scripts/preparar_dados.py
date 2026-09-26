"""Prepara os dados de entrada: estações, chuva diária e área de estudo.

As fontes são públicas e o script usa só a biblioteca padrão do Python — não
precisa de ArcPy nem de credenciais:

1. Estações e chuva: o arquivo fechado de 1º de janeiro a 31 de agosto de 2026
   que o monitor-chuva-rj publica (pluviômetros do CEMADEN no estado do RJ).
2. Área de estudo: o limite do estado do RJ, da API de malhas do IBGE.

Saídas, em data/:
    stations.csv             uma linha por estação (código, nome, coordenadas)
    precipitation_daily.csv  uma linha por estação e dia COM leitura
    study_area.geojson       o polígono do estado

Uso:
    python backend/scripts/preparar_dados.py
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

CAMPOS_ESTACOES = ["station_id", "name", "municipality", "longitude", "latitude", "source"]
CAMPOS_CHUVA = ["date", "station_id", "precip_mm"]

PARTICULAS = {"de", "da", "do", "das", "dos", "e"}


def nome_proprio(texto: str) -> str:
    """'SÃO JOÃO DE MERITI' -> 'São João de Meriti'."""
    palavras = texto.strip().lower().split()
    return " ".join(
        p if i and p in PARTICULAS else p.capitalize()
        for i, p in enumerate(palavras)
    )


def estacoes_e_chuva(serie: dict) -> tuple[list[dict], list[dict]]:
    """Catálogo de estações e chuva diária, só com o que é confiável.

    Duas regras, as mesmas do monitor-chuva-rj:
    - dia sem leitura não vira linha: "não mediu" não é "não choveu", e um
      zero ali cavaria um falso buraco seco na superfície interpolada;
    - pluviômetro travado sai inteiro: mediria 0 mm onde choveu.
    """
    estacoes, chuva = [], []
    for estacao in serie["estacoes"]:
        if estacao["suspeita"]:
            continue
        dias = [
            (serie["datas"][i], estacao["acum_24h"][i])
            for i, presente in enumerate(estacao["presenca"])
            if presente == "1"
        ]
        if not dias:
            continue
        estacoes.append({
            "station_id": estacao["codestacao"],
            "name": estacao["nome"],
            "municipality": nome_proprio(estacao["municipio"]),
            "longitude": round(estacao["lon"], 6),
            "latitude": round(estacao["lat"], 6),
            "source": "CEMADEN",
        })
        chuva.extend(
            {"date": dia, "station_id": estacao["codestacao"], "precip_mm": round(valor, 1)}
            for dia, valor in dias
        )
    estacoes.sort(key=lambda e: e["station_id"])
    chuva.sort(key=lambda c: (c["date"], c["station_id"]))
    return estacoes, chuva


def baixar_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resposta:
        corpo = resposta.read()
    # A API do IBGE responde comprimida mesmo sem o cliente pedir, e o urllib
    # não descomprime sozinho. Os dois primeiros bytes denunciam o gzip.
    if corpo[:2] == b"\x1f\x8b":
        corpo = gzip.decompress(corpo)
    return json.loads(corpo)


def gravar_csv(caminho: Path, campos: list[str], linhas: list[dict]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--serie", default=URL_SERIE,
                   help="URL ou caminho local do serie.json do monitor-chuva-rj")
    p.add_argument("--saida", type=Path, default=PASTA_DADOS)
    args = p.parse_args()

    if args.serie.startswith("http"):
        serie = baixar_json(args.serie)
    else:
        serie = json.loads(Path(args.serie).read_text(encoding="utf-8"))

    estacoes, chuva = estacoes_e_chuva(serie)
    args.saida.mkdir(parents=True, exist_ok=True)
    gravar_csv(args.saida / "stations.csv", CAMPOS_ESTACOES, estacoes)
    gravar_csv(args.saida / "precipitation_daily.csv", CAMPOS_CHUVA, chuva)

    limite = baixar_json(URL_LIMITE)
    limite["features"][0]["properties"] = {
        "codarea": "33",
        "nome": "Rio de Janeiro",
        "fonte": "IBGE, API de malhas territoriais v3 (qualidade máxima)",
    }
    (args.saida / "study_area.geojson").write_text(
        json.dumps(limite, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    dias = sorted({c["date"] for c in chuva})
    print(
        f"{len(estacoes)} estações, {len(chuva):,} leituras diárias, "
        f"{len(dias)} dias ({dias[0]} a {dias[-1]}) -> {args.saida}"
    )


if __name__ == "__main__":
    main()
