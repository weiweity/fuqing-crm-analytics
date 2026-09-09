/** DESIGN.md brand tokens mapped to Ant Design seed names. Not a Vue theme.ts import. */

export const PRODUCT_NAME = '伸美 AI 增长董事会';
export const PRODUCT_NAME_EN = 'SHINE MAGE';
export const PRODUCT_TAGLINE = '把分散经营信号变成可执行洞察';

export const BRAND_ASSET_URLS = Object.freeze({
  logo: '/b0/brand/logo.png',
  mark: '/b0/brand/mark.svg',
  outfit: '/b0/brand/outfit.ttf',
  outfitLicense: '/b0/brand/outfit-ofl.txt',
});

export const BRAND_DIGESTS = Object.freeze({
  logoPng: '21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000',
  markSvg: '1bcd095360e42081429d23972e25f8d4a831a241df565d920c020d27aab8f4a8',
  outfitTtf: 'fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade',
});

export const competitionColor = Object.freeze({
  background: '#09050D',
  backgroundTop: '#0F0B17',
  backgroundMiddle: '#120D1D',
  backgroundBottom: '#0A0711',
  brandPrimary: '#805D9D',
  brandPrimaryHover: '#9877B1',
  brandPrimaryPressed: '#674482',
  brandSecondary: '#D3C3E8',
  brandAccent: '#F2FFDC',
  ink: '#FEFCFF',
  inkOnAccent: '#201426',
  copyStrong: '#ECE5F0',
  copy: '#C4B8CB',
  muted: '#9A8BA4',
  faint: '#6F6078',
  danger: '#FF7D91',
  success: '#10B981',
  warning: '#F59E0B',
});

export const competitionFont = Object.freeze({
  body: "'Alibaba PuHuiTi 3.0', 'Alibaba PuHuiTi', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
  display: "'Outfit', 'Alibaba PuHuiTi 3.0', 'Alibaba PuHuiTi', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  mono: "'SFMono-Regular', 'SF Mono', Menlo, Monaco, Consolas, monospace",
});

export const competitionMaterial = Object.freeze({
  line: 'rgba(211, 195, 232, 0.12)',
  lineStrong: 'rgba(211, 195, 232, 0.24)',
  glass: 'rgba(255, 255, 255, 0.03)',
  overlay: 'rgba(5, 2, 8, 0.72)',
  nav: 'rgba(9, 5, 13, 0.90)',
  navActive: 'rgba(211, 195, 232, 0.12)',
  dangerSoft: 'rgba(255, 125, 145, 0.08)',
  purpleSoft: 'rgba(128, 93, 157, 0.12)',
});

export const competitionMotion = Object.freeze({
  focusBreath: '2400ms ease-in-out',
  fast: '160ms cubic-bezier(0.2, 0.8, 0.2, 1)',
  standard: '240ms cubic-bezier(0.2, 0.8, 0.2, 1)',
});

/** Ant Design 5 seed tokens; algorithms are applied by the React provider. */
export const antdSeedToken = Object.freeze({
  colorPrimary: competitionColor.brandPrimary,
  colorSuccess: competitionColor.brandAccent,
  colorError: competitionColor.danger,
  colorWarning: competitionColor.warning,
  colorInfo: competitionColor.brandSecondary,
  colorText: competitionColor.ink,
  colorTextSecondary: competitionColor.brandSecondary,
  colorTextTertiary: competitionColor.muted,
  colorBgBase: competitionColor.background,
  colorBgLayout: competitionColor.background,
  colorBgContainer: competitionMaterial.glass,
  colorBgElevated: competitionColor.backgroundMiddle,
  colorBorder: competitionMaterial.lineStrong,
  colorSplit: competitionMaterial.line,
  fontFamily: competitionFont.body,
  fontFamilyCode: competitionFont.mono,
  borderRadius: 12,
  controlHeight: 44,
  lineWidth: 1,
});

export const antdTheme = Object.freeze({
  cssVar: { prefix: 'sm', key: 'competition' },
  hashed: true,
  token: antdSeedToken,
});

export const competitionCssVars = Object.freeze({
  '--sm-bg': competitionColor.background,
  '--sm-bg-top': competitionColor.backgroundTop,
  '--sm-purple': competitionColor.brandPrimary,
  '--sm-purple-hover': competitionColor.brandPrimaryHover,
  '--sm-purple-pressed': competitionColor.brandPrimaryPressed,
  '--sm-lilac': competitionColor.brandSecondary,
  '--sm-signal': competitionColor.brandAccent,
  '--sm-ink': competitionColor.ink,
  '--sm-on-accent': competitionColor.inkOnAccent,
  '--sm-copy': competitionColor.copy,
  '--sm-muted': competitionColor.muted,
  '--sm-danger': competitionColor.danger,
  '--sm-line': competitionMaterial.line,
  '--sm-line-strong': competitionMaterial.lineStrong,
  '--sm-glass': competitionMaterial.glass,
  '--sm-overlay': competitionMaterial.overlay,
  '--sm-nav': competitionMaterial.nav,
  '--sm-nav-active': competitionMaterial.navActive,
  '--sm-font-body': competitionFont.body,
  '--sm-font-display': competitionFont.display,
  '--sm-font-mono': competitionFont.mono,
  '--sm-touch': '44px',
  '--sm-logo-width': '177px',
  '--sm-logo-width-compact': '140px',
  '--sm-logo-ratio': '249 / 45',
  '--sm-logo-pad': '8px',
  '--sm-filter-brand-inverse': 'brightness(0) invert(1)',
  '--sm-motion-fast': competitionMotion.fast,
  '--sm-motion-standard': competitionMotion.standard,
  '--sm-motion-focus-breath': competitionMotion.focusBreath,
});

export const competitionTokens = Object.freeze({
  productName: PRODUCT_NAME,
  productNameEn: PRODUCT_NAME_EN,
  tagline: PRODUCT_TAGLINE,
  color: competitionColor,
  font: competitionFont,
  material: competitionMaterial,
  motion: competitionMotion,
  cssVars: competitionCssVars,
  assets: BRAND_ASSET_URLS,
  antd: antdTheme,
  breakpoint: Object.freeze({ phone: 390, tablet: 768, desktop: 1440 }),
});

export type CompetitionColorScheme = 'light' | 'dark';

const lightColor = Object.freeze({
  ...competitionColor,
  background: competitionColor.ink,
  backgroundTop: '#F7F2FA',
  backgroundMiddle: '#F0E8F5',
  backgroundBottom: competitionColor.ink,
  ink: competitionColor.background,
  brandSecondary: '#674482',
  copyStrong: '#33273C',
  copy: '#51415D',
  muted: '#675471',
  faint: '#81708C',
  danger: '#AB2944',
});
const lightMaterial = Object.freeze({
  ...competitionMaterial,
  line: 'rgba(103, 68, 130, 0.16)',
  lineStrong: 'rgba(103, 68, 130, 0.32)',
  glass: 'rgba(128, 93, 157, 0.04)',
  nav: 'rgba(254, 252, 255, 0.96)',
  navActive: 'rgba(128, 93, 157, 0.10)',
});
const lightCompetitionTokens = Object.freeze({
  ...competitionTokens, color: lightColor, material: lightMaterial,
  cssVars: Object.freeze({
    ...competitionCssVars,
    '--sm-bg': lightColor.background, '--sm-bg-top': lightColor.backgroundTop,
    '--sm-ink': lightColor.ink, '--sm-copy': lightColor.copy, '--sm-muted': lightColor.muted,
    '--sm-lilac': lightColor.brandSecondary, '--sm-danger': lightColor.danger,
    '--sm-signal': competitionColor.brandPrimary,
    '--sm-line': lightMaterial.line, '--sm-line-strong': lightMaterial.lineStrong,
    '--sm-glass': lightMaterial.glass, '--sm-nav': lightMaterial.nav, '--sm-nav-active': lightMaterial.navActive,
    '--sm-filter-brand-inverse': 'none',
  }),
  antd: Object.freeze({
    ...antdTheme, cssVar: { prefix: 'sm', key: 'competition-light' },
    token: Object.freeze({
      ...antdSeedToken, colorText: lightColor.ink, colorTextSecondary: lightColor.copy,
      colorTextTertiary: lightColor.muted, colorBgBase: lightColor.background,
      colorBgLayout: lightColor.background, colorBgContainer: lightColor.background,
      colorBgElevated: lightColor.background, colorBorder: lightMaterial.lineStrong,
      colorSplit: lightMaterial.line, colorError: lightColor.danger,
    }),
  }),
});

export function competitionThemeFor(scheme: CompetitionColorScheme) {
  return scheme === 'light' ? lightCompetitionTokens : competitionTokens;
}

/** Owned override layer for DSH's official theme presenter. Never writes preferences. */
export const nativeBrandTokens = Object.freeze(Object.fromEntries(Object.entries({
  '--dsw-alias-bg-base': [lightColor.background, competitionColor.background],
  '--dsw-alias-bg-layer-1': [lightColor.backgroundTop, competitionColor.backgroundTop],
  '--dsw-alias-bg-layer-2': [lightColor.backgroundMiddle, competitionColor.backgroundMiddle],
  '--dsw-alias-bg-overlay': [lightColor.background, competitionColor.backgroundMiddle],
  '--dsw-alias-border-l1': [lightMaterial.line, competitionMaterial.line],
  '--dsw-alias-border-l2': [lightMaterial.lineStrong, competitionMaterial.lineStrong],
  '--dsw-alias-brand-primary': [competitionColor.brandPrimary, competitionColor.brandPrimary],
  '--dsw-alias-label-primary': [lightColor.ink, competitionColor.ink],
  '--dsw-alias-label-secondary': [lightColor.copy, competitionColor.copy],
  '--dsw-alias-state-error-primary': [lightColor.danger, competitionColor.danger],
  '--dsw-specific-sidebar-fill': [lightColor.backgroundTop, competitionColor.backgroundTop],
  '--dsw-font-family': [competitionFont.body, competitionFont.body],
  '--ds-font-family-code': [competitionFont.mono, competitionFont.mono],
  '--sm-native-logo-filter': ['none', 'brightness(0) invert(1)'],
}).map(([name, [light, dark]]) => [name, { light, dark }])));

export type CompetitionTokens = ReturnType<typeof competitionThemeFor>;
export type AntdSeedToken = typeof antdSeedToken;
export type AntdThemeConfig = typeof antdTheme;
