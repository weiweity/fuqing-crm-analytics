/**
 * Host leave adapter (D41/T22, D44/T25).
 *
 * Verified seam facts against the pinned DSH 0.1.6-alpha.2 (`ddefc45f`):
 *
 *   1. `ctx.layout.selectPanel(id)` is a synchronous setter. It checks the live
 *      `main` registry and then writes `panelInfo.activePanelId`; there is no
 *      pre-navigation approval hook and no way to defer or veto the write.
 *   2. The sidebar panel row (`ui-sidebar` PanelRow) calls that same
 *      `selectPanel` directly from its own onClick. The plugin does not own the
 *      row and cannot interpose on it.
 *   3. `ctx.layout.beginNavigation()` exists and returns an AbortSignal aborted
 *      by the next navigation. It cancels *reads*, not a panel write.
 *
 * So the honest seam is: the plugin cannot veto a native panel write, but it
 * CAN (a) route every plugin-owned entry through the coordinator, and (b) keep
 * the navigation epoch authoritative so a panel write that lands mid-flight
 * cannot make stale reads commit. The un-vetoable native sidebar row is
 * recorded as PARTIAL and handed to P12 — see the lane report.
 *
 * This adapter therefore:
 *   - wraps plugin-owned entries (library navigation, return-to-conversation,
 *     cockpit close, session switch) so they submit a leave intent first;
 *   - observes the host panel selection so an externally-originated switch is
 *     treated as an intent rather than silently unloading the library state.
 */

/** Entry points that own their navigation and can route it through the coordinator. */
export const OWNED_ENTRIES = Object.freeze(['library', 'conversation', 'panel', 'session', 'close']);

export function createHostLeaveAdapter({ coordinator, layout, onPanelChange, readPanelId } = {}) {
  if (!coordinator) throw new Error('宿主离开适配器需要离开协调器。');
  let disposed = false;
  let unsubscribe;
  // The host seam is bound after construction: the plugin creates the adapter
  // before the host controller is reachable.
  let host = layout;

  /** Plugin-owned entries submit an intent instead of calling selectPanel directly. */
  async function request(entry, intent = {}) {
    if (disposed) return 'stayed';
    if (!OWNED_ENTRIES.includes(entry)) throw new Error(`未知的离开入口：${entry}`);
    return coordinator.request({ ...intent, kind: entry });
  }

  /**
   * The panel observer. A selection change the plugin did not initiate still
   * advances the epoch, so reads from the previous panel cannot commit. It
   * cannot block the write — that is the recorded seam limit.
   */
  function observePanel() {
    if (typeof onPanelChange !== 'function') return () => {};
    const stop = onPanelChange(panelId => {
      if (disposed) return;
      const current = typeof readPanelId === 'function' ? readPanelId() : undefined;
      observe(panelId ?? null, current ?? null);
    });
    return typeof stop === 'function' ? stop : () => {};
  }

  /**
   * A panel selection the plugin did not initiate (the sidebar row writes
   * straight to the host setter). The host has already committed that write and
   * the plugin cannot veto it, so this must NOT submit a leave intent — doing so
   * would re-issue a navigation for the panel the user just left. The only
   * correct action is to advance the epoch, so a read issued for the previous
   * panel discards itself instead of publishing over the new one.
   */
  function observe(panelId, previous = null) {
    if (disposed) return 'stayed';
    coordinator.observeExternal?.('panel');
    return 'stayed';
  }

  unsubscribe = observePanel();
  return Object.freeze({
    request,
    observe,
    /** Bind the host controller once it is reachable; returns false if the seam is absent. */
    useLayout(controller) { host = controller; return typeof host?.selectPanel === 'function'; },
    /**
     * Perform the original navigation for a resolved intent. Each entry maps to
     * the host call that entry actually means; a `library` switch keeps the
     * cockpit selected (the asset is opened by the library client), while
     * conversation/panel/session/close all return to the conversation.
     */
    async perform(intent) {
      if (disposed) return;
      if (!host || typeof host.selectPanel !== 'function') {
        throw new Error('宿主导航入口不可用，已留在当前页。');
      }
      // Every owned entry must actually hit the host setter. A library switch
      // stays on the cockpit; a panel switch with an id goes to that panel;
      // conversation / session / close return to the conversation.
      if (intent.kind === 'library') {
        host.selectPanel('cockpit');
        return;
      }
      if (intent.kind === 'panel' && intent.id) {
        host.selectPanel(intent.id);
        return;
      }
      host.selectPanel(null);
    },
    /** True when the host exposes the synchronous setter the adapter relies on. */
    seamAvailable: () => typeof host?.selectPanel === 'function',
    dispose() { disposed = true; unsubscribe?.(); },
  });
}

