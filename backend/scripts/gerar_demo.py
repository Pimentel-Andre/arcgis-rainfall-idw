"""Congela respostas da API em arquivos, para o site estático (GitHub Pages).

O GitHub Pages só serve arquivos: não roda Python, muito menos ArcPy. Então
este script processa todos os dias do arquivo e grava cada resposta
exatamente como a API a devolve. No "modo demonstração", o front-end lê esses
arquivos com o mesmo código que usa para falar com a API.

É a mesma ideia do serie.json do monitor-chuva-rj: o dado viaja congelado do
Python até o navegador. Cada arquivo gerado é uma resposta da API:

    dates.json                  GET  /api/dates (+ os parâmetros do modo demo)
    study_area.geojson          GET  /api/study-area
    stations/<dia>.json         GET  /api/stations?date=<dia>
    idw/<rodada>/result.json    POST /api/interpolations/idw, com o PNG ao lado

Duas fontes, o mesmo resultado:

    python backend/scripts/gerar_demo.py
        chama o pipeline no próprio processo (precisa do ArcPy com licença);
    python backend/scripts/gerar_demo.py --api http://127.0.0.1:8000
        conversa com uma API já no ar — útil quando o ArcPy funciona no
        terminal onde a API roda.

Dias já gerados são pulados, então dá para interromper e continuar depois.
--refazer apaga tudo e começa do zero.
"""

import argparse
import json
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

DESTINO = config.ROOT / "frontend" / "public" / "demo"

# No site estático os parâmetros ficam fixos: 243 dias × uma combinação. Variar
# potência, resolução e vizinhos é trabalho da API local, com o ArcPy.
PADRAO = {"power": 2, "cell_size": 1000, "neighbors": 12}
CAMPOS_ESTACAO = ("station_id", "name", "municipality", "longitude", "latitude", "precip_mm")


class FonteDireta:
    """Chama o pipeline no próprio processo: precisa do ArcPy com licença."""

    def __init__(self):
        # Import tardio: no modo --api este processo nem tenta carregar o ArcPy.
        from app.services import idw_service, symbology, stations
        self.idw_service, self.symbology, self.stations = idw_service, symbology, stations

    def dias(self):
        return {"default": config.DEFAULT_DATE, "dates": self.stations.available_dates()}

    def estacoes(self, dia):
        linhas = self.stations.stations_for_date(dia)
        return {
            "dataset": self.stations.dataset_info(linhas),
            "legend": self.symbology.legend(),
            "stations": [{k: s[k] for k in CAMPOS_ESTACAO} for s in linhas],
        }

    def area(self):
        return config.STUDY_AREA.read_bytes()

    def idw(self, dia):
        s = self.idw_service
        pasta = config.OUTPUTS_DIR / s.run_id(dia, **PADRAO)
        gravado = pasta / "result.json"
        # Reaproveita a rodada que já está em outputs/, se houver.
        if gravado.exists():
            resultado = json.loads(gravado.read_text(encoding="utf-8"))
        else:
            resultado = s.run_idw(dia, **PADRAO)
        return resultado, lambda nome: (pasta / nome).read_bytes()


class FonteApi:
    """Conversa com uma API já no ar, exatamente como o front-end faria."""

    def __init__(self, url):
        self.url = url.rstrip("/")

    def _get(self, caminho):
        with urllib.request.urlopen(f"{self.url}{caminho}", timeout=60) as resposta:
            return resposta.read()

    def dias(self):
        return json.loads(self._get("/api/dates"))

    def estacoes(self, dia):
        return json.loads(self._get(f"/api/stations?date={dia}"))

    def area(self):
        return self._get("/api/study-area")

    def idw(self, dia):
        pedido = urllib.request.Request(
            f"{self.url}/api/interpolations/idw",
            data=json.dumps({"date": dia, **PADRAO}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(pedido, timeout=600) as resposta:
            resultado = json.loads(resposta.read())
        return resultado, lambda nome: self._get(f"/outputs/{resultado['run_id']}/{nome}")


def gravar_json(caminho: Path, dados) -> None:
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Gera os arquivos do modo demonstração")
    p.add_argument("--api", help="URL de uma API no ar (ex.: http://127.0.0.1:8000)")
    p.add_argument("--refazer", action="store_true", help="apaga o demo e gera tudo de novo")
    args = p.parse_args()

    fonte = FonteApi(args.api) if args.api else FonteDireta()

    if args.refazer and DESTINO.exists():
        shutil.rmtree(DESTINO)
    (DESTINO / "stations").mkdir(parents=True, exist_ok=True)
    (DESTINO / "idw").mkdir(exist_ok=True)
    (DESTINO / "study_area.geojson").write_bytes(fonte.area())

    lista = fonte.dias()
    dias, inicio = [], time.perf_counter()
    for n, resumo in enumerate(lista["dates"], start=1):
        dia = resumo["date"]
        gravar_json(DESTINO / "stations" / f"{dia}.json", fonte.estacoes(dia))

        # O nome da rodada é estável (dia + parâmetros): se já está no demo,
        # este dia foi feito numa execução anterior.
        prontos = list((DESTINO / "idw").glob(f"idw_{dia}_*/result.json"))
        if prontos:
            resultado = json.loads(prontos[0].read_text(encoding="utf-8"))
        else:
            resultado, baixar = fonte.idw(dia)
            saida = DESTINO / "idw" / resultado["run_id"]
            saida.mkdir(exist_ok=True)
            arquivos = {"png": resultado["files"]["png"]}
            # O GeoTIFF só vai no dia padrão: 243 rasters pesariam no
            # repositório, e um basta para quem quiser abri-lo no ArcGIS Pro.
            if dia == lista["default"]:
                arquivos["geotiff"] = resultado["files"]["geotiff"]
            for nome in arquivos.values():
                (saida / nome).write_bytes(baixar(nome))
            gravar_json(saida / "result.json", {**resultado, "files": arquivos})
            print(f"  {n:3}/{len(lista['dates'])} {dia} · "
                  f"{time.perf_counter() - inicio:5.0f} s", flush=True)
        dias.append({**resumo, "run_id": resultado["run_id"]})

    gravar_json(DESTINO / "dates.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "default": lista["default"],
        "params": PADRAO,
        "dates": dias,
    })
    tamanho = sum(f.stat().st_size for f in DESTINO.rglob("*") if f.is_file()) / 1024**2
    print(f"{len(dias)} dias em {DESTINO} ({tamanho:.1f} MB)")


if __name__ == "__main__":
    main()
