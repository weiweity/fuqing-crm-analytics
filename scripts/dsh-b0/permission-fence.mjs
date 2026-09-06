/** Current-authority checks, never a cached positive grant. */
export async function currentPermission(check) {
  try { return await check() === true; } catch { return false; }
}

/** Serialize a bounded stream and stop permanently on lost permission.
 * A closed fence is never reopened by a late successful check or reconnect;
 * a new connection gets new fences and authenticates independently.
 */
export function permissionFence(check, denied, { queueLimit = 16, pollMs = 0 } = {}) {
  let closed = false, pending = 0, tail = Promise.resolve(), polling = false;
  let timer;
  const close = () => { closed = true; clearInterval(timer); };
  const refuse = () => { if (!closed) { close(); denied(); } };
  const verify = async () => {
    if (closed) return false;
    if (!await currentPermission(check)) { refuse(); return false; }
    return !closed;
  };
  if (pollMs > 0) {
    timer = setInterval(() => {
      if (closed || polling) return;
      polling = true;
      void verify().finally(() => { polling = false; });
    }, pollMs);
    timer.unref();
  }
  return {
    close,
    enqueue(action) {
      if (closed) return Promise.resolve(false);
      if (pending >= queueLimit) { refuse(); return Promise.resolve(false); }
      pending++;
      const work = tail.then(async () => {
        if (!await verify()) return false;
        await action();
        return true;
      }).catch(() => { refuse(); return false; }).finally(() => { pending--; });
      tail = work;
      return work;
    },
  };
}
