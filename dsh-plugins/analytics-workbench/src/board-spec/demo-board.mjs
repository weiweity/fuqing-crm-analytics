/**
 * Seeded demo 看板 for the cockpit main panel.
 *
 * Synthetic ONLY. Every number here is a fixed fixture with a frozen
 * source_result_id; it is not a live query, not a saved SNAPSHOT and not a
 * business conclusion. Titles and the EVIDENCE block keep that boundary
 * visible so an empty cockpit never gets mistaken for real operations data.
 * The 生成驾驶舱 dock still replaces this board with the conversation product.
 */
export const DEMO_BOARD_SPEC = Object.freeze({
  board_id: 'board_demo_channel_gsv_2026_08',
  version: 1,
  session_id: 'sess_demo_synthetic',
  blocks: Object.freeze([
    Object.freeze({
      block_id: 'd1',
      kind: 'METRIC',
      title: '样例 · 直播渠道 GSV',
      metric_ref: 'retail_gsv',
      source_result_id: 'demo_live',
    }),
    Object.freeze({
      block_id: 'd2',
      kind: 'METRIC',
      title: '样例 · 私域渠道 GSV',
      metric_ref: 'retail_gsv',
      source_result_id: 'demo_private',
    }),
    Object.freeze({
      block_id: 'd3',
      kind: 'METRIC',
      title: '样例 · 门店渠道 GSV',
      metric_ref: 'retail_gsv',
      source_result_id: 'demo_store',
    }),
    Object.freeze({
      block_id: 'd4',
      kind: 'LINE',
      title: '直播两期走势',
      metric_ref: 'retail_gsv',
      source_result_id: 'demo_live',
    }),
    Object.freeze({
      block_id: 'd5',
      kind: 'BAR',
      title: '私域两期对比',
      metric_ref: 'retail_gsv',
      source_result_id: 'demo_private',
    }),
    Object.freeze({
      block_id: 'd6',
      kind: 'TABLE',
      title: '门店口径明细',
      metric_ref: 'retail_gsv',
      source_result_id: 'demo_store',
    }),
    Object.freeze({
      block_id: 'd7',
      kind: 'EVIDENCE',
      title: '样例边界',
      chips: Object.freeze(['SYNTHETIC', '非真实经营数据', '固定合成 GSV 快照']),
    }),
    Object.freeze({
      block_id: 'd8',
      kind: 'LINK',
      title: '样例说明 · 渠道看板口径',
      url: 'https://example.invalid/shine-mage/demo/cockpit-board',
      note: '合成样例文档；不接飞书 token，也不代表真实经营结论。',
    }),
  ]),
});

export const DEMO_BOARD_FACTS = Object.freeze({
  demo_live: Object.freeze({ current_gsv: 180, comparison_gsv: 150, difference: 30, change_ratio: 0.2 }),
  demo_private: Object.freeze({ current_gsv: 96, comparison_gsv: 84, difference: 12, change_ratio: 1 / 7 }),
  demo_store: Object.freeze({ current_gsv: 124, comparison_gsv: 126, difference: -2, change_ratio: -2 / 126 }),
});

export const DEMO_BOARD = Object.freeze({ spec: DEMO_BOARD_SPEC, facts: DEMO_BOARD_FACTS });
