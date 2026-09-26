import { describe, expect, it } from 'vitest'

import { dateBR, int, mm, signed } from './format.js'

describe('formatação pt-BR', () => {
  it('uma casa decimal com vírgula', () => {
    expect(mm(47.5)).toBe('47,5')
    expect(mm(null)).toBe('—')
  })

  it('erro com sinal explícito', () => {
    expect(signed(-4)).toBe('−4,0')
    expect(signed(2.26)).toBe('+2,3')
    expect(signed(0.01)).toBe('0,0')
  })

  it('milhar com ponto', () => {
    expect(int(43742)).toBe('43.742')
  })

  it('data UTC não escorrega para o dia anterior', () => {
    expect(dateBR('2026-01-20')).toBe('20 de janeiro de 2026')
  })
})
