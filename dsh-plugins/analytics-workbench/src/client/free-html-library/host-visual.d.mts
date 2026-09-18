export function relativeLuminance(hex: string): number;
export function contrastRatio(foreground: string, background: string): number;
export function contrastReport(schemeTokens: {
  color: { background: string; ink: string; brandSecondary: string; brandPrimary: string; brandAccent: string; danger: string };
}): { background: string; rows: { role: string; fg: string; bg: string; min: number; bodyForbidden?: boolean; ratio: number; pass: boolean }[] };
export function widthBand(viewportWidth: number): 'phone-375' | 'tablet-768' | 'desktop-1280' | 'desktop-1440';
export function defaultRailCollapsed(viewportWidth: number): boolean;
export function panelPresentation(viewportWidth: number): 'fullscreen' | 'overlay' | 'side';
export function estimateIframeContentWidth(input?: {
  viewportWidth?: number; railOpen?: boolean; panelOpen?: boolean; zoom?: number; padding?: number; rail?: number; panel?: number;
}): {
  viewportWidth: number; band: ReturnType<typeof widthBand>; orientation: string; zoom: number;
  railOpen: boolean; panelOpen: boolean; iframeContentWidth: number; hostOverflow: string;
};
export const WIDTH_MATRIX: readonly ReturnType<typeof estimateIframeContentWidth>[];
export const HOST_VERDICTS: readonly string[];
export function inspectPage(input?: {
  host?: { landmarks?: boolean; nativeChat?: boolean; statusSpineVisible?: boolean; keyboard?: boolean };
  page?: { focusableActions?: boolean; textStatus?: boolean; chartAlternative?: boolean; hostOverflow?: boolean; canvasUnknown?: boolean; repaired?: boolean };
}): {
  hostVerdict: string; pageVerdict: string; hostGaps: string[]; pageGaps: string[];
  blocksGenerate: false; silentRewrite: false; notes: string;
};
export function bindingLabel(state: string, opts?: { partial?: boolean }): string;
