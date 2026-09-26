import { computed, reactive, ref, shallowRef } from 'vue'

import {
  createApiSource, createDemoSource, detectBackend, loadMethod,
} from '../services/idwApi.js'

// Só um ponto de partida: os valores de verdade vêm do estudo de validação
// cruzada (idw_parameters.json) assim que ele carrega.
export const DEFAULT_PARAMS = { power: 2, cell_size: 1000, neighbors: 12 }

/**
 * O estado da interpolação num lugar só: de onde vêm os dados, o dia, as
 * estações, os parâmetros e o último resultado. Os componentes recebem
 * pedaços disso por props e avisam mudanças por eventos — nenhum deles chama
 * a API.
 */
export function useInterpolation() {
  const source = shallowRef(null)
  const notice = ref('')
  const error = ref('')
  const booting = ref(true)
  const loading = ref(false)

  // shallowRef: listas que só são trocadas inteiras, nunca editadas por
  // dentro. Reatividade profunda custaria caro e não serviria para nada.
  const dates = shallowRef([])
  const date = ref('')
  const dataset = shallowRef(null)
  const legend = shallowRef([])
  const stations = shallowRef([])
  const result = shallowRef(null)
  const method = shallowRef(null)
  const params = reactive({ ...DEFAULT_PARAMS })

  const mode = computed(() => source.value?.mode ?? null)
  const stationCount = computed(() => stations.value.length)

  // Trocar de dia leva alguns segundos com o ArcPy. Nesse meio-tempo o
  // resultado anterior é de OUTRO dia, e misturá-lo com as estações novas
  // mostraria a validação de um dia sobre a chuva de outro.
  const currentResult = computed(() => (result.value?.date === date.value ? result.value : null))

  // Cada estação com a sua validação ao lado — é o que a tabela e o popup
  // mostram: quanto choveu e quanto o IDW estimaria ali sem ela.
  const stationRows = computed(() => {
    const porId = new Map(
      (currentResult.value?.validation.stations ?? []).map((v) => [v.station_id, v]),
    )
    return stations.value.map((s) => ({
      ...s,
      estimated: porId.get(s.station_id)?.estimated ?? null,
      error: porId.get(s.station_id)?.error ?? null,
    }))
  })

  async function runInterpolation(next = {}) {
    Object.assign(params, next)
    loading.value = true
    error.value = ''
    try {
      result.value = await source.value.runIdw({ date: date.value, ...params })
    } catch (falha) {
      error.value = `Não foi possível executar o IDW: ${falha.message}`
    } finally {
      loading.value = false
    }
  }

  async function selectDate(novo) {
    if (!novo || novo === date.value) return
    error.value = ''
    try {
      const dados = await source.value.getStations(novo)
      date.value = novo
      dataset.value = dados.dataset
      legend.value = dados.legend
      stations.value = dados.stations
    } catch (falha) {
      error.value = `Não foi possível carregar ${novo}: ${falha.message}`
      return
    }
    await runInterpolation()
  }

  async function start() {
    try {
      const saude = await detectBackend()
      if (saude?.engine.available) {
        source.value = createApiSource(saude)
      } else {
        source.value = await createDemoSource()
        if (saude) {
          notice.value = `A API local está no ar, mas o ArcPy não obteve a licença (${saude.engine.detail}). `
            + 'Abra o ArcGIS Pro, entre na sua conta e reinicie a API para rodar o IDW com '
            + 'qualquer parâmetro. Enquanto isso, o mapa mostra resultados já processados.'
        }
      }
      // O estudo é opcional: sem ele, o mapa funciona com os valores clássicos.
      method.value = await loadMethod().catch(() => null)
      if (method.value) {
        const { power, cell_size: cellSize, neighbors } = method.value.chosen
        Object.assign(params, { power, cell_size: cellSize, neighbors })
      }
      // No site estático os parâmetros são os dos arquivos pré-processados.
      if (source.value.fixedParams) Object.assign(params, source.value.fixedParams)

      const lista = await source.value.getDates()
      dates.value = lista.dates
      await selectDate(lista.default)
    } catch (falha) {
      error.value = `Não foi possível carregar os dados: ${falha.message}`
    } finally {
      booting.value = false
    }
  }

  return {
    source, mode, notice, error, booting, loading,
    dates, date, dataset, legend, stations, stationRows, stationCount,
    result: currentResult, params, method,
    start, selectDate, runInterpolation,
  }
}
