const EXACT: Record<string, string> = {
  凉茶次抛: '爆款次抛',
  经典膜: '爆款面膜',
  医用洁面: '爆款洁面',
}

const SUFFIXES = ['次抛', '面膜', '洁面', '护理液', '美瞳', '面霜', '水乳', '凝胶', '棉片', '护理贴']

export const CATEGORY_NAME_PASSTHROUGH = new Set(['合计', 'TTL', '全部', '全店'])

export function maskCategoryName(name: string | null | undefined): string {
  const raw = (name || '').trim()
  if (!raw || CATEGORY_NAME_PASSTHROUGH.has(raw)) return raw
  if (raw.startsWith('爆款')) return raw
  if (EXACT[raw]) return EXACT[raw]
  const suffix = SUFFIXES.find((item) => raw.includes(item))
  return suffix ? `爆款${suffix}` : '爆款品类'
}

export function categoryDisplayName(row: { name?: string; display_name?: string | null }): string {
  return row.display_name || maskCategoryName(row.name)
}

export function selectableCategoryNames(names: Array<string | null | undefined>): string[] {
  return names.filter((name): name is string => {
    if (!name) return false
    return !CATEGORY_NAME_PASSTHROUGH.has(name)
  })
}
