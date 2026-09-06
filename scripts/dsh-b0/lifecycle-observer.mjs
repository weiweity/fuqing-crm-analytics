/** Passive B0 diagnostics, not a supervisor/retry loop or business audit log.
 * No signal/unhandledRejection handler: preserve Node's default crash behavior.
 * SIGKILL/power loss cannot write an exit event; absence is NOT a cause verdict.
 */
import { openSync, appendFileSync, closeSync } from 'node:fs';
import { join } from 'node:path';

const events = new Set(['start', 'heartbeat', 'mock-ready', 'kernel-start', 'kernel-exit',
  'host-start', 'host-close', 'host-ready', 'signal', 'stop-start', 'stop-complete',
  'startup-error', 'diagnostic-pipe-closed', 'fatal', 'exit']);
const signals = new Set(['SIGTERM', 'SIGINT', 'SIGUSR1', 'SIGUSR2', 'SIGKILL', 'SIGHUP', 'SIGABRT']);
const reasons = new Set(['SIGTERM', 'SIGINT', 'host-restart-failed', 'startup-failed', 'child-exit']);
const codes = new Set(['EPIPE', 'ENOSPC', 'EIO', 'ENOENT', 'EACCES', 'ENOMEM',
  'ERR_UNHANDLED_REJECTION', 'ERR_ASSERTION']);

export function observeLifecycle(directory) {
  // Fresh private runtime only: never overwrite/follow an existing evidence file.
  const fd = openSync(join(directory, 'supervisor-lifecycle.jsonl'), 'wx', 0o600);
  let available = true;
  let closed = false;
  let count = 0;
  let capped = false;
  const terminals = new Set();
  function record(event, fields = {}) {
    if (!available || !events.has(event)) return false;
    try {
      const terminal = event === 'fatal' || event === 'exit';
      if (terminal) {
        if (terminals.has(event)) return false;
        terminals.add(event);
      } else if (count++ >= 500) {
        if (capped) return false;
        capped = true;
        event = 'limit-reached';
        fields = {};
      }
      const row = { at: new Date().toISOString(), event, pid: process.pid };
      for (const key of ['ppid', 'childPid', 'generation', 'exitCode']) {
        if (Number.isSafeInteger(fields[key])) row[key] = fields[key];
      }
      if (signals.has(fields.signal)) row.signal = fields.signal;
      if (reasons.has(fields.reason)) row.reason = fields.reason;
      if (['uncaughtException', 'unhandledRejection'].includes(fields.origin)) row.origin = fields.origin;
      if (fields.errorCode !== undefined) row.errorCode = codes.has(fields.errorCode) ? fields.errorCode : 'OTHER';
      appendFileSync(fd, JSON.stringify(row) + '\n');
      return true;
    } catch {
      // Observability must not create a second crash or swallow the original one.
      available = false;
      return false;
    }
  }
  const fatal = (error, origin) => {
    try { record('fatal', { origin, errorCode: error?.code ?? 'OTHER' }); } catch { /* hostile error getter */ }
  };
  const exited = exitCode => { record('exit', { exitCode }); dispose(); };
  process.on('uncaughtExceptionMonitor', fatal);
  process.once('exit', exited);
  const heartbeat = setInterval(() => record('heartbeat', { ppid: process.ppid }), 5000);
  heartbeat.unref();
  function dispose() {
    if (closed) return;
    closed = true;
    clearInterval(heartbeat);
    process.off('uncaughtExceptionMonitor', fatal);
    process.off('exit', exited);
    available = false;
    try { closeSync(fd); } catch { /* already closed */ }
  }
  record('start', { ppid: process.ppid });
  return { record, dispose };
}
