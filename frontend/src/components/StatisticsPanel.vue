<script setup>
import { computed } from 'vue'

import { int, mm, signed } from '../format.js'

const props = defineProps({
  result: { type: Object, default: null },
  dataset: { type: Object, default: null },
  stationCount: { type: Number, default: 0 },
})

const validation = computed(() => props.result?.validation ?? null)
const crs = computed(() => props.result?.raster.spatial_reference.replaceAll('_', ' ') ?? '')
const seconds = computed(() => (props.result
  ? props.result.elapsed_seconds.toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  : ''))
</script>

<template>
  <section class="cartao estatisticas">
    <h2>Estatísticas</h2>

    <div class="blocos">
      <div class="bloco">
        <span class="rotulo">Estações</span>
        <strong class="numero">{{ stationCount }}</strong>
      </div>
      <div v-if="dataset" class="bloco">
        <span class="rotulo">Chuva medida (mm)</span>
        <span class="trio">
          <span>mín <b>{{ mm(dataset.observed_min) }}</b></span>
          <span>média <b>{{ mm(dataset.observed_mean) }}</b></span>
          <span>máx <b>{{ mm(dataset.observed_max) }}</b></span>
        </span>
      </div>
      <div v-if="result" class="bloco">
        <span class="rotulo">Superfície IDW (mm)</span>
        <span class="trio">
          <span>mín <b>{{ mm(result.min_precipitation) }}</b></span>
          <span>média <b>{{ mm(result.mean_precipitation) }}</b></span>
          <span>máx <b>{{ mm(result.max_precipitation) }}</b></span>
        </span>
      </div>
    </div>

    <template v-if="validation">
      <h3>Validação cruzada (leave-one-out)</h3>
      <dl class="metricas">
        <div><dt>RMSE</dt><dd>{{ mm(validation.rmse) }} mm</dd></div>
        <div><dt>MAE</dt><dd>{{ mm(validation.mae) }} mm</dd></div>
        <div><dt>Viés</dt><dd>{{ signed(validation.bias) }} mm</dd></div>
      </dl>
      <p class="nota">
        Cada estação é estimada pelo IDW sem ela mesma e comparada ao que mediu.
        Viés é a média de estimado − observado: negativo, o método subestima.
      </p>
    </template>

    <template v-if="result">
      <h3>Processamento</h3>
      <ul class="processamento">
        <li>{{ result.engine }} · {{ seconds }} s</li>
        <li>
          {{ result.raster.columns }} × {{ result.raster.rows }} células de
          {{ int(result.cell_size) }} m · {{ int(result.raster.area_km2) }} km²
        </li>
        <li>{{ crs }} (EPSG:{{ result.raster.wkid }})</li>
      </ul>
      <a v-if="result.urls?.geotiff" class="baixar" :href="result.urls.geotiff" download>
        Baixar GeoTIFF
      </a>
    </template>
  </section>
</template>

<style scoped>
.blocos {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.bloco {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.rotulo {
  font-size: 0.72rem;
  color: var(--tinta-2);
}

.numero {
  font-size: 1.4rem;
  line-height: 1.2;
}

.trio {
  display: flex;
  gap: 0.8rem;
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
}

.metricas {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.4rem;
  margin: 0;
}

.metricas div {
  padding: 0.45rem 0.5rem;
  background: var(--realce);
  border-radius: 8px;
}

dt {
  font-size: 0.7rem;
  color: var(--tinta-2);
}

dd {
  margin: 0.1rem 0 0;
  font-size: 0.92rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.processamento {
  margin: 0;
  padding-left: 1rem;
  font-size: 0.78rem;
  line-height: 1.6;
}

.baixar {
  display: inline-block;
  margin-top: 0.7rem;
  padding: 0.35rem 0.8rem;
  font-size: 0.8rem;
  color: var(--acento-escuro);
  border: 1px solid var(--acento);
  border-radius: 999px;
  text-decoration: none;
}

.baixar:hover {
  background: var(--realce);
}
</style>
