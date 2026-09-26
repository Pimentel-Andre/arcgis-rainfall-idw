<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'

import DaySelector from './components/DaySelector.vue'
import InterpolationForm from './components/InterpolationForm.vue'
import MapLegend from './components/MapLegend.vue'
import MapView from './components/MapView.vue'
import MethodPanel from './components/MethodPanel.vue'
import StationTable from './components/StationTable.vue'
import StatisticsPanel from './components/StatisticsPanel.vue'
import { useInterpolation } from './composables/useInterpolation.js'
import { dateBR } from './format.js'

const {
  source, mode, notice, error, booting, loading,
  dates, date, dataset, legend, stationRows, stationCount, result, params, method,
  start, selectDate, runInterpolation,
} = useInterpolation()

// O que o mapa mostra é estado da tela, não dos dados: fica aqui, e o mapa
// só obedece.
const layers = reactive({ surface: true, stations: true, boundary: true, opacity: 0.85 })
const selectedStationId = ref('')
const mapCard = ref(null)

// A tabela fica abaixo do mapa: escolher uma linha sem trazer o mapa à vista
// levaria a estação para um lugar que a pessoa não está vendo.
function selectFromTable(id) {
  selectedStationId.value = id
  mapCard.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

// Nem toda estação mede todo dia: se a escolhida não existe no dia novo, a
// escolha cai.
watch(stationRows, (rows) => {
  if (selectedStationId.value && !rows.some((r) => r.station_id === selectedStationId.value)) {
    selectedStationId.value = ''
  }
})

const subtitle = computed(() => {
  if (!dataset.value) return 'Carregando as estações…'
  const d = dataset.value
  return `Pluviômetros do ${d.source} no estado do Rio de Janeiro · chuva de ${d.window} `
    + `em ${dateBR(d.date)} (UTC)`
})

onMounted(start)
</script>

<template>
  <div class="app">
    <header class="topo">
      <div>
        <h1>Mapa de precipitação — IDW</h1>
        <p class="sub">{{ subtitle }}</p>
      </div>
      <span v-if="mode" class="modo" :class="mode">
        {{ mode === 'api' ? 'API local · ArcPy' : 'Demonstração estática' }}
      </span>
    </header>

    <p v-if="notice" class="estado alerta">{{ notice }}</p>
    <p v-if="error" class="estado alerta" role="alert">{{ error }}</p>

    <main class="corpo">
      <section ref="mapCard" class="cartao mapa-cartao">
        <DaySelector
          :dates="dates"
          :model-value="date"
          :disabled="loading || booting || !mode"
          @update:model-value="selectDate"
        />
        <MapView
          :stations="stationRows"
          :legend="legend"
          :study-area-url="source?.studyAreaUrl ?? ''"
          :result="result"
          :show-surface="layers.surface"
          :show-stations="layers.stations"
          :show-boundary="layers.boundary"
          :surface-opacity="layers.opacity"
          :selected-station-id="selectedStationId"
          :busy="loading"
          @select-station="selectedStationId = $event"
        />
        <MapLegend :legend="legend" title="Chuva em 24 h (mm)" />
      </section>

      <aside class="painel">
        <InterpolationForm
          :params="params"
          :locked="mode === 'demo'"
          :loading="loading"
          :disabled="booting || !mode"
          @run-idw="runInterpolation"
        />

        <section class="cartao camadas">
          <h2>Camadas</h2>
          <label><input v-model="layers.surface" type="checkbox" /> Superfície IDW</label>
          <label class="opacidade">
            Opacidade
            <input
              v-model.number="layers.opacity"
              type="range"
              min="0.2"
              max="1"
              step="0.05"
              :disabled="!layers.surface"
              aria-label="Opacidade da superfície IDW"
            />
            <span>{{ Math.round(layers.opacity * 100) }}%</span>
          </label>
          <label><input v-model="layers.stations" type="checkbox" /> Estações ({{ stationCount }})</label>
          <label><input v-model="layers.boundary" type="checkbox" /> Limite do estado</label>
        </section>

        <StatisticsPanel :result="result" :dataset="dataset" :station-count="stationCount" />
      </aside>
    </main>

    <StationTable
      :rows="stationRows"
      :selected-id="selectedStationId"
      @select="selectFromTable"
    />

    <MethodPanel v-if="method" :method="method" />

    <footer class="rodape">
      Dados: CEMADEN (pluviômetros) e IBGE (limite estadual) · Processamento: ArcPy
      e Spatial Analyst · Mapa: ArcGIS Maps SDK for JavaScript · Andre Anjos ·
      <a href="https://github.com/Pimentel-Andre/arcgis-rainfall-idw">código-fonte</a>
    </footer>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  max-width: 1440px;
  margin: 0 auto;
  padding: 1rem 1rem 2rem;
}

.topo {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  align-items: flex-end;
  justify-content: space-between;
}

h1 {
  margin: 0;
  font-size: 1.25rem;
}

.sub {
  margin: 0.2rem 0 0;
  font-size: 0.78rem;
  color: var(--tinta-2);
}

.modo {
  padding: 0.25rem 0.7rem;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 999px;
}

.modo.api {
  color: #fff;
  background: var(--acento-escuro);
}

.modo.demo {
  color: var(--acento-escuro);
  background: var(--realce);
}

.estado {
  margin: 0;
  font-size: 0.85rem;
}

.alerta {
  padding: 0.6rem 0.8rem;
  color: var(--alerta);
  background: var(--alerta-fundo);
  border-radius: 8px;
}

.corpo {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 0.9rem;
  align-items: start;
}

.mapa-cartao {
  padding: 0;
  overflow: hidden;
}

.painel {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.camadas label {
  display: flex;
  gap: 0.45rem;
  align-items: center;
  margin-bottom: 0.4rem;
  font-size: 0.84rem;
}

.opacidade {
  padding-left: 1.4rem;
  font-size: 0.78rem !important;
  color: var(--tinta-2);
}

.opacidade input {
  flex: 1;
}

.opacidade span {
  min-width: 2.5rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.rodape {
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--tinta-2);
}

.rodape a {
  color: var(--acento-escuro);
}

@media (max-width: 960px) {
  .corpo {
    grid-template-columns: 1fr;
  }
}
</style>
