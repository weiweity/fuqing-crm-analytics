/** T10 design context for native generate. Not a component whitelist or second Agent. */
export const GENERATE_CONTEXT_SCHEMA = 'free-page-generate-context/v1';

export const SHINE_INVARIANTS = Object.freeze([
  '伸美 AI 增长董事会品牌与可信状态不可跳过',
  '自由 HTML/CSS/JavaScript 是页面资产，不是 BoardSpec 或组件白名单',
  '宿主状态脊的示例/绑定/过期/待保存不能被页面 CSS/JS 删除或改写',
  '数据桥只读授权结果；页面不能持有凭据或执行 SQL',
  'DESIGN.md 与 skill 只影响表达方向；未读到不得声称已遵循',
]);

export const ANTI_TEMPLATE = Object.freeze([
  '不要退化成无意义 KPI 卡片墙、默认仪表盘或装饰渐变图标集',
  '指定首屏视觉锚点、内容节奏和数据呈现方式',
  '图表需要摘要或数据表替代入口，但不因此改成固定组件目录',
]);

export const HOST_CHROME_BOUNDS = Object.freeze({
  maxResidentShells: 2,
  contextPanels: 1,
  statusSpine: ['title', 'binding', 'save', 'primary-action'],
  preview: 'free-html-iframe',
  nativeChat: 'required',
});

const DARK = Object.freeze({
  background: '#09050D', ink: '#FEFCFF', lilac: '#D3C3E8', purple: '#805D9D', signal: '#F2FFDC', danger: '#FF7D91',
});
const LIGHT = Object.freeze({
  background: '#FEFCFF', ink: '#09050D', lilac: '#674482', purple: '#805D9D', signal: '#805D9D', danger: '#AB2944',
});
const FONT = Object.freeze({
  body: "'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
  display: "'Outfit', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  mono: "'SFMono-Regular', 'SF Mono', Menlo, Monaco, Consolas, monospace",
});

export function themeValueCopy(scheme = 'dark') {
  const color = scheme === 'light' ? LIGHT : DARK;
  return Object.freeze({
    scheme,
    note: 'Value copy for the page package. Not a second palette and cannot override the host.',
    color: {
      background: color.background,
      ink: color.ink,
      lilac: color.lilac,
      purpleEmphasisOnly: color.purple,
      signal: color.signal,
      danger: color.danger,
    },
    font: FONT,
  });
}

export function buildGenerateContext({
  prompt,
  designGuide = null,
  skill = null,
  scheme = 'dark',
} = {}) {
  const designLoaded = Boolean(designGuide?.loaded && designGuide.excerpt);
  const skillLoaded = Boolean(skill?.loaded && skill.excerpt);
  return Object.freeze({
    schema_version: GENERATE_CONTEXT_SCHEMA,
    prompt: String(prompt ?? ''),
    invariants: SHINE_INVARIANTS,
    antiTemplate: ANTI_TEMPLATE,
    hostChromeBounds: HOST_CHROME_BOUNDS,
    themeCopy: themeValueCopy(scheme),
    designGuide: designGuide ? {
      kind: designGuide.kind ?? 'design.md',
      loaded: designLoaded,
      excerpt: designLoaded ? designGuide.excerpt : '',
      error: designLoaded ? '' : `${designGuide.error ? `${designGuide.error}；` : ''}未读到 DESIGN.md，不能声称已遵循设计指导`,
    } : { kind: null, loaded: false, excerpt: '', error: '' },
    skill: skill ? {
      loaded: skillLoaded,
      excerpt: skillLoaded ? skill.excerpt : '',
      error: skillLoaded ? '' : `${skill.error ? `${skill.error}；` : ''}未读到 skill，不能声称已遵循 skill`,
    } : { kind: null, loaded: false, excerpt: '', error: '' },
    claimedFollowed: {
      designGuide: designLoaded,
      skill: skillLoaded,
    },
    nativeRuntime: 'dsh-native-agent-only',
  });
}

export const SAMPLE_PROMPTS = Object.freeze([
  '做一张本周收入波动复盘页',
  '把销售明细做成可筛选看板',
  '改已有页面的标题和图表说明',
]);
