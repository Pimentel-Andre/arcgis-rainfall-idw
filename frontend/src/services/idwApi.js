/**
 * Acesso aos dados do mapa, em dois modos com a MESMA interface:
 *
 * - api: conversa com o backend FastAPI + ArcPy rodando na máquina;
 * - demo: lê respostas da API congeladas em arquivos (public/demo), geradas
 *   pelo próprio backend. É o que roda no GitHub Pages, onde não há servidor.
 *
 * O resto do app não sabe qual dos dois está usando: pede os dias, as
 * estações de um dia e o IDW, e recebe o mesmo formato de resposta.
 */

const API = '/api'
const PARAM_KEYS = ['power', 'cell_size', 'neighbors']

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

/** Mesma potência, resolução e vizinhos? (números que chegam como texto valem) */
export function sameParams(a, b) {
  return PARAM_KEYS.every((chave) => Number(a[chave]) === Number(b[chave]))
}

/**
 * O estudo que escolheu os parâmetros (validação cruzada nos 243 dias). É um
 * arquivo estático nos dois modos: descreve os dados, não depende da API.
 */
export function loadMethod(base = './demo/') {
  return getJson(`${base}idw_parameters.json`)
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
    fixedParams: null,
    studyAreaUrl: `${API}/study-area`,
    getDates: () => getJson(`${API}/dates`),
    getStations: (date) => getJson(`${API}/stations?date=${date}`),
    async runIdw(params) {
      const resultado = await getJson(`${API}/interpolations/idw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      // O mesmo dia com os mesmos parâmetros regrava os mesmos arquivos: o
      // carimbo impede o navegador de reaproveitar a imagem antiga do cache.
      return withFileUrls(resultado, `./outputs/${resultado.run_id}/`, Date.now())
    },
  }
}

export async function createDemoSource(base = './demo/') {
  const manifest = await getJson(`${base}dates.json`)
  const porDia = new Map(manifest.dates.map((d) => [d.date, d]))
  return {
    mode: 'demo',
    fixedParams: manifest.params,
    studyAreaUrl: `${base}study_area.geojson`,
    getDates: async () => manifest,
    getStations: (date) => getJson(`${base}stations/${date}.json`),
    async runIdw(params) {
      const dia = porDia.get(params.date)
      if (!dia || !sameParams(params, manifest.params)) {
        throw new Error(
          'Esse dia ou combinação de parâmetros não foi pré-processado. Rode o '
          + 'backend para escolher qualquer valor.',
        )
      }
      const resultado = await getJson(`${base}idw/${dia.run_id}/result.json`)
      return withFileUrls(resultado, `${base}idw/${dia.run_id}/`)
    },
  }
}
