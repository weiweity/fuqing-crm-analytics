import client from './index'

// ============================================================
// 模块二：全店资产
// ============================================================

export interface StoreAssetWeek {
  week_label: string
  week_end_date: string
  total: number
  discover: number
  engage: number
  enthuse: number
  perform: number
  initial: number
  numerous: number
  keen: number
  total_change: number
  discover_change: number
  engage_change: number
  enthuse_change: number
  perform_change: number
  initial_change: number
  numerous_change: number
  keen_change: number
}

export interface StoreAssetResponse {
  weeks: StoreAssetWeek[]
  latest_week: string
}

export function fetchStoreAssets(weeks: number = 4, days: number = 0): Promise<StoreAssetResponse> {
  return client.get('/v1/market-focus/store-assets', { params: { weeks, days } })
}

// ============================================================
// 模块三：单品资产
// ============================================================

export interface ProductAssetWeek {
  week_label: string
  week_end_date: string
  total: number
  shallow_grass: number
  deep_grass: number
  initial: number
  repurchase: number
  lian_dai: number
  total_change: number
  shallow_grass_change: number
  deep_grass_change: number
  initial_change: number
  repurchase_change: number
  lian_dai_change: number
}

export interface ProductAssetItem {
  name: string
  spu_classes: string[]   // 与前端 CORE_PRODUCTS.spuc_classes 一致，后端单一数据源
  weeks: ProductAssetWeek[]
}

export interface ProductAssetResponse {
  products: ProductAssetItem[]
  latest_week: string
}

export function fetchProductAssets(weeks: number = 4): Promise<ProductAssetResponse> {
  return client.get('/v1/market-focus/product-assets', { params: { weeks } })
}

export function fetchOtherProductAssets(weeks: number = 4): Promise<ProductAssetResponse> {
  return client.get('/v1/market-focus/other-product-assets', { params: { weeks } })
}

