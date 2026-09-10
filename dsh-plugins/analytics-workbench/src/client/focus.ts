import type { KeyboardEvent } from 'react';

/** Keep Tab inside the business overlay; do not replace native focus listeners. */
export function trapDialogTab(event: KeyboardEvent<HTMLDialogElement>): void {
  if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) return;
  const root = event.currentTarget;
  const controls = [...root.querySelectorAll<HTMLElement>(
    'button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href],summary,[tabindex]:not([tabindex="-1"])',
  )].filter(element => element.getClientRects().length > 0);
  if (controls.length === 0) return;
  const first = controls[0];
  const last = controls[controls.length - 1];
  const active = root.ownerDocument.activeElement;
  const target = event.shiftKey && active === first ? last
    : !event.shiftKey && active === last ? first : undefined;
  if (target) {
    event.preventDefault();
    target.focus();
  }
}
