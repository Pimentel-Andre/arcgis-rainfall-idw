import { describe, expect, it } from 'vitest'

import { findScenario, withFileUrls } from './idwApi.js'

const manifest = {
  scenarios: [
    { run_id: 'idw_p2_c1000_n12', power: 2, cell_size: 1000, neighbors: 12 },
    { run_id: 'idw_p3_c500_n6', power: 3, cell_size: 500, neighbors: 6 },
  ],
}

describe('findScenario', () => {
  it('acha o cenário pelos três parâmetros', () => {
    expect(findScenario(manifest, { power: 3, cell_size: 500, neighbors: 6 }).run_id)
      .toBe('idw_p3_c500_n6')
  })

  it('aceita números que chegaram como texto do formulário', () => {
    expect(findScenario(manifest, { power: '2', cell_size: '1000', neighbors: '12' }).run_id)
      .toBe('idw_p2_c1000_n12')
  })

  it('devolve null para combinação não pré-processada', () => {
    expect(findScenario(manifest, { power: 2, cell_size: 500, neighbors: 12 })).toBeNull()
  })
})

describe('withFileUrls', () => {
  const resultado = { files: { png: 'a.png', geotiff: 'a.tif' } }

  it('monta os endereços a partir da pasta da rodada', () => {
    expect(withFileUrls(resultado, './demo/x/').urls)
      .toEqual({ png: './demo/x/a.png', geotiff: './demo/x/a.tif' })
  })

  it('carimba a imagem para o navegador não reusar a do cache', () => {
    expect(withFileUrls(resultado, '/outputs/x/', 123).urls.png).toBe('/outputs/x/a.png?v=123')
  })

  it('sem GeoTIFF no resultado, não há link de download', () => {
    expect(withFileUrls({ files: { png: 'a.png' } }, './').urls.geotiff).toBeNull()
  })
})
