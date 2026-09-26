import { describe, expect, it } from 'vitest'

import { useInterpolation } from './useInterpolation.js'

describe('useInterpolation sem dados', () => {
  // O cenário do site recém-publicado sem os arquivos do demo: a carga falha
  // e, antes da correção, clicar em "Executar IDW" trocava a mensagem clara
  // por "Cannot read properties of null (reading 'runIdw')".
  it('carga que falha deixa a tela desligada e o motivo à vista', async () => {
    const tela = useInterpolation()
    await tela.start()

    expect(tela.mode.value).toBeNull()
    expect(tela.booting.value).toBe(false)
    expect(tela.error.value).toMatch(/^Não foi possível carregar os dados do mapa/)
  })

  it('executar o IDW sem fonte de dados não apaga o erro de carga', async () => {
    const tela = useInterpolation()
    await tela.start()
    const motivo = tela.error.value

    await tela.runInterpolation({ power: 3 })
    await tela.selectDate('2026-01-20')

    expect(tela.error.value).toBe(motivo)
    expect(tela.loading.value).toBe(false)
    expect(tela.params.power).not.toBe(3)
  })
})
