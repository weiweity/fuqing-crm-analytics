/**
 * Navigation ownership for asset/panel intents (D43/T24).
 *
 * Every intent that may replace what the user is looking at takes an epoch.
 * A read issued under an older epoch is discarded when it settles: it must not
 * publish a page, a list, a message or an error over the newer intent.
 *
 * Save requests are NOT read operations. Their receipt is matched by
 * idempotency key/CAS, and a plain navigation must never cancel or discard it
 * (`fixtures/leave-epoch.fixture.json`: `never_discard_as_read`).
 */

/**
 * The operations a new intent discards, verbatim from the frozen leave-epoch
 * fixture (`epoch.discard`). Kept as a named set so widening it is a visible,
 * reviewable change rather than a scattered condition.
 */
export const EPOCH_DISCARDED_OPERATIONS = Object.freeze(['get', 'list', 'preview']);

/** Operations that must survive a navigation: a receipt is evidence, not a page read. */
export const EPOCH_PRESERVED_OPERATIONS = Object.freeze(['confirm', 'cancel', 'cancel_edit']);

export function isEpochDiscarded(operation) {
  return EPOCH_DISCARDED_OPERATIONS.includes(operation);
}

/** Raised inside the client when a read settles after its intent was superseded. */
export class SupersededRead extends Error {
  constructor(epoch) {
    super('这次读取已被新的导航取代，结果不采用。');
    this.name = 'SupersededRead';
    this.superseded = true;
    this.epoch = epoch;
  }
}

export function isSupersededRead(error) {
  return error?.superseded === true;
}

/**
 * Monotonic intent ownership. `begin` supersedes every earlier read; `isCurrent`
 * is the only commit gate. Nothing here decides *what* navigation happens —
 * that stays with the leave coordinator (D44).
 */
export function createNavigationEpoch() {
  let issued = 0;
  let active = 0;
  let activeKind = 'mount';
  let disposed = false;
  const controllers = new Map();
  const take = epoch => { const controller = controllers.get(epoch); controllers.delete(epoch); return controller; };
  return Object.freeze({
    get current() { return active; },
    /** Advance ownership. The returned ticket owns the read signal for this intent. */
    begin(kind = 'navigation') {
      if (disposed) throw new Error('导航生命周期已结束，不能再提交意图。');
      take(active)?.abort(new SupersededRead(active));
      const epoch = ++issued;
      active = epoch;
      activeKind = kind;
      const controller = new AbortController();
      controllers.set(epoch, controller);
      // The ticket carries its own epoch: `abort()` must report the epoch it
      // was issued for, not whatever intent happens to be current when a late
      // caller gets around to aborting it.
      return Object.freeze({ epoch, kind: activeKind, signal: controller.signal,
        abort: () => controller.abort(new SupersededRead(epoch)) });
    },
    /** The ticket a read issued right now belongs to; null once disposed. */
    ticket() {
      const controller = controllers.get(active);
      return controller ? Object.freeze({ epoch: active, kind: activeKind, signal: controller.signal }) : null;
    },
    /** Commit gate for reads: an older intent may not publish state. */
    isCurrent(epoch) { return !disposed && epoch === active; },
    /** Retire a finished intent without changing ownership. */
    settle(epoch) { take(epoch); },
    dispose() {
      disposed = true;
      for (const [epoch, controller] of controllers) controller.abort(new SupersededRead(epoch));
      controllers.clear();
    },
  });
}
