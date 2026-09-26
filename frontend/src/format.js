// Números no padrão brasileiro: vírgula decimal e ponto de milhar.
const umaCasa = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })

const vazio = (valor) => valor == null || Number.isNaN(valor)

/** 47.5 -> "47,5" */
export function mm(valor) {
  return vazio(valor) ? '—' : umaCasa.format(valor)
}

/** -4 -> "−4,0", 2 -> "+2,0". O sinal é o que diz se o IDW errou para cima ou para baixo. */
export function signed(valor) {
  if (vazio(valor)) return '—'
  const texto = umaCasa.format(Math.abs(valor))
  if (texto === '0,0') return texto
  return `${valor > 0 ? '+' : '−'}${texto}`
}

/** 43742 -> "43.742" */
export function int(valor) {
  return vazio(valor) ? '—' : inteiro.format(valor)
}

/** "2026-01-20" -> "20 de janeiro de 2026" (a data é UTC; sem fixar o fuso, o Brasil veria o dia 19). */
export function dateBR(iso) {
  if (!iso) return ''
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('pt-BR', {
    timeZone: 'UTC', day: 'numeric', month: 'long', year: 'numeric',
  })
}
