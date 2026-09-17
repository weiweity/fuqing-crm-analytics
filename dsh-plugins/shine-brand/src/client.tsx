import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client';
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client';
import { PRODUCT_NAME, watchCompetitionBrandSurface } from './brand-surface.mjs';

/** Required service: ctx.slots throws "without inject" unless this is exported. */
export const inject = ['slots'];

/** No JSX: this package is not in the web ModuleLoader React seed. */
function BrandName() {
  return PRODUCT_NAME;
}

export function apply(ctx: Context): void {
  ctx.effect(() => watchCompetitionBrandSurface(), 'shine-brand-surface');
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register(
    { name: 'sidebar.brand.name', priority: -10 },
    BrandName,
  ));
}
