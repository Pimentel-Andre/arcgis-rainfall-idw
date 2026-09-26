<script setup>
import { computed } from 'vue'

import { mm } from '../format.js'

const props = defineProps({
  // [{ date, station_count, mean, max }], em ordem de data
  dates: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
// update:modelValue é o par de modelValue: o pai pode usar v-model.
const emit = defineEmits(['update:modelValue'])

const index = computed(() => props.dates.findIndex((d) => d.date === props.modelValue))
const atual = computed(() => props.dates[index.value] ?? null)

// Atalhos para os dias que mais têm o que mostrar: num dia seco a superfície
// sai quase toda da mesma cor.
const maisChuvosos = computed(() => [...props.dates]
  .sort((a, b) => b.mean - a.mean)
  .slice(0, 5))

function ir(i) {
  if (i >= 0 && i < props.dates.length) emit('update:modelValue', props.dates[i].date)
}

function escolher(valor) {
  if (props.dates.some((d) => d.date === valor)) emit('update:modelValue', valor)
}

// "2026-01-20" -> "20/01"
const curta = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
</script>

<template>
  <div class="dia">
    <div class="linha">
      <span class="rotulo">Dia</span>
      <div class="navegacao">
        <button type="button" :disabled="disabled || index <= 0" aria-label="Dia anterior" @click="ir(index - 1)">‹</button>
        <input
          type="date"
          :value="modelValue"
          :min="dates[0]?.date"
          :max="dates.at(-1)?.date"
          :disabled="disabled"
          aria-label="Dia da chuva"
          @change="escolher($event.target.value)"
        />
        <button
          type="button"
          :disabled="disabled || index < 0 || index >= dates.length - 1"
          aria-label="Próximo dia"
          @click="ir(index + 1)"
        >›</button>
      </div>
      <span v-if="atual" class="resumo">
        {{ atual.station_count }} estações · média {{ mm(atual.mean) }} mm · máx {{ mm(atual.max) }} mm
      </span>
    </div>
    <div v-if="dates.length > 1" class="linha atalhos">
      <span class="rotulo">Mais chuvosos</span>
      <button
        v-for="d in maisChuvosos"
        :key="d.date"
        type="button"
        :class="{ ativo: d.date === modelValue }"
        :disabled="disabled"
        @click="escolher(d.date)"
      >{{ curta(d.date) }}</button>
    </div>
  </div>
</template>

<style scoped>
.dia {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--linha);
}

.linha {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.7rem;
  align-items: center;
}

.rotulo {
  min-width: 6.5rem;
  font-size: 0.78rem;
  font-weight: 600;
}

.navegacao {
  display: flex;
  gap: 0.3rem;
  align-items: center;
}

.navegacao input {
  padding: 0.25rem 0.4rem;
  font: inherit;
  font-size: 0.82rem;
  color: var(--tinta);
  background: #fff;
  border: 1px solid var(--linha);
  border-radius: 6px;
}

.navegacao button {
  width: 1.9rem;
  padding: 0.15rem 0;
  font-size: 0.95rem;
  color: var(--tinta);
  background: #fff;
  border: 1px solid var(--linha);
  border-radius: 6px;
  cursor: pointer;
}

button:disabled {
  color: #b5b5b0;
  cursor: default;
}

.resumo {
  font-size: 0.76rem;
  color: var(--tinta-2);
  font-variant-numeric: tabular-nums;
}

.atalhos button {
  padding: 0.15rem 0.6rem;
  font: inherit;
  font-size: 0.76rem;
  color: var(--tinta);
  background: #fff;
  border: 1px solid var(--linha);
  border-radius: 999px;
  cursor: pointer;
}

.atalhos button.ativo {
  color: #fff;
  background: var(--acento);
  border-color: var(--acento);
}
</style>
