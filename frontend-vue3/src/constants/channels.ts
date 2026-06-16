/**
 * 渠道常量 - 统一定义，避免多处重复
 *
 * 9 个真实渠道: 货架/达播/直播/淘客/微博/U先派样/百补派样/赠品&0.01/其他
 * 2 个虚拟渠道: 全店(聚合)/纯派样(聚合)
 */

/** 9 个真实业务渠道（规范排序） */
export const ACTIVE_CHANNELS = [
  '货架', '达播', '直播', '淘客', '微博',
  'U先派样', '百补派样', '赠品&0.01', '其他',
] as const

/** 渠道排序（看板图表用，与 ACTIVE_CHANNELS 同序） */
export const CHANNEL_ORDER: readonly string[] = ACTIVE_CHANNELS

/** 低价渠道列表，用于"剔除低价"筛选 */
export const LOW_PRICE_CHANNELS = ['U先派样', '百补派样', '赠品&0.01', '其他']

/** 健康分看板渠道（全店 + 5 个核心渠道） */
export const HEALTH_SCORE_CHANNELS = ['全店', '货架', '达播', '直播', '淘客'] as const

/** 全局筛选栏渠道选项（含虚拟渠道） */
export const ALL_CHANNEL_OPTIONS = [
  { label: '全店', value: '全店' },
  { label: '纯派样', value: '纯派样' },
  ...ACTIVE_CHANNELS.map(ch => ({ label: ch, value: ch })),
]
