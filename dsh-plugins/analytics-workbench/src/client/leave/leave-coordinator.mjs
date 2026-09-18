/**
 * Single leave coordinator (D44/T25).
 *
 * Every leaving entry point — library asset switch, return-to-conversation, the
 * DSH global panel, a session switch and closing the cockpit — submits one
 * leave intent here. The coordinator alone reads `hasUnsavedChanges`, runs the
 * three choices, advances the navigation epoch and performs the original
 * navigation. Composition keeps display and session binding only.
 *
 * Dependencies are injected so the transaction can be tested without a host:
 *   snapshot()            - current library state (dirty predicate input)
 *   beginEpoch(kind)      - advance navigation ownership, returns a ticket
 *   save()                - save the pending draft, returns {ok, reason}
 *   discard()             - drop the draft, returns {ok, message}
 *   navigate(intent)      - perform the original navigation exactly once
 *
 * Guarantees, in the order acceptance asks for them:
 *   - a clean selection leaves immediately and never calls `cancel_edit`;
 *   - only real unsaved work prompts, with three explicit choices;
 *   - the original navigation runs at most once, and only after a save receipt
 *     matched by idempotency key/CAS;
 *   - failure, conflict or an unknown receipt stays on the page with the draft;
 *   - a repeat click while an intent is in flight never queues a second one.
 */
import { hasUnsavedChanges, unsavedReasons } from './dirty-predicate.mjs';
import { saveFailureMessage } from './save-receipt.mjs';

export const LEAVE_CHOICES = Object.freeze(['save_and_leave', 'discard', 'stay']);

const idle = Object.freeze({ status: 'idle', intent: null, reasons: [], message: '' });

export function createLeaveCoordinator({ snapshot, beginEpoch, save, discard, navigate, onLeaveRequest } = {}) {
  for (const [name, fn] of [['snapshot', snapshot], ['beginEpoch', beginEpoch], ['save', save], ['discard', discard], ['navigate', navigate]]) {
    if (typeof fn !== 'function') throw new Error(`离开协调器缺少依赖：${name}`);
  }
  const listeners = new Set();
  let state = idle;
  let disposed = false;

  const update = patch => {
    if (disposed) return;
    const next = { ...state, ...patch };
    if (Object.keys(next).every(key => next[key] === state[key])) return;
    state = Object.freeze(next);
    for (const listener of [...listeners]) listener();
  };

  /** Perform the original navigation at most once per intent. */
  async function navigateOnce(intent) {
    if (intent.performed) return 'navigated';
    intent.performed = true;
    try {
      await navigate(intent, { epoch: intent.epoch });
      update({ status: 'idle', intent: null, reasons: [], message: '' });
      return 'navigated';
    } catch (error) {
      // A host that refuses the navigation leaves the user on the page. That is
      // a stay, and the draft is still there.
      update({ status: 'prompting', message: error instanceof Error ? error.message : '导航未完成，已留在当前页。' });
      return 'stayed';
    }
  }

  async function resolve(intent, choice) {
    if (choice === 'stay') {
      update({ status: 'idle', intent: null, reasons: [], message: '' });
      return 'stayed';
    }
    const reasons = unsavedReasons(snapshot());
    if (choice === 'discard') {
      update({ status: 'discarding', intent, reasons, message: '正在放弃未保存的草稿…' });
      const dropped = await discard();
      if (!dropped?.ok) {
        // A missing or conflicting receipt is the only evidence of what
        // happened; keep the draft instead of pretending it is gone.
        update({ status: 'prompting', message: dropped?.message ?? '未能放弃草稿，已留在当前页。' });
        return 'stayed';
      }
      return navigateOnce(intent);
    }
    if (choice !== 'save_and_leave') throw new Error(`未知的离开选择：${choice}`);
    update({ status: 'saving', intent, reasons, message: '正在保存后离开…' });
    const receipt = await save();
    if (!receipt?.ok) {
      update({ status: 'prompting', message: saveFailureMessage(receipt?.reason ?? 'failed') });
      return 'stayed';
    }
    return navigateOnce(intent);
  }

  return Object.freeze({
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    /**
     * Submit one leave intent.
     * @returns 'navigated' when the page may switch, 'prompt' when the three
     * choices must be shown, 'busy' when another intent is still being resolved
     * (a second navigation is never queued).
     */
    async request(intent) {
      if (disposed) return 'stayed';
      if (state.status !== 'idle') return 'busy';
      const ticket = beginEpoch(intent.kind);
      const pending = { ...intent, epoch: ticket.epoch, performed: false };
      const reasons = unsavedReasons(snapshot());
      if (!hasUnsavedChanges(snapshot())) return navigateOnce(pending);
      update({ status: 'prompting', intent: pending, reasons, message: '' });
      onLeaveRequest?.(pending, reasons);
      return 'prompt';
    },
    /** Apply one of the three explicit choices to the pending intent. */
    async choose(choice) {
      if (disposed || state.status !== 'prompting' || !state.intent) return 'stayed';
      return resolve(state.intent, choice);
    },
    /** Esc and the visible cancel both mean "stay"; neither discards nor saves. */
    stay() {
      if (disposed || state.status !== 'prompting') return;
      update({ status: 'idle', intent: null, reasons: [], message: '' });
    },
    dispose() { disposed = true; listeners.clear(); state = idle; },
  });
}
