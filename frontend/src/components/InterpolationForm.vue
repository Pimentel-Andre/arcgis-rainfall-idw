<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  params: { type: Object, required: true },
  // Valores pré-processados (modo demonstração). Sem eles, o campo é livre.
  options: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['run-idw'])

// Rascunho local: o formulário edita uma cópia e só entrega ao pai no
// "Executar". Assim o mapa não recalcula a cada tecla digitada.
const draft = reactive({ ...props.params })
watch(() => props.params, (atual) => Object.assign(draft, atual), { deep: true })

// Mesmos limites da API (schemas/interpolation.py): o navegador já recusa o
// que o servidor recusaria.
const FIELDS = [
  {
    key: 'power', label: 'Potência', unit: '', min: 0.5, max: 6, step: 0.5,
    help: 'Quanto uma estação próxima pesa mais que uma distante.',
  },
  {
    key: 'cell_size', label: 'Resolução', unit: 'm', min: 250, max: 5000, step: 250,
    help: 'Tamanho da célula do raster.',
  },
  {
    key: 'neighbors', label: 'Vizinhos', unit: '', min: 3, max: 50, step: 1,
    help: 'Estações usadas no cálculo de cada célula.',
  },
]

function submit() {
  emit('run-idw', {
    power: Number(draft.power),
    cell_size: Number(draft.cell_size),
    neighbors: Number(draft.neighbors),
  })
}
</script>

<template>
  <form class="cartao formulario" @submit.prevent="submit">
    <h2>Interpolação</h2>
    <p class="metodo">Método <strong>IDW</strong> · inverso da distância ponderado</p>

    <label v-for="campo in FIELDS" :key="campo.key" class="campo">
      <span class="rotulo">{{ campo.label }}</span>
      <span class="entrada">
        <select v-if="options" v-model.number="draft[campo.key]">
          <option v-for="valor in options[campo.key]" :key="valor" :value="valor">{{ valor }}</option>
        </select>
        <input
          v-else
          v-model.number="draft[campo.key]"
          type="number"
          :min="campo.min"
          :max="campo.max"
          :step="campo.step"
          required
        />
        <span class="unidade">{{ campo.unit }}</span>
      </span>
      <small>{{ campo.help }}</small>
    </label>

    <button type="submit" :disabled="loading || disabled">
      {{ loading ? 'Processando…' : 'Executar IDW' }}
    </button>

    <p v-if="options" class="nota">
      Modo demonstração: cenários processados com ArcPy e congelados em arquivo.
      Para qualquer valor, rode o backend — instruções no README.
    </p>
  </form>
</template>

<style scoped>
.metodo {
  margin: -0.3rem 0 0.8rem;
  font-size: 0.78rem;
  color: var(--tinta-2);
}

.campo {
  display: grid;
  grid-template-columns: 6.5rem 1fr;
  gap: 0.15rem 0.6rem;
  align-items: center;
  margin-bottom: 0.7rem;
}

.rotulo {
  font-size: 0.85rem;
  font-weight: 600;
}

.entrada {
  display: flex;
  gap: 0.35rem;
  align-items: center;
}

.entrada input,
.entrada select {
  width: 6.5rem;
  padding: 0.35rem 0.5rem;
  font: inherit;
  font-size: 0.85rem;
  color: var(--tinta);
  background: #fff;
  border: 1px solid var(--linha);
  border-radius: 6px;
}

.unidade {
  font-size: 0.8rem;
  color: var(--tinta-2);
}

small {
  grid-column: 2;
  font-size: 0.72rem;
  color: var(--tinta-2);
}

button {
  width: 100%;
  margin-top: 0.3rem;
  padding: 0.6rem 1rem;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  color: #fff;
  background: var(--acento);
  border: 1px solid var(--acento);
  border-radius: 999px;
  cursor: pointer;
}

button:hover:not(:disabled) {
  background: var(--acento-escuro);
}

button:disabled {
  background: #9dbbe4;
  border-color: #9dbbe4;
  cursor: progress;
}
</style>
