export interface NavTab {
  key: string
  label: string
}

export interface NavItem {
  key: string
  label: string
  tabs: NavTab[]
}

export const NAV_ITEMS: NavItem[] = [
  {
    key: '/audience',
    label: '人群看板',
    tabs: [
      { key: '#overview', label: '数据总览' },
      { key: '#channel', label: '渠道概览' },
      { key: '#metrics', label: '30指标对比' },
    ],
  },
  {
    key: '/customer-health',
    label: '老客分析',
    tabs: [
      { key: '#overview', label: '现状概览' },
      { key: '#tiers', label: 'RFM分析' },
      { key: '#r-interval', label: 'R区间分析' },
      { key: '#f-interval', label: 'F区间分析' },
      { key: '#m-interval', label: 'M区间分析' },
      { key: '#repurchase', label: '复购周期' },
    ],
  },
  {
    key: '/category',
    label: '品类看板',
    tabs: [
      { key: '#overview', label: '现状概览' },
      { key: '#association', label: '连带分析' },
      { key: '#product-repurchase', label: '品类复购周期' },
      { key: '#repurchase', label: '品类回购分析' },
      { key: '#flow', label: '品类流转' },
      { key: '#wool', label: '羊毛党分析' },
      { key: '#risk', label: '风险预警' },
    ],
  },
  {
    key: '/market-focus',
    label: '市场对焦',
    tabs: [
      { key: '#product-customer', label: '核心单品新老客' },
      { key: '#store-assets', label: '全店资产' },
      { key: '#product-assets', label: '单品资产' },
      { key: '#other-product-assets', label: '单品资产-其他' },
    ],
  },
  {
    key: '/sampling',
    label: '派样正装转化',
    tabs: [
      { key: '#roi', label: '派样正装转化分析' },
    ],
  },
]