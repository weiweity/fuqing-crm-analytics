/** One Host Loader source owns the private bridge and discovers the browser entry. */
import type { Context } from '@deepseek-ai/cordis';
import { apply as applyBridge } from './bridge.ts';
import * as competition from './competition-agent/apply.ts';

declare const __COMPETITION_SKILL_PACKAGE__: { manifest: object; contents: Record<string, string> };
export const name = 'analytics-workbench-b0-ui';
export { inject } from './bridge.ts';

export function apply(ctx: Context): void {
  applyBridge(ctx);
  if (process.env.DSH_ANALYTICS_UI_ONLY === '1'
    && process.env.COMPETITION_HTTP_BASE && process.env.COMPETITION_HTTP_TOKEN) {
    ctx.plugin(competition, __COMPETITION_SKILL_PACKAGE__);
  }
}
