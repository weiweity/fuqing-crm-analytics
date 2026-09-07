/** B0/query navigation only: select the exact Host-listed session, never create one. */
export const B0_PRIMARY_SESSION_ID = 'session-b0-synthetic-primary';
export const QUERY_SESSION_IDS = Object.freeze(['session-query-synthetic-a', 'session-query-synthetic-b']);

function listed(snapshot, id) {
  return snapshot.ids.includes(id) && snapshot.byId[id]?.id === id;
}

export function configuredSession(snapshot) {
  if (snapshot.phase !== 'ready') return null;
  if (QUERY_SESSION_IDS.every(id => listed(snapshot, id))) return QUERY_SESSION_IDS[0];
  if (listed(snapshot, B0_PRIMARY_SESSION_ID)) return B0_PRIMARY_SESSION_ID;
  return null;
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
