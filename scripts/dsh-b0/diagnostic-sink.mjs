/** Optional diagnostic forwarding must survive a closed consumer pipe.
 * Only EPIPE is recoverable here; other stream errors retain Node's fatal behavior.
 * The listener lives as long as the supervisor-owned destination stream.
 */
export function createDiagnosticSink(stream, onClosed) {
  let closed = false;
  const handleError = error => {
    if (error?.code !== 'EPIPE') throw error;
    if (closed) return;
    closed = true;
    onClosed();
  };
  stream.on('error', handleError);
  return {
    write(chunk) {
      if (closed) return false;
      try { return stream.write(chunk); }
      catch (error) { handleError(error); return false; }
    },
  };
}
