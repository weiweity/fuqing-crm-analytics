import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client';
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client';
import type {} from '@deepseek-ai/dsh-client-ui-slots/client';
import { PRODUCT_NAME, watchCompetitionBrandSurface } from './brand-surface.mjs';

export function apply(ctx: Context): void {
  ctx.effect(() => watchCompetitionBrandSurface(), 'shine-brand-surface');
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register(
    { name: 'sidebar.brand.name', priority: -10 },
    () => <>{PRODUCT_NAME}</>,
  ));
}
