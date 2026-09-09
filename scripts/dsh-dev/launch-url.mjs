/** Launch-URL helpers for the owned web port. No credentials, no B0 imports. */

const ESC = String.fromCharCode(27);
const stripAnsi = text => text.replace(new RegExp(`${ESC}\\[[0-?]*[ -/]*[@-~]`, 'g'), '');

/** Pass the accumulated log, never an individual stdout chunk. */
export function findReadyUrl(log, origin) {
  if (typeof log !== 'string') return null;
  const complete = stripAnsi(log.slice(0, log.lastIndexOf('\n') + 1));
  for (const candidate of complete.match(/https?:\/\/[^\s<>"']+/g) ?? []) {
    try {
      const url = new URL(candidate);
      const tokens = url.searchParams.getAll('token');
      if (url.origin === origin && !url.username && !url.password && !url.hash
        && tokens.length === 1 && /^[A-Za-z0-9_-]+$/.test(tokens[0])) return url.href;
    } catch { /* incomplete URL */ }
  }
  return null;
}

export function redactLaunchLog(log) {
  return stripAnsi(String(log)).replace(/([?&](?:token|b0)=)[^&#\s"'<>]*/gi, '$1[REDACTED]');
}

export function originOf(host, port) {
  return `http://${host}:${port}`;
}
