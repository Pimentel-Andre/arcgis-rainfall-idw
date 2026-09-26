import { describe, expect, it } from 'vitest'

import { sameParams, withFileUrls } from './idwApi.js'

describe('sameParams', () => {
  const padrao = { power: 2, cell_size: 1000, neighbors: 12 }

  it('compara potência, resolução e vizinhos', () => {
    expect(sameParams({ ...padrao, date: '2026-01-20' }, padrao)).toBe(true)
    expect(sameParams({ ...padrao, power: 3 }, padrao)).toBe(false)
  })

  it('aceita números que chegaram como texto do formulário', () => {
    expect(sameParams({ power: '2', cell_size: '1000', neighbors: '12' }, padrao)).toBe(true)
  })
})

describe('withFileUrls', () => {
  const resultado = { files: { png: 'a.png', geotiff: 'a.tif' } }

  it('monta os endereços a partir da pasta da rodada', () => {
    expect(withFileUrls(resultado, './demo/idw/x/').urls)
      .toEqual({ png: './demo/idw/x/a.png', geotiff: './demo/idw/x/a.tif' })
  })

  it('carimba a imagem para o navegador não reusar a do cache', () => {
    expect(withFileUrls(resultado, './outputs/x/', 123).urls.png).toBe('./outputs/x/a.png?v=123')
  })

  it('sem GeoTIFF no resultado, não há link de download', () => {
    expect(withFileUrls({ files: { png: 'a.png' } }, './').urls.geotiff).toBeNull()
  })
})
