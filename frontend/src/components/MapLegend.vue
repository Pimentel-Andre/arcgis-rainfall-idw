<script setup>
defineProps({
  legend: { type: Array, default: () => [] },
  title: { type: String, default: 'Chuva acumulada (mm)' },
})
</script>

<template>
  <div v-if="legend.length" class="legenda" role="group" :aria-label="title">
    <span class="titulo">{{ title }}</span>
    <ol class="escala">
      <li v-for="classe in legend" :key="classe.label">
        <span class="cor" :style="{ background: classe.color }"></span>
        <span class="faixa">{{ classe.label }}</span>
      </li>
    </ol>
    <span class="simbolos">
      <span class="ponto"></span> estação (cor = chuva medida)
      <span class="contorno"></span> limite do estado
    </span>
  </div>
</template>

<style scoped>
.legenda {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.2rem;
  align-items: center;
  padding: 0.7rem 1rem;
  border-top: 1px solid var(--linha);
}

.titulo {
  font-size: 0.78rem;
  font-weight: 600;
}

.escala {
  display: flex;
  flex: 1 1 22rem;
  gap: 2px;
  max-width: 34rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.escala li {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.2rem;
}

.cor {
  display: block;
  height: 0.7rem;
}

.escala li:first-child .cor { border-radius: 4px 0 0 4px; }
.escala li:last-child .cor { border-radius: 0 4px 4px 0; }

.faixa {
  font-size: 0.7rem;
  color: var(--tinta-2);
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.simbolos {
  display: flex;
  gap: 0.35rem;
  align-items: center;
  font-size: 0.72rem;
  color: var(--tinta-2);
}

.ponto {
  width: 0.55rem;
  height: 0.55rem;
  background: var(--acento);
  border: 1.5px solid #fff;
  border-radius: 50%;
  box-shadow: 0 0 2px #0b0b0b;
}

.contorno {
  width: 0.9rem;
  height: 0.6rem;
  margin-left: 0.6rem;
  border: 1px solid #16202b;
}
</style>
