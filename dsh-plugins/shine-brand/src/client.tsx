import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client';
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client';
import { PRODUCT_NAME, watchCompetitionBrandSurface } from './brand-surface.mjs';

export function apply(ctx: Context): void {
  ctx.effect(() => watchCompetitionBrandSurface(), 'shine-brand-surface');
  const slots = ctx.slots;
  if (slots == null || typeof slots.inject !== 'function' || typeof slots.register !== 'function') return;
  slots.inject('sidebar.brand.name', () => slots.register(
    { name: 'sidebar.brand.name', priority: -10 },
    () => <>{PRODUCT_NAME}</>,
  ));
}
