import { computed, reactive, ref, shallowRef } from 'vue'

import { createApiSource, createDemoSource, detectBackend } from '../services/idwApi.js'

export const DEFAULT_PARAMS = { power: 2, cell_size: 1000, neighbors: 12 }

/**
 * O estado da interpolação num lugar só: de onde vêm os dados, as estações,
 * os parâmetros e o último resultado. Os componentes recebem pedaços disso
 * por props e avisam mudanças por eventos — nenhum deles chama a API.
 */
export function useInterpolation() {
  const source = shallowRef(null)
  const notice = ref('')
  const error = ref('')
  const booting = ref(true)
  const loading = ref(false)

  // shallowRef: listas grandes que só são trocadas inteiras, nunca editadas
  // por dentro. Reatividade profunda custaria caro e não serviria para nada.
  const dataset = shallowRef(null)
  const legend = shallowRef([])
  const stations = shallowRef([])
  const result = shallowRef(null)
  const params = reactive({ ...DEFAULT_PARAMS })

  const mode = computed(() => source.value?.mode ?? null)
  const stationCount = computed(() => stations.value.length)

  // Cada estação com a sua validação ao lado — é o que a tabela e o popup
  // mostram: quanto choveu e quanto o IDW estimaria ali sem ela.
  const stationRows = computed(() => {
    const porId = new Map(
      (result.value?.validation.stations ?? []).map((v) => [v.station_id, v]),
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
      result.value = await source.value.runIdw({ ...params })
    } catch (falha) {
      // O resultado anterior continua no mapa: melhor que uma tela vazia.
      error.value = `Não foi possível executar o IDW: ${falha.message}`
    } finally {
      loading.value = false
    }
  }

  async function start() {
    try {
      const saude = await detectBackend()
      if (saude?.engine.available) {
        source.value = createApiSource(saude)
      } else {
        source.value = await createDemoSource()
        if (saude) {
          notice.value = `A API local está no ar, mas sem ArcPy (${saude.engine.detail}). `
            + 'Com o ArcGIS Pro aberto e logado, reinicie a API para processar ao vivo. '
            + 'Enquanto isso, o mapa mostra os cenários pré-processados.'
        }
      }
      const dados = await source.value.getStations()
      dataset.value = dados.dataset
      legend.value = dados.legend
      stations.value = dados.stations
      await runInterpolation()
    } catch (falha) {
      error.value = `Não foi possível carregar os dados: ${falha.message}`
    } finally {
      booting.value = false
    }
  }

  return {
    source, mode, notice, error, booting, loading,
    dataset, legend, stations, stationRows, stationCount, result, params,
    start, runInterpolation,
  }
}
