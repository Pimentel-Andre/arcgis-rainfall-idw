<script setup>
/**
 * O mapa: basemap, superfície IDW (imagem georreferenciada), limite do estado
 * e estações. Recebe tudo por props e só devolve um evento — a estação
 * clicada. Não busca dado nenhum sozinho.
 */
import { onMounted, ref, shallowRef, watch } from 'vue'

// Importar o componente já registra o custom element; os imports são só de
// efeito colateral.
import '@arcgis/map-components/components/arcgis-map'
import '@arcgis/map-components/components/arcgis-zoom'
import '@arcgis/map-components/components/arcgis-home'
import '@arcgis/map-components/components/arcgis-scale-bar'

import Basemap from '@arcgis/core/Basemap.js'
import esriConfig from '@arcgis/core/config.js'
import Graphic from '@arcgis/core/Graphic.js'
import { setLocale } from '@arcgis/core/intl.js'
import FeatureLayer from '@arcgis/core/layers/FeatureLayer.js'
import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer.js'
import MediaLayer from '@arcgis/core/layers/MediaLayer.js'
import OpenStreetMapLayer from '@arcgis/core/layers/OpenStreetMapLayer.js'
import ExtentAndRotationGeoreference from '@arcgis/core/layers/support/ExtentAndRotationGeoreference.js'
import ImageElement from '@arcgis/core/layers/support/ImageElement.js'

const props = defineProps({
  stations: { type: Array, default: () => [] },
  legend: { type: Array, default: () => [] },
  studyAreaUrl: { type: String, default: '' },
  result: { type: Object, default: null },
  showStations: { type: Boolean, default: true },
  showSurface: { type: Boolean, default: true },
  showBoundary: { type: Boolean, default: true },
  surfaceOpacity: { type: Number, default: 0.85 },
  selectedStationId: { type: String, default: '' },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['select-station'])

// A chave vem do frontend/.env.local, que não é versionado. O Vite só expõe
// ao navegador as variáveis com prefixo VITE_.
const apiKey = import.meta.env.VITE_ARCGIS_API_KEY
if (apiKey) esriConfig.apiKey = apiKey
// Popups e escala em português. Na versão 5 é intl.setLocale — a antiga
// propriedade de locale do esriConfig não existe mais.
setLocale('pt-BR')

const mapRef = ref(null)
const homeRef = ref(null)
const view = shallowRef(null)
// Sobe a cada troca das feições das estações: o realce precisa ser refeito.
const stationsVersion = ref(0)

// A superfície é uma imagem ancorada pela extensão. O ArcPy já a entrega em
// Web Mercator, o mesmo sistema do basemap, então ela cai no lugar sem
// distorção — o SDK só estica a imagem entre os cantos.
const surfaceLayer = new MediaLayer({ title: 'Superfície IDW', opacity: props.surfaceOpacity })
let boundaryLayer = null
let stationsLayer = null
let stationsView = null
let highlight = null
let pickedOnMap = ''
// Fila das edições da camada de estações: trocar de dia rápido não pode
// intercalar duas trocas de feições.
let edits = Promise.resolve()

function createBasemap() {
  // Os basemaps "arcgis/*" exigem chave; sem ela o SDK responde 401. O OSM não
  // exige — e em tons de cinza não disputa com a rampa azul da chuva.
  if (apiKey) return 'arcgis/light-gray'
  return new Basemap({
    title: 'OpenStreetMap',
    baseLayers: [
      new OpenStreetMapLayer({ effect: 'grayscale(100%) brightness(108%) contrast(85%)' }),
    ],
  })
}

// Campo numérico formatado exige places E digitSeparator juntos.
const NUMBER_FORMAT = { places: 1, digitSeparator: true }

const STATION_FIELDS = [
  { name: 'oid', type: 'oid' },
  { name: 'station_id', type: 'string', alias: 'Código' },
  { name: 'name', type: 'string', alias: 'Estação' },
  { name: 'municipality', type: 'string', alias: 'Município' },
  { name: 'precip_mm', type: 'double', alias: 'Chuva observada (mm)' },
  { name: 'estimated', type: 'double', alias: 'Estimada sem a estação (mm)' },
  { name: 'error', type: 'double', alias: 'Erro (mm)' },
]

function toGraphic(row) {
  return new Graphic({
    geometry: { type: 'point', longitude: row.longitude, latitude: row.latitude },
    attributes: {
      station_id: row.station_id,
      name: row.name,
      municipality: row.municipality,
      precip_mm: row.precip_mm,
      estimated: row.estimated,
      error: row.error,
    },
  })
}

/**
 * Mesmas classes e cores da superfície, vindas da API. No renderer do ArcGIS
 * os limites valem nas duas pontas e a primeira classe que casa vence:
 * 10 mm exatos caem em "0–10", igual ao PNG gerado pelo backend.
 */
function stationRenderer(legend) {
  return {
    type: 'class-breaks',
    field: 'precip_mm',
    classBreakInfos: legend.map((classe) => ({
      minValue: classe.min,
      maxValue: classe.max ?? Number.MAX_SAFE_INTEGER,
      label: `${classe.label} mm`,
      symbol: {
        type: 'simple-marker',
        size: 8,
        color: classe.color,
        outline: { color: '#ffffff', width: 1.2 },
      },
    })),
  }
}

function createStationsLayer(legend) {
  return new FeatureLayer({
    title: 'Estações do CEMADEN',
    // Nasce vazia: as feições entram e saem por applyEdits, e a camada
    // numera os objectIds sozinha.
    source: [],
    objectIdField: 'oid',
    geometryType: 'point',
    spatialReference: { wkid: 4326 },
    fields: STATION_FIELDS,
    outFields: ['*'],
    renderer: stationRenderer(legend),
    // O IDW passa exatamente pelo valor medido, então o ponto tem a mesma cor
    // da superfície logo abaixo dele. A sombra escura é o que o destaca.
    effect: 'drop-shadow(0px 0px 1.5px #0b0b0b)',
    popupTemplate: {
      title: '{name} — {municipality}',
      content: [{
        type: 'fields',
        fieldInfos: [
          { fieldName: 'precip_mm', label: 'Chuva observada em 24 h (mm)', format: NUMBER_FORMAT },
          { fieldName: 'estimated', label: 'Estimada pelo IDW sem esta estação (mm)', format: NUMBER_FORMAT },
          { fieldName: 'error', label: 'Erro da estimativa (mm)', format: NUMBER_FORMAT },
          { fieldName: 'station_id', label: 'Código CEMADEN' },
        ],
      }],
    },
  })
}

/** Troca todas as feições de uma vez: o conjunto muda com o dia, porque nem toda estação mede todo dia. */
async function replaceStations(rows) {
  const antigas = await stationsLayer.queryObjectIds()
  await stationsLayer.applyEdits({
    deleteFeatures: antigas.map((objectId) => ({ objectId })),
    addFeatures: rows.map(toGraphic),
  })
  stationsVersion.value += 1
}

async function findStation(id) {
  if (!stationsLayer || !id) return null
  const { features } = await stationsLayer.queryFeatures({
    where: `station_id = '${id.replaceAll("'", "''")}'`,
    returnGeometry: true,
    outFields: ['*'],
  })
  return features[0] ?? null
}

// Superfície: cada resultado troca a imagem e a extensão da mesma camada.
watch([view, () => props.result], ([v, result]) => {
  if (!v) return
  // Depois que a camada carrega, a fonte não pode ser trocada inteira: o
  // SDK 5 recusa. Troca-se o que está dentro dela.
  surfaceLayer.source.elements.removeAll()
  // Sem resultado para o dia exibido (ainda calculando), sem superfície:
  // melhor um mapa só com as estações do que a chuva de outro dia.
  if (!result) return
  const e = result.image_extent
  surfaceLayer.source.elements.add(new ImageElement({
    image: result.urls.png,
    georeference: new ExtentAndRotationGeoreference({
      extent: {
        xmin: e.xmin, ymin: e.ymin, xmax: e.xmax, ymax: e.ymax,
        spatialReference: { wkid: e.wkid },
      },
    }),
  }))
})

// Limite do estado: criado uma vez, e usado para enquadrar o mapa.
watch([view, () => props.studyAreaUrl], ([v, url]) => {
  if (!v || !url || boundaryLayer) return
  boundaryLayer = new GeoJSONLayer({
    url,
    title: 'Limite do estado (IBGE)',
    popupEnabled: false,
    visible: props.showBoundary,
    renderer: {
      type: 'simple',
      symbol: {
        type: 'simple-fill',
        color: [0, 0, 0, 0],
        outline: { color: [22, 32, 43, 0.8], width: 1 },
      },
    },
  })
  v.map.add(boundaryLayer, 1)
  boundaryLayer.when(async () => {
    await v.goTo(boundaryLayer.fullExtent.expand(1.04), { animate: false })
    // O botão "início" volta para o estado inteiro, não para o zoom de abertura.
    if (homeRef.value) homeRef.value.viewpoint = v.viewpoint.clone()
  })
})

// Estações: uma camada só; a cada dia ou resultado novo, as feições são
// trocadas de uma vez, na ordem em que as mudanças chegaram.
watch([view, () => props.stations, () => props.legend], ([v, rows, legend]) => {
  if (!v || !legend.length) return
  if (!stationsLayer) {
    stationsLayer = createStationsLayer(legend)
    stationsLayer.visible = props.showStations
    v.map.add(stationsLayer)
    edits = edits.then(async () => { stationsView = await v.whenLayerView(stationsLayer) })
  }
  // O popup aberto mostraria atributos de feições que acabaram de sair.
  if (v.popup?.visible) v.closePopup()
  edits = edits.then(() => replaceStations(rows)).catch(() => {})
})

watch(() => props.showSurface, (visivel) => { surfaceLayer.visible = visivel })
watch(() => props.surfaceOpacity, (opacidade) => { surfaceLayer.opacity = opacidade })
watch(() => props.showBoundary, (visivel) => { if (boundaryLayer) boundaryLayer.visible = visivel })
watch(() => props.showStations, (visivel) => { if (stationsLayer) stationsLayer.visible = visivel })

// Realce da estação escolhida: refeito também quando as feições são trocadas,
// porque o realce antigo apontava para feições que não existem mais.
watch([() => props.selectedStationId, stationsVersion], async ([id]) => {
  highlight?.remove()
  highlight = null
  const feicao = await findStation(id)
  if (feicao && stationsView) highlight = stationsView.highlight(feicao)
})

// Estação escolhida na tabela: leva o mapa até ela e abre o popup. A escolhida
// no mapa não precisa — o popup já abriu onde a pessoa está olhando.
watch(() => props.selectedStationId, async (id) => {
  if (!id || !view.value) return
  if (pickedOnMap === id) {
    pickedOnMap = ''
    return
  }
  await edits
  const feicao = await findStation(id)
  if (!feicao) return
  await view.value.goTo({ target: feicao.geometry, zoom: Math.max(view.value.zoom, 10) }, { duration: 600 })
  view.value.openPopup({ features: [feicao], location: feicao.geometry })
})

onMounted(() => {
  const mapa = mapRef.value
  mapa.basemap = createBasemap()

  // Registrado por addEventListener, e não no template: em custom elements o
  // Vue pode normalizar o nome do evento, e o listener nunca dispararia.
  mapa.addEventListener('arcgisViewReadyChange', (evento) => {
    if (!evento.target.ready || view.value) return
    const v = evento.target.view
    v.map.add(surfaceLayer, 0)

    v.on('click', async (clique) => {
      if (!stationsLayer) return
      const alvo = await v.hitTest(clique, { include: [stationsLayer] })
      // O hitTest devolve só o objectId e o campo do renderer: o SDK não
      // embarca no gráfico de desenho atributos que não precisa para pintar.
      const oid = alvo.results.find((r) => r.graphic?.attributes?.oid)?.graphic.attributes.oid
      let id = ''
      if (oid) {
        const { features } = await stationsLayer.queryFeatures({
          objectIds: [oid], outFields: ['station_id'],
        })
        id = features[0]?.attributes.station_id ?? ''
      }
      pickedOnMap = id
      emit('select-station', id)
    })

    view.value = v
  })
})
</script>

<template>
  <div class="mapa">
    <arcgis-map ref="mapRef" center="-42.7,-22.2" zoom="7">
      <arcgis-zoom slot="top-left"></arcgis-zoom>
      <arcgis-home ref="homeRef" slot="top-left"></arcgis-home>
      <arcgis-scale-bar slot="bottom-left" unit="metric"></arcgis-scale-bar>
    </arcgis-map>
    <p v-if="busy" class="processando" role="status">Calculando a superfície…</p>
  </div>
</template>

<style scoped>
.mapa {
  position: relative;
  height: min(70vh, 660px);
  min-height: 380px;
}

arcgis-map {
  width: 100%;
  height: 100%;
}

.processando {
  position: absolute;
  top: 0.8rem;
  right: 0.8rem;
  margin: 0;
  padding: 0.4rem 0.8rem;
  font-size: 0.8rem;
  color: #fff;
  background: var(--acento-escuro);
  border-radius: 999px;
  box-shadow: 0 2px 8px #00000033;
}
</style>
