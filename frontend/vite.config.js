import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const API = 'http://127.0.0.1:8000'

export default defineConfig({
  // Caminhos relativos no build: o GitHub Pages serve o site em
  // /<repositorio>/, e com base absoluta os assets apontariam para a raiz
  // do domínio e dariam 404.
  base: './',
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // <arcgis-map> e companhia são custom elements, não componentes
          // Vue: sem esta regra o compilador os procura, não acha e avisa.
          isCustomElement: (tag) => tag.startsWith('arcgis-') || tag.startsWith('calcite-'),
        },
      },
    }),
  ],
  // Em desenvolvimento o Vite repassa /api e /outputs para o FastAPI. Para o
  // navegador fica tudo na mesma origem, e o backend dispensa CORS.
  server: { proxy: { '/api': API, '/outputs': API } },
  preview: { proxy: { '/api': API, '/outputs': API } },
})
