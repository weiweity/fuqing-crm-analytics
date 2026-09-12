/** Read-only fixture aligned with Figma GENERATE_BOARD example. Not a live query. */
export const BOARD_SPEC_FIXTURE = Object.freeze({
  board_id: 'board_retail_gsv_2026_08',
  version: 1,
  session_id: 'sess_1',
  blocks: Object.freeze([
    Object.freeze({
      block_id: 'b1',
      kind: 'METRIC',
      title: '零售 GSV',
      metric_ref: 'retail_gsv',
      source_result_id: 'r1',
    }),
    Object.freeze({
      block_id: 'b2',
      kind: 'BAR',
      title: '两期对比',
      metric_ref: 'retail_gsv',
      source_result_id: 'r1',
    }),
    Object.freeze({
      block_id: 'b3',
      kind: 'LINE',
      title: '两期连线',
      metric_ref: 'retail_gsv',
      source_result_id: 'r1',
    }),
    Object.freeze({
      block_id: 'b4',
      kind: 'TABLE',
      title: '口径表',
      metric_ref: 'retail_gsv',
      source_result_id: 'r1',
    }),
    Object.freeze({
      block_id: 'b5',
      kind: 'EVIDENCE',
      title: '口径与证据',
      source_result_id: 'r1',
      chips: Object.freeze(['digest', '期间', '筛选']),
    }),
    Object.freeze({
      block_id: 'b6',
      kind: 'html_sandbox',
      title: '渠道结构',
      source_result_id: 'r1',
    }),
    Object.freeze({
      block_id: 'b7',
      kind: 'LINK',
      title: '飞书文档 · 渠道结论',
      url: 'https://example.invalid/feishu/doc/channel',
      note: '这场对话生成的说明文档，已写入驾驶舱。',
    }),
    Object.freeze({
      block_id: 'b8',
      kind: 'LINK',
      title: '多维表 · 首购承接',
      url: 'https://example.invalid/feishu/bitable/first-purchase',
      note: '同源明细表。右侧问数默认基于此表。',
    }),
  ]),
});

export const BOARD_SPEC_FACTS = Object.freeze({
  r1: Object.freeze({
    current_gsv: 400,
    comparison_gsv: 300,
    difference: 100,
    change_ratio: 1 / 3,
  }),
});
