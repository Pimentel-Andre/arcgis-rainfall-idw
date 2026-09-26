<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import { mm, signed } from '../format.js'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  selectedId: { type: String, default: '' },
})
const emit = defineEmits(['select'])

const COLUMNS = [
  { key: 'name', label: 'Estação', numeric: false },
  { key: 'municipality', label: 'Município', numeric: false },
  { key: 'precip_mm', label: 'Medida (mm)', numeric: true },
  { key: 'estimated', label: 'Estimada sem ela (mm)', numeric: true },
  { key: 'error', label: 'Erro (mm)', numeric: true },
]

const sortKey = ref('precip_mm')
const sortDesc = ref(true)
const query = ref('')

const visibleRows = computed(() => {
  const alvo = query.value.trim().toLocaleLowerCase('pt-BR')
  const filtradas = alvo
    ? props.rows.filter((r) => `${r.name} ${r.municipality} ${r.station_id}`
      .toLocaleLowerCase('pt-BR').includes(alvo))
    : props.rows
  const sinal = sortDesc.value ? -1 : 1
  const chave = sortKey.value
  // Sem estimativa (antes do primeiro IDW) vai para o fim, nos dois sentidos.
  return [...filtradas].sort((a, b) => {
    if (a[chave] == null) return 1
    if (b[chave] == null) return -1
    if (typeof a[chave] === 'string') return sinal * a[chave].localeCompare(b[chave], 'pt-BR')
    return sinal * (a[chave] - b[chave])
  })
})

function sortBy(coluna) {
  if (sortKey.value === coluna.key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortKey.value = coluna.key
    sortDesc.value = coluna.numeric
  }
}

function ariaSort(coluna) {
  if (sortKey.value !== coluna.key) return 'none'
  return sortDesc.value ? 'descending' : 'ascending'
}

// Estação escolhida no mapa: a tabela rola até ela.
watch(() => props.selectedId, async (id) => {
  if (!id) return
  await nextTick()
  document.getElementById(`estacao-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})
</script>

<template>
  <section class="cartao tabela-cartao">
    <header class="cabecalho">
      <h2>Estações ({{ visibleRows.length }})</h2>
      <input
        v-model="query"
        type="search"
        placeholder="Buscar estação ou município"
        aria-label="Buscar estação ou município"
      />
    </header>

    <div class="rolagem">
      <table>
        <thead>
          <tr>
            <th
              v-for="coluna in COLUMNS"
              :key="coluna.key"
              :class="{ numero: coluna.numeric }"
              :aria-sort="ariaSort(coluna)"
            >
              <button type="button" @click="sortBy(coluna)">
                {{ coluna.label }}
                <span v-if="sortKey === coluna.key" aria-hidden="true">{{ sortDesc ? '▾' : '▴' }}</span>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in visibleRows"
            :id="`estacao-${row.station_id}`"
            :key="row.station_id"
            :class="{ escolhida: row.station_id === selectedId }"
            tabindex="0"
            @click="emit('select', row.station_id)"
            @keydown.enter="emit('select', row.station_id)"
          >
            <td>{{ row.name }}</td>
            <td>{{ row.municipality }}</td>
            <td class="numero">{{ mm(row.precip_mm) }}</td>
            <td class="numero">{{ mm(row.estimated) }}</td>
            <td class="numero">{{ signed(row.error) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="nota">
      Clique numa linha para ver a estação no mapa. "Estimada sem ela" é a
      validação leave-one-out: o valor que o IDW daria ali se a estação não
      existisse.
    </p>
  </section>
</template>

<style scoped>
.cabecalho {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.6rem;
}

.cabecalho h2 {
  margin: 0;
}

.cabecalho input {
  width: min(18rem, 100%);
  padding: 0.35rem 0.6rem;
  font: inherit;
  font-size: 0.82rem;
  background: #fff;
  border: 1px solid var(--linha);
  border-radius: 999px;
}

.rolagem {
  max-height: 24rem;
  overflow: auto;
  border: 1px solid var(--linha);
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 0;
  background: var(--superficie);
  border-bottom: 1px solid var(--linha);
}

th button {
  width: 100%;
  padding: 0.5rem 0.6rem;
  font: inherit;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--tinta-2);
  text-align: inherit;
  background: none;
  border: none;
  cursor: pointer;
}

th {
  text-align: left;
}

td {
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid #eeeeea;
}

.numero {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover {
  background: #f3f6fb;
}

tbody tr.escolhida {
  background: var(--realce);
  box-shadow: inset 3px 0 0 var(--acento);
}
</style>
