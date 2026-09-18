/** UI composition only. The native session/composer/Agent remain owned by DSH. */
import { mainViewSessionId, retainMainView } from '../initial-session.mjs';
export const COMPOSITION_PIN = 'ddefc45fbc7f8e46dd73185e68295696d1297887';
export const CHAT_MIN = 400;
export const CANVAS_MIN = 560;
export const SPLIT_GAP = 8;
// Pinned native rail is 56px. Below this width, expanded navigation overlays
// the single-column canvas instead of consuming its reading width.
export const COMPACT_FRAME_MAX = CANVAS_MIN + 56;

export function compositionGeometry(width, preferred = 440, showChat = true, narrowView = 'canvas') {
  if (!Number.isFinite(width) || width <= 0) return { mode: 'unavailable', canvas: 0, chat: 0 };
  const wide = width >= CHAT_MIN + CANVAS_MIN + SPLIT_GAP;
  if (!showChat || (!wide && narrowView !== 'chat')) return { mode: 'canvas', canvas: width, chat: 0 };
  if (!wide) return { mode: 'chat', canvas: 0, chat: width };
  const chat = Math.min(width - CANVAS_MIN - SPLIT_GAP, Math.max(CHAT_MIN, Math.round(Number.isFinite(preferred) ? preferred : 440)));
  return { mode: 'split', canvas: width - chat - SPLIT_GAP, chat };
}

export function createCockpitComposition({ sessions, layout }) {
  let state = Object.freeze({ open: false, fallback: false, showChat: true, narrowView: 'canvas', width: 440,
    sessionId: null, sessionAvailable: true });
  const listeners = new Set();
  let disposed = false;
  let held;
  let lastCurrent = mainViewSessionId(sessions.list.getSnapshot()) ?? null;
  const update = changes => {
    if (disposed) return;
    const next = { ...state, ...changes };
    if (Object.keys(next).every(key => next[key] === state[key])) return;
    state = Object.freeze(next); for (const listener of [...listeners]) listener();
  };
  const bind = sessionId => {
    if (disposed) return;
    const list = sessions.list.getSnapshot();
    const available = sessionId == null || list.ids.includes(sessionId);
    update({ sessionId: sessionId ?? null, sessionAvailable: available });
    if (available && sessionId != null && mainViewSessionId(list) !== sessionId) {
      held?.release();
      held = retainMainView(sessions, sessionId);
    }
  };
  const off = sessions.list.subscribe(() => {
    const list = sessions.list.getSnapshot();
    const current = mainViewSessionId(list) ?? null, changed = current !== lastCurrent;
    lastCurrent = current;
    if (!state.open) return;
    if (changed && current !== null && current !== state.sessionId) { update({ open: false }); return; }
    if (state.sessionId != null && !list.ids.includes(state.sessionId)) {
      update({ sessionAvailable: false }); return;
    }
    if (state.sessionAvailable && current !== state.sessionId) update({ open: false });
  });
  return {
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot: () => state,
    open(sessionId) {
      if (disposed) return;
      layout.selectPanel(null);
      bind(sessionId ?? mainViewSessionId(sessions.list.getSnapshot()) ?? null);
      update({ open: true, fallback: false });
    },
    bindSession: bind,
    revealChat() { update({ showChat: true, narrowView: 'chat' }); },
    toggleChat() { update({ showChat: !state.showChat, narrowView: 'chat' }); },
    showCanvas() { update({ narrowView: 'canvas' }); },
    toggleSidebar() { if (!disposed) layout.toggleSidebar?.(); },
    setWidth(width) { if (Number.isFinite(width)) update({ width: Math.max(CHAT_MIN, Math.round(width)) }); },
    close() { update({ open: false, fallback: false }); },
    fallback() { if (!disposed) { update({ open: false, fallback: true }); layout.selectPanel('cockpit'); } },
    dispose() { if (disposed) return; disposed = true; held?.release(); off(); listeners.clear(); },
  };
}

/** Scoped native navigation styling; no layout preference or upstream DOM replacement. */
export function leaseCompactNavigation(frame, center) {
  const sidebar = center.previousElementSibling;
  if (!sidebar || sidebar.parentElement !== frame) throw new Error('native sidebar seam unavailable');
  const compact = 'data-sm-cockpit-compact', marker = 'data-sm-cockpit-sidebar';
  if (frame.hasAttribute(compact) || sidebar.hasAttribute(marker)) throw new Error('native navigation already leased');
  const key = '--sm-cockpit-sidebar-width';
  const prior = [frame.style.getPropertyValue(key), frame.style.getPropertyPriority(key)];
  sidebar.setAttribute(marker, 'v1');
  let disposed = false;
  return {
    update(width) {
      if (disposed) return false;
      const narrow = width > 0 && width <= COMPACT_FRAME_MAX;
      if (frame.hasAttribute(compact) !== narrow) frame.toggleAttribute(compact, narrow);
      // Read the native inline preference, not the CSS-overridden 56px track.
      const preferred = Number.parseFloat(frame.style.gridTemplateColumns);
      const value = `${Number.isFinite(preferred) && preferred > 56 ? preferred : 280}px`;
      if (frame.style.getPropertyValue(key) !== value) frame.style.setProperty(key, value);
      return narrow && !frame.hasAttribute('data-sidebar-collapsed');
    },
    dispose() {
      if (disposed) return; disposed = true;
      frame.removeAttribute(compact); sidebar.removeAttribute(marker);
      if (prior[0]) frame.style.setProperty(key, ...prior); else frame.style.removeProperty(key);
    },
  };
}

/** Strict pinned DOM seam. No hashed class selectors, reparenting, cloning or React root. */
export function nativeCompositionTarget(anchor) {
  const layer = anchor.closest('[data-shell-overlay]');
  const frame = layer?.parentElement;
  if (!frame || !frame.querySelector(':scope > [data-rightbar-col]')) return null;
  const scrollers = frame.querySelectorAll('[data-conversation-scroll]');
  if (scrollers.length !== 1) return null;
  const native = scrollers[0].parentElement?.parentElement;
  // The pinned renderer owns two layout-neutral outlet anchors. These are real
  // DOM nodes even though display:contents keeps the native root a flex item.
  const conversationSlot = native?.parentElement, mainSlot = conversationSlot?.parentElement;
  const center = mainSlot?.parentElement;
  if (!native || !['hero', 'settling', 'active'].includes(native.dataset.phase)
    || !native.querySelector('[data-composer-seat]')
    || conversationSlot?.getAttribute('data-slot') !== 'main.conversation' || conversationSlot.style.display !== 'contents'
    || mainSlot?.getAttribute('data-slot') !== 'main' || mainSlot.style.display !== 'contents'
    || center?.parentElement !== frame) return null;
  return { frame, center, native };
}

/** Own only these attributes/properties; preserve native DOM identity and prior values on unload. */
export function leaseNativeComposition(native) {
  const attribute = 'data-sm-cockpit-native';
  if (native.hasAttribute(attribute)) throw new Error('native composition already leased');
  const styleKeys = ['--sm-cockpit-chat-width', '--sm-cockpit-chat-hidden'];
  const priorStyles = styleKeys.map(key => [key, native.style.getPropertyValue(key), native.style.getPropertyPriority(key)]);
  const priorInert = native.inert, priorHidden = native.getAttribute('aria-hidden');
  let disposed = false;
  native.setAttribute(attribute, 'v1');
  return {
    update(width, hidden) {
      if (disposed) return;
      native.style.setProperty(styleKeys[0], `${width}px`);
      native.style.setProperty(styleKeys[1], hidden ? 'hidden' : 'visible');
      native.inert = hidden || Boolean(priorInert);
      if (hidden) native.setAttribute('aria-hidden', 'true');
      else if (priorHidden === null) native.removeAttribute('aria-hidden');
      else native.setAttribute('aria-hidden', priorHidden);
    },
    dispose() {
      if (disposed) return; disposed = true;
      native.removeAttribute(attribute);
      for (const [key, value, priority] of priorStyles) {
        if (value) native.style.setProperty(key, value, priority); else native.style.removeProperty(key);
      }
      native.inert = priorInert;
      if (priorHidden === null) native.removeAttribute('aria-hidden'); else native.setAttribute('aria-hidden', priorHidden);
    },
  };
}
