<script setup>
import { computed } from 'vue'

import { int, mm } from '../format.js'

const props = defineProps({
  // data/idw_parameters.json: o estudo que escolheu os parâmetros
  method: { type: Object, required: true },
})

const escolha = computed(() => props.method.chosen)
const resolucao = computed(() => props.method.resolution)
const potencias = computed(() => props.method.grid.power)
const vizinhos = computed(() => props.method.grid.neighbors)

// Quanto o clássico (potência 2, 12 vizinhos) erra a mais que a escolha.
const excessoClassico = computed(() => 100 * (props.method.classic.rmse / escolha.value.rmse - 1))

// O "vale" do erro: combinações a menos de 1% do melhor. Calculado, e não
// escrito à mão, para continuar certo quando o arquivo ganhar meses.
const vale = computed(() => {
  const limite = escolha.value.rmse * 1.01
  const perto = props.method.table.filter((linha) => linha.rmse <= limite)
  const naPotencia = perto
    .filter((linha) => linha.power === escolha.value.power)
    .map((linha) => linha.neighbors)
  return { total: perto.length, kMin: Math.min(...naPotencia), kMax: Math.max(...naPotencia) }
})

const rmse = computed(() => new Map(
  props.method.table.map((linha) => [`${linha.power}|${linha.neighbors}`, linha.rmse]),
))
const faixa = computed(() => {
  const valores = props.method.table.map((linha) => linha.rmse)
  return { min: Math.min(...valores), max: Math.max(...valores) }
})

// Cinco passos da rampa azul do projeto: claro = erro menor.
const PASSOS = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf']

function celula(p, k) {
  const valor = rmse.value.get(`${p}|${k}`)
  const { min, max } = faixa.value
  const passo = Math.min(PASSOS.length - 1, Math.floor(((valor - min) / (max - min)) * PASSOS.length))
  return {
    valor,
    fundo: PASSOS[passo],
    tinta: passo >= 3 ? '#ffffff' : '#16202b',
    escolhida: p === escolha.value.power && k === escolha.value.neighbors,
    classica: p === 2 && k === 12,
  }
}

const decimal = (valor, casas = 1) => valor.toLocaleString('pt-BR', {
  minimumFractionDigits: casas, maximumFractionDigits: casas,
})
const km = (metros) => decimal(metros / 1000, 1)

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const nomeMes = (aaaamm) => MESES[Number(aaaamm.slice(5, 7)) - 1]
</script>

<template>
  <section id="metodo" class="cartao metodo">
    <h2>Método e confiabilidade</h2>
    <p class="introducao">
      O IDW estima a chuva de cada célula como uma média das estações vizinhas,
      com peso maior para as mais próximas. Os três parâmetros do método não
      foram escolhidos por padrão de software: saem dos próprios dados.
    </p>

    <div class="escolhas">
      <div>
        <span class="rotulo">Potência</span>
        <strong>{{ decimal(escolha.power) }}</strong>
        <p>
          Menor erro na validação cruzada: cada estação, em cada um dos
          {{ method.days }} dias, estimada sem ela mesma
          ({{ int(method.residuals) }} estimativas por combinação testada).
        </p>
      </div>
      <div>
        <span class="rotulo">Vizinhos</span>
        <strong>{{ escolha.neighbors }}</strong>
        <p>
          Mesmo critério, testado junto com a potência em
          {{ potencias.length * vizinhos.length }} combinações.
        </p>
      </div>
      <div>
        <span class="rotulo">Célula</span>
        <strong>{{ km(resolucao.chosen_cell_m) }} km</strong>
        <p>
          No máximo metade da distância média entre estações vizinhas
          ({{ km(resolucao.mean_nearest_neighbor_m) }} km), regra de Hengl (2006).
          Células menores mostrariam detalhe que a rede não mede.
        </p>
      </div>
    </div>

    <h3>Quanto o IDW acerta</h3>
    <p>
      No arquivo inteiro, a estimativa erra em média <b>{{ mm(escolha.mae) }} mm</b>
      (RMSE de {{ mm(escolha.rmse) }} mm, viés de {{ decimal(escolha.bias, 2) }} mm).
      Usar só a média das estações do dia erraria mais: RMSE de
      {{ mm(method.baseline.rmse) }} mm. O IDW elimina
      <b>{{ Math.round(100 * escolha.skill_vs_mean) }}%</b> do erro quadrático
      dessa referência ingênua. Os parâmetros clássicos da literatura (potência 2,
      12 vizinhos) erram {{ decimal(excessoClassico) }}% a mais que os escolhidos.
    </p>

    <div class="tabela-caixa">
      <table class="grade">
        <caption>
          RMSE da validação cruzada (mm), nos {{ method.days }} dias. Linhas:
          potência; colunas: número de vizinhos. Tom mais claro, erro menor.
        </caption>
        <thead>
          <tr>
            <th scope="col">potência</th>
            <th v-for="k in vizinhos" :key="k" scope="col">{{ k }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in potencias" :key="p">
            <th scope="row">{{ decimal(p) }}</th>
            <td
              v-for="k in vizinhos"
              :key="k"
              :class="{ escolhida: celula(p, k).escolhida, classica: celula(p, k).classica }"
              :style="{ background: celula(p, k).fundo, color: celula(p, k).tinta }"
              :title="`potência ${decimal(p)}, ${k} vizinhos: RMSE ${decimal(celula(p, k).valor, 2)} mm`"
            >{{ decimal(celula(p, k).valor, 2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="nota">
      Contorno escuro: a combinação escolhida. Contorno tracejado: a clássica
      (potência 2, 12 vizinhos). O vale é raso: {{ vale.total }} das
      {{ method.table.length }} combinações ficam a menos de 1% do menor erro;
      com potência {{ decimal(escolha.power) }}, qualquer número de vizinhos
      entre {{ vale.kMin }} e {{ vale.kMax }}. A escolha é robusta a esse detalhe.
    </p>

    <h3>Estável ao longo do ano</h3>
    <p>
      Escolhida uma vez para os oito meses, a combinação fica perto da melhor
      de cada mês. Quanto ela erra a mais que a ótima do mês:
    </p>
    <ul class="meses">
      <li v-for="m in method.stability_by_month" :key="m.month">
        <span>{{ nomeMes(m.month) }}</span>
        <b>+{{ decimal(m.penalty_pct) }}%</b>
      </li>
    </ul>

    <h3>Como ler o mapa</h3>
    <ul class="leitura">
      <li>
        <b>O IDW não conhece o relevo.</b> Na Serra do Mar a chuva muda em
        poucos quilômetros, e uma estação do outro lado da serra pesa como uma
        do mesmo lado.
      </li>
      <li>
        <b>Os picos saem suavizados.</b> Uma média ponderada nunca passa do
        maior valor medido ao redor, então a chuva mais forte do dia aparece
        menor entre as estações.
      </li>
      <li>
        <b>Longe das estações, a superfície é extrapolação.</b> No noroeste do
        estado, onde a rede é esparsa, ela repete as estações mais próximas.
        A rede é agrupada (índice de Clark-Evans R = {{ decimal(resolucao.clark_evans_r, 2) }};
        1 seria ao acaso), com mais estações na região metropolitana.
      </li>
      <li>
        <b>O dia é a janela de 24 h em UTC</b>, das 21h do dia anterior às 21h
        no horário de Brasília.
      </li>
      <li>
        <b>Sem leitura não é zero.</b> Estação que não mediu no dia fica de
        fora do cálculo, e pluviômetros travados foram excluídos do arquivo.
      </li>
    </ul>

    <h3>Referências</h3>
    <ol class="referencias">
      <li v-for="ref in method.references" :key="ref">{{ ref }}</li>
    </ol>
  </section>
</template>

<style scoped>
.introducao {
  max-width: 62rem;
  margin: 0 0 1rem;
  font-size: 0.88rem;
  line-height: 1.55;
}

.escolhas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 0.7rem;
}

.escolhas > div {
  padding: 0.75rem 0.9rem;
  background: var(--realce);
  border-radius: 8px;
}

.escolhas .rotulo {
  display: block;
  font-size: 0.72rem;
  color: var(--tinta-2);
}

.escolhas strong {
  font-size: 1.35rem;
  font-variant-numeric: tabular-nums;
}

.escolhas p {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  line-height: 1.45;
  color: var(--tinta-2);
}

.metodo p {
  max-width: 62rem;
  font-size: 0.86rem;
  line-height: 1.55;
}

.tabela-caixa {
  overflow-x: auto;
}

.grade {
  border-collapse: separate;
  border-spacing: 2px;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
}

.grade caption {
  margin-bottom: 0.4rem;
  font-size: 0.76rem;
  color: var(--tinta-2);
  text-align: left;
}

.grade th {
  padding: 0.25rem 0.45rem;
  font-weight: 600;
  color: var(--tinta-2);
}

.grade td {
  min-width: 3.1rem;
  padding: 0.3rem 0.45rem;
  text-align: right;
  border-radius: 3px;
}

.grade td.escolhida {
  font-weight: 700;
  outline: 2.5px solid #0b0b0b;
  outline-offset: -2.5px;
}

.grade td.classica {
  outline: 2px dashed #0b0b0b;
  outline-offset: -2px;
}

.meses {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.meses li {
  display: flex;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  font-size: 0.78rem;
  background: var(--realce);
  border-radius: 999px;
  font-variant-numeric: tabular-nums;
}

.leitura {
  max-width: 62rem;
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.84rem;
  line-height: 1.55;
}

.leitura li + li {
  margin-top: 0.35rem;
}

.referencias {
  margin: 0;
  padding-left: 1.3rem;
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--tinta-2);
}
</style>
