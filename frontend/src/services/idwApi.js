/**
 * Acesso aos dados do mapa, em dois modos com a MESMA interface:
 *
 * - api: conversa com o backend FastAPI + ArcPy rodando na máquina;
 * - demo: lê respostas da API congeladas em arquivos (public/demo), geradas
 *   pelo próprio backend. É o que roda no GitHub Pages, onde não há servidor.
 *
 * O resto do app não sabe qual dos dois está usando: pede estações e pede o
 * IDW, e recebe o mesmo formato de resposta.
 */

const API = '/api'

async function getJson(url, options) {
  const resposta = await fetch(url, options)
  if (!resposta.ok) {
    let detalhe = `HTTP ${resposta.status}`
    try {
      const corpo = await resposta.json()
      if (corpo?.detail) {
        detalhe = typeof corpo.detail === 'string' ? corpo.detail : JSON.stringify(corpo.detail)
      }
    } catch {
      // resposta sem JSON: fica o código HTTP
    }
    throw new Error(detalhe)
  }
  return resposta.json()
}

/** Acrescenta ao resultado os endereços completos da imagem e do GeoTIFF. */
export function withFileUrls(result, baseUrl, cacheKey = '') {
  const sufixo = cacheKey ? `?v=${cacheKey}` : ''
  return {
    ...result,
    urls: {
      png: `${baseUrl}${result.files.png}${sufixo}`,
      geotiff: result.files.geotiff ? `${baseUrl}${result.files.geotiff}` : null,
    },
  }
}

/** O cenário pré-processado com exatamente estes parâmetros, se existir. */
export function findScenario(manifest, params) {
  return manifest.scenarios.find((s) => s.power === Number(params.power)
    && s.cell_size === Number(params.cell_size)
    && s.neighbors === Number(params.neighbors)) ?? null
}

/** A API local está no ar? No GitHub Pages a resposta é 404, e cai no modo demo. */
export async function detectBackend() {
  try {
    const saude = await getJson(`${API}/health`, { signal: AbortSignal.timeout(3000) })
    return saude.status === 'ok' ? saude : null
  } catch {
    return null
  }
}

export function createApiSource(health) {
  return {
    mode: 'api',
    engine: health.engine,
    studyAreaUrl: `${API}/study-area`,
    getStations: () => getJson(`${API}/stations`),
    async runIdw(params) {
      const resultado = await getJson(`${API}/interpolations/idw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      // Os mesmos parâmetros regravam os mesmos arquivos: o carimbo impede o
      // navegador de reaproveitar a imagem antiga do cache.
      return withFileUrls(resultado, `./outputs/${resultado.run_id}/`, Date.now())
    },
  }
}

export async function createDemoSource(base = './demo/') {
  const manifest = await getJson(`${base}scenarios.json`)
  return {
    mode: 'demo',
    manifest,
    studyAreaUrl: `${base}study_area.geojson`,
    getStations: () => getJson(`${base}stations.json`),
    async runIdw(params) {
      const cenario = findScenario(manifest, params)
      if (!cenario) {
        throw new Error(
          'Essa combinação não foi pré-processada. No modo demonstração, use os '
          + 'valores da lista — ou rode o backend para escolher qualquer valor.',
        )
      }
      const resultado = await getJson(`${base}${cenario.run_id}/result.json`)
      return withFileUrls(resultado, `${base}${cenario.run_id}/`)
    },
  }
}
