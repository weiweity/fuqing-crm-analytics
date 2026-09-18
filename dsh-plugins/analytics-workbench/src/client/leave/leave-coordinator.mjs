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

  /**
   * Perform the original navigation at most once per intent. A host that
   * refuses leaves the intent retryable: `performed` is only marked after the
   * navigation actually resolves, so the user can try again instead of being
   * told they left while still on the page.
   */
  async function navigateOnce(intent) {
    if (intent.performed) return 'navigated';
    try {
      await navigate(intent, { epoch: intent.epoch });
    } catch (error) {
      update({ status: 'prompting', message: error instanceof Error ? error.message : '导航未完成，已留在当前页。' });
      return 'stayed';
    }
    intent.performed = true;
    update({ status: 'idle', intent: null, reasons: [], message: '' });
    return 'navigated';
  }

  /**
   * Apply one choice. `busy` is set synchronously before the first await, so a
   * second click cannot start a parallel save/discard against the same draft.
   */
  function resolve(intent, choice) {
    if (choice === 'stay') {
      update({ status: 'idle', intent: null, reasons: [], message: '' });
      return Promise.resolve('stayed');
    }
    const reasons = unsavedReasons(snapshot());
    if (choice === 'discard') {
      update({ status: 'discarding', intent, reasons, message: '正在放弃未保存的草稿…' });
      return discard().then(dropped => {
        if (!dropped?.ok) {
          // A missing or conflicting receipt is the only evidence of what
          // happened; keep the draft instead of pretending it is gone.
          update({ status: 'prompting', message: dropped?.message ?? '未能放弃草稿，已留在当前页。' });
          return 'stayed';
        }
        return afterDraftResolved(intent);
      });
    }
    if (choice !== 'save_and_leave') throw new Error(`未知的离开选择：${choice}`);
    update({ status: 'saving', intent, reasons, message: '正在保存后离开…' });
    return save().then(receipt => {
      if (!receipt?.ok) {
        update({ status: 'prompting', message: saveFailureMessage(receipt?.reason ?? 'failed') });
        return 'stayed';
      }
      return afterDraftResolved(intent);
    });
  }

  /**
   * A save/discard receipt is not by itself permission to leave: the page must
   * actually be clean now. An uncertain receipt, or a layout draft the discard
   * did not cover, still blocks — otherwise the user leaves work behind while
   * being told it was saved.
   */
  function afterDraftResolved(intent) {
    const remaining = unsavedReasons(snapshot());
    if (remaining.length > 0) {
      update({ status: 'prompting', reasons: remaining,
        message: saveFailureMessage(remaining.includes('confirmationUncertain') ? 'uncertain' : 'failed') });
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
    /**
     * Advance navigation ownership for a switch the plugin did not initiate and
     * cannot veto (the host's sidebar row writes straight to `selectPanel`).
     *
     * This deliberately does NOT submit a leave intent: the host has already
     * committed the switch, so asking the coordinator to "navigate" would
     * re-issue a navigation for a page the user already left. Taking the epoch
     * is the whole point — it makes in-flight get/list/preview discard
     * themselves instead of publishing over the new panel.
     */
    observeExternal(kind = 'panel') {
      if (disposed) return;
      beginEpoch(kind);
    },
    /**
     * Apply one of the three explicit choices to the pending intent.
     * Not `async`: the choice must take the busy lock synchronously, so two
     * overlapping clicks cannot both start a write against the same draft.
     */
    choose(choice) {
      if (disposed || state.status !== 'prompting' || !state.intent) return Promise.resolve('stayed');
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
