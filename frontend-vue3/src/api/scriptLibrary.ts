/**
 * 话术库 API
 */
import http from './http'

// 类型定义
export interface ProductScript {
  name: string
  qa_count: number
  updated_at: string
}

export interface QAItem {
  question: string
  answer: string
  has_answer: boolean
}

export interface ProductDetail {
  qa_list: QAItem[]
  updated_at: string
}

export interface Celebrity {
  name: string
  avatar: string
  title: string
  status: '待开发' | '已上线'
  scripts: Array<{ question: string; answer: string }>
}

export interface ImportResult {
  imported: number
  skipped: number
  total_products: number
}

// 产品话术 API
export const productApi = {
  /** 获取产品列表 */
  list(): Promise<ProductScript[]> {
    return http.get('/api/v1/scripts/products').then(r => r.data.data)
  },

  /** 获取产品详情 */
  get(name: string): Promise<ProductDetail> {
    return http.get(`/api/v1/scripts/products/${encodeURIComponent(name)}`).then(r => r.data.data)
  },

  /** 搜索产品话术 */
  search(keyword: string): Promise<Array<{ product: string } & QAItem>> {
    return http.get('/api/v1/scripts/products/search', { params: { keyword } }).then(r => r.data.data)
  },

  /** 导入产品话术 */
  import(file: File): Promise<ImportResult> {
    const formData = new FormData()
    formData.append('file', file)
    return http.post('/api/v1/scripts/products/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data.data)
  }
}

// 明星专项 API
export const celebrityApi = {
  /** 获取明星列表 */
  list(): Promise<Celebrity[]> {
    return http.get('/api/v1/scripts/celebrities').then(r => r.data.data)
  },

  /** 获取明星详情 */
  get(name: string): Promise<Celebrity> {
    return http.get(`/api/v1/scripts/celebrities/${encodeURIComponent(name)}`).then(r => r.data.data)
  },

  /** 更新明星话术 */
  update(name: string, scripts: Celebrity['scripts']): Promise<void> {
    return http.put(`/api/v1/scripts/celebrities/${encodeURIComponent(name)}/scripts`, scripts)
  }
}
