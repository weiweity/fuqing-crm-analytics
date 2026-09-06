/** B0 navigation only: select the exact Host-listed session, never create one. */
export const B0_PRIMARY_SESSION_ID = 'session-b0-synthetic-primary';

export function configuredSession(snapshot) {
  if (snapshot.phase !== 'ready' || !snapshot.ids.includes(B0_PRIMARY_SESSION_ID)
    || snapshot.byId[B0_PRIMARY_SESSION_ID]?.id !== B0_PRIMARY_SESSION_ID) return null;
  return snapshot.byId[B0_PRIMARY_SESSION_ID].id;
}

/** One attempt per plugin lifetime; later user navigation is never overridden. */
export function bindInitialSession(sessions, onFailure) {
  let active = true;
  let consumed = false;
  const select = () => {
    if (!active || consumed) return;
    const snapshot = sessions.list.getSnapshot();
    const id = configuredSession(snapshot);
    if (id === null) return;
    // Set before open(): selection can synchronously notify this same list.
    consumed = true;
    if (snapshot.current === id) return;
    try { sessions.open(id); }
    catch { onFailure(); } // No create, alternate session, or automatic retry.
  };
  const unsubscribe = sessions.list.subscribe(select);
  select();
  return () => { active = false; unsubscribe(); };
}
