/** Read-only diagnostic, mounted only by the explicit disposable browser probe. */
export const name = 'composition-fixture-diagnostic';
export const inject = ['webServer', 'connection', 'loader', 'clientModules'];
export function apply(ctx) {
  ctx.effect(() => ctx.webServer.register({ kind: 'exact', path: '/__composition_diagnostic__',
    handler(req, res) {
      const rejection = ctx.connection.requestRejection(req);
      if (rejection) { res.writeHead(rejection); res.end(); return; }
      const runtimes = [...ctx.registry.values()].filter(runtime =>
        /analytics|competition|board|connection/.test(runtime.name ?? ''));
      const rows = runtimes.map(runtime => ({ name: runtime.name,
        fibers: [...runtime.fibers].map(fiber => ({ state: fiber.state,
          error: fiber.state === 3 ? String(fiber._error?.message ?? 'unknown').replace(/([?&]token=)[^\s&]+/g, '$1[REDACTED]').slice(0, 1000) : undefined,
          services: Object.fromEntries(['agents', 'sessions', 'sessionController', 'connection', 'webServer', 'tools', 'skills']
            .map(key => [key, Boolean(fiber.ctx.get(key))])) })) }));
      res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify({ rows,
        businessEntries: [...ctx.loader.entries()].filter(entry => entry.options.name === '@shine-mage/dsh-analytics-workbench-b0')
          .map(entry => ({ id: entry.options.id, disabled: entry.disabled, fiber: entry.fiber?.state })),
        businessClient: ctx.clientModules.graph().entries.filter(entry => entry.id === '@shine-mage/dsh-analytics-workbench-b0')
          .map(entry => ({ id: entry.id, rev: entry.rev })),
      }));
    } }), 'composition-fixture: read-only runtime diagnosis');
}
