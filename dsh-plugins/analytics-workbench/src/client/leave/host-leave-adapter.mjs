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
      coordinator.request({ kind: 'panel', id: panelId ?? null, external: true, previous: current ?? null })
        .then(result => { if (result === 'prompt') coordinator.stay(); })
        .catch(() => {});
    });
    return typeof stop === 'function' ? stop : () => {};
  }

  unsubscribe = observePanel();
  return Object.freeze({
    request,
    /** Bind the host controller once it is reachable; returns false if the seam is absent. */
    useLayout(controller) { host = controller; return typeof host?.selectPanel === 'function'; },
    /** Perform the original navigation for a resolved intent, exactly once. */
    async perform(intent) {
      if (disposed) return;
      if (intent.kind === 'conversation' || intent.kind === 'panel') host?.selectPanel?.(null);
      else if (intent.kind === 'library' && intent.id) host?.selectPanel?.('cockpit');
    },
    /** True when the host exposes the synchronous setter the adapter relies on. */
    seamAvailable: () => typeof host?.selectPanel === 'function',
    dispose() { disposed = true; unsubscribe?.(); },
  });
}
