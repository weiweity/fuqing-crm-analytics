const EXACT: Record<string, string> = {
  凉茶次抛: '爆款次抛',
  经典膜: '爆款面膜',
  医用洁面: '爆款洁面',
}

const SUFFIXES = ['次抛', '面膜', '洁面', '护理液', '美瞳', '面霜', '水乳', '凝胶', '棉片', '护理贴']

export const CATEGORY_NAME_PASSTHROUGH = new Set([
  '合计',
  'TTL',
  '全部',
  '全店',
  '流失',
  '其他',
  '沉默流失',
  '无',
])

export function maskCategoryName(name: string | null | undefined): string {
  const raw = (name || '').trim()
  if (!raw || CATEGORY_NAME_PASSTHROUGH.has(raw)) return raw
  if (raw.startsWith('爆款')) return raw
  if (EXACT[raw]) return EXACT[raw]
  const suffix = SUFFIXES.find((item) => raw.includes(item))
  return suffix ? `爆款${suffix}` : '爆款品类'
}

function abcSuffix(index: number): string {
  const chars: string[] = []
  let n = index
  while (true) {
    chars.push(String.fromCharCode(65 + (n % 26)))
    n = Math.floor(n / 26) - 1
    if (n < 0) break
  }
  return chars.reverse().join('')
}

export function uniqueDisplayNames(names: Array<string | null | undefined>): Map<string, string> {
  const ordered: string[] = []
  const seen = new Set<string>()
  for (const name of names) {
    const raw = (name || '').trim()
    if (!raw || seen.has(raw)) continue
    seen.add(raw)
    ordered.push(raw)
  }
  const groups = new Map<string, string[]>()
  for (const raw of ordered) {
    const base = maskCategoryName(raw)
    const members = groups.get(base)
    if (members) members.push(raw)
    else groups.set(base, [raw])
  }
  const result = new Map<string, string>()
  for (const [base, members] of groups) {
    const sorted = [...members].sort()
    if (sorted.length === 1) {
      result.set(sorted[0], base)
      continue
    }
    sorted.forEach((raw, index) => {
      result.set(raw, `${base}${abcSuffix(index)}`)
    })
  }
  return result
}

export function categoryDisplayName(row: {
  name?: string
  category_name?: string
  display_name?: string | null
}): string {
  if (row.display_name) return row.display_name
  return maskCategoryName(row.name || row.category_name)
}

export function labeledCategoryOptions(
  names: Array<string | null | undefined>,
  labels?: Record<string, string>,
): Array<{ label: string; value: string }> {
  const raws = names.filter((name): name is string => Boolean(name && !CATEGORY_NAME_PASSTHROUGH.has(name)))
  return raws.map((value) => ({
    label: labels?.[value] || maskCategoryName(value),
    value,
  }))
}

const DEST_COLOR: Record<string, string> = {
  面膜: '#533afd',
  洁面: '#15be53',
  精华: '#8b5cf6',
  凝胶: '#ea2261',
  面霜: '#f59e0b',
  防晒: '#10b981',
}

export function destColor(dest: string): string {
  for (const [key, color] of Object.entries(DEST_COLOR)) {
    if (dest.includes(key)) return color
  }
  return '#64748b'
}

export function destDisplayName(dest: string | null | undefined): string {
  const raw = (dest || '').trim()
  if (!raw) return '—'
  return categoryDisplayName({ name: raw })
}

export function maskDestsInText(
  text: string | null | undefined,
  dests: Array<string | null | undefined>,
): string {
  let next = (text || '').trim()
  if (!next) return '—'
  const ordered = dests
    .filter((dest): dest is string => Boolean(dest))
    .slice()
    .sort((a, b) => b.length - a.length)
  for (const dest of ordered) {
    const label = destDisplayName(dest)
    if (label && next.includes(dest)) next = next.split(dest).join(label)
  }
  return next
}

const CATEGORY_TOKEN_RE = /[^\s，。：:、,（）()]+(?:次抛|面膜|洁面|护理液|美瞳|面霜|水乳|凝胶|棉片|护理贴)/g

export function maskCategoryTokensInText(text: string | null | undefined): string {
  let next = (text || '').trim()
  if (!next) return ''
  for (const [raw, label] of Object.entries(EXACT)) {
    if (next.includes(raw)) next = next.split(raw).join(label)
  }
  return next.replace(CATEGORY_TOKEN_RE, (token) => maskCategoryName(token))
}

export function selectableCategoryNames(names: Array<string | null | undefined>): string[] {
  return names.filter((name): name is string => {
    if (!name) return false
    return !CATEGORY_NAME_PASSTHROUGH.has(name)
  })
}
