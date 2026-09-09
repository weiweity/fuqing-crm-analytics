/** 12-col clamp + keyboard substitutes. react-grid-layout is not a locked dependency. */

export const GRID = Object.freeze({ cols: 12, minW: 2, minH: 2, maxH: 12, maxY: 240, pointerStep: 48 });

export function clampLayout(layout, patch = {}) {
  const next = { ...layout, ...patch };
  next.w = Math.min(GRID.cols, Math.max(GRID.minW, next.w));
  next.h = Math.min(GRID.maxH, Math.max(GRID.minH, next.h));
  next.x = Math.min(GRID.cols - next.w, Math.max(0, next.x));
  next.y = Math.min(GRID.maxY, Math.max(0, next.y));
  return next;
}

export const LAYOUT_ACTIONS = Object.freeze({
  left: { label: '左移', shortcut: 'Alt+ArrowLeft', patch: { dx: -1 } },
  right: { label: '右移', shortcut: 'Alt+ArrowRight', patch: { dx: 1 } },
  up: { label: '上移', shortcut: 'Alt+ArrowUp', patch: { dy: -1 } },
  down: { label: '下移', shortcut: 'Alt+ArrowDown', patch: { dy: 1 } },
  wider: { label: '加宽', shortcut: 'Alt+Shift+ArrowRight', patch: { dw: 1 } },
  narrower: { label: '减宽', shortcut: 'Alt+Shift+ArrowLeft', patch: { dw: -1 } },
  taller: { label: '加高', shortcut: 'Alt+Shift+ArrowDown', patch: { dh: 1 } },
  shorter: { label: '减高', shortcut: 'Alt+Shift+ArrowUp', patch: { dh: -1 } },
});

export function applyLayoutAction(layout, action) {
  const spec = LAYOUT_ACTIONS[action];
  if (!spec) return layout;
  const { dx = 0, dy = 0, dw = 0, dh = 0 } = spec.patch;
  return clampLayout(layout, {
    x: layout.x + dx,
    y: layout.y + dy,
    w: layout.w + dw,
    h: layout.h + dh,
  });
}

export function matchLayoutKeyboard(event) {
  if (!event?.altKey || event.ctrlKey || event.metaKey) return null;
  const key = event.key;
  if (event.shiftKey) {
    if (key === 'ArrowRight') return 'wider';
    if (key === 'ArrowLeft') return 'narrower';
    if (key === 'ArrowDown') return 'taller';
    if (key === 'ArrowUp') return 'shorter';
    return null;
  }
  if (key === 'ArrowLeft') return 'left';
  if (key === 'ArrowRight') return 'right';
  if (key === 'ArrowUp') return 'up';
  if (key === 'ArrowDown') return 'down';
  return null;
}

export function pointerDelta(startClient, nowClient, origin, axis) {
  const delta = Math.round((nowClient - startClient) / GRID.pointerStep);
  if (axis === 'x') return clampLayout(origin, { x: origin.x + delta });
  if (axis === 'y') return clampLayout(origin, { y: origin.y + delta });
  if (axis === 'w') return clampLayout(origin, { w: origin.w + delta });
  if (axis === 'h') return clampLayout(origin, { h: origin.h + delta });
  return origin;
}
