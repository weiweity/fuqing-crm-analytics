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

export function mainViewSessionId(snapshot) {
  for (const id of snapshot.ids) {
    if ((snapshot.byId[id]?.retainedBy?.mainView ?? 0) > 0) return id;
  }
  return undefined;
}

/** Visible conversation for free-HTML generate. Never ids[0] or the B0 fixture unless it is current. */
export function resolvePageGenerateSession(list, compositionSessionId) {
  const ids = Array.isArray(list?.ids) ? list.ids : [];
  if (typeof compositionSessionId === 'string' && ids.includes(compositionSessionId)) {
    return compositionSessionId;
  }
  const current = mainViewSessionId(list);
  if (typeof current === 'string' && ids.includes(current)) return current;
  return null;
}

export function retainMainView(sessions, id) {
  return sessions.retain(id, { source: 'mainView' });
}

/** One attempt per plugin lifetime; later user navigation is never overridden. */
export function bindInitialSession(sessions, onFailure) {
  let active = true;
  let consumed = false;
  let held;
  const select = () => {
    if (!active || consumed) return;
    const snapshot = sessions.list.getSnapshot();
    const id = configuredSession(snapshot);
    if (id === null) return;
    consumed = true;
    if (mainViewSessionId(snapshot) === id) return;
    try { held = retainMainView(sessions, id); }
    catch { onFailure(); }
  };
  const unsubscribe = sessions.list.subscribe(select);
  select();
  return () => { active = false; unsubscribe(); held?.release(); };
}
