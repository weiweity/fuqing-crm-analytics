/** Offline cockpit HTTP contract. Never start CRM/HTTP/DB. */
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const [mode, pythonFlag, python, ...extra] = process.argv.slice(2);
if (!['--write', '--check'].includes(mode) || pythonFlag !== '--python' || !python || !isAbsolute(python) || extra.length) {
  throw new Error('Usage: node scripts/dsh-b0/cockpit-contract.mjs --check|--write --python /absolute/path/to/python3.14');
}
const generate = String.raw`
import importlib.abc, json, sys
if sys.version_info < (3, 14):
    raise SystemExit('cockpit contract generation requires explicit Python 3.14+')
class DenyLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'backend.config', 'backend.routers', 'backend.main', 'backend.db', 'duckdb', 'dotenv'}:
            raise RuntimeError('offline cockpit generation cannot import legacy services')
sys.meta_path.insert(0, DenyLegacy())
def offline_only(event, args):
    if event in {'sqlite3.connect', 'socket.connect', 'subprocess.Popen'}:
        raise RuntimeError('offline generation cannot open state or external services')
sys.addaudithook(offline_only)
from backend.analytics_cockpit_app import create_cockpit_app
schema = create_cockpit_app().openapi()
if schema.get('x-cockpit-http') is not True:
    raise SystemExit('cockpit OpenAPI must declare x-cockpit-http')
print(json.dumps(schema, sort_keys=True, ensure_ascii=False, allow_nan=False))
`;
const result = spawnSync(python, ['-c', generate], {
  cwd: root, encoding: 'utf8', timeout: 15000, maxBuffer: 2 * 1024 * 1024,
  env: {
    PATH: `${dirname(python)}:/usr/bin:/bin`, PYTHONPATH: root,
    PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1',
  },
});
if (result.error || result.status !== 0) {
  throw new Error(`Offline cockpit schema generation failed: ${result.error?.message ?? result.stderr}`);
}
const schema = JSON.parse(result.stdout);
function assertLocalRefs(value) {
  if (!value || typeof value !== 'object') return;
  if ('$ref' in value && !value.$ref.startsWith('#/')) throw new Error('External contract references are forbidden');
  Object.values(value).forEach(assertLocalRefs);
}
assertLocalRefs(schema);
if (!schema.paths?.['/api/v1/analytics/dashboards']) throw new Error('missing dashboards collection path');
if (schema.paths['/api/v1/analytics/analyses']) throw new Error('cockpit contract must not publish saved-analysis routes');
if (schema.paths['/api/v1/analytics-query/runs/{run_id}']) throw new Error('cockpit contract must not publish query session routes');
const digest = createHash('sha256').update(JSON.stringify(schema)).digest('hex');
const buildRequire = createRequire(join(root, 'dsh-plugins/analytics-workbench/build-tools/package.json'));
const { default: openapiTS, astToString } = buildRequire('openapi-typescript');
const ts = buildRequire('typescript');
const generatorVersion = JSON.parse(await readFile(buildRequire.resolve('openapi-typescript/package.json'), 'utf8')).version;
if (generatorVersion !== '7.13.0' || ts.version !== '6.0.3') {
  throw new Error('Expected local openapi-typescript 7.13.0 and TypeScript 6.0.3; review toolchain drift before regeneration');
}
const ast = await openapiTS(schema, { alphabetize: true });
const typed = `/** Generated cockpit HTTP contract; do not edit. OpenAPI SHA-256: ${digest} */\n${astToString(ast)}`;
const artifacts = new Map([
  ['backend/contracts/analytics-cockpit.openapi.json', JSON.stringify({ ...schema, 'x-schema-sha256': digest }, null, 2) + '\n'],
  ['dsh-plugins/analytics-workbench/src/cockpit-contract.generated.d.ts', typed],
]);
for (const [relative, content] of artifacts) {
  const path = join(root, relative);
  if (mode === '--write') await writeFile(path, content);
  else if (await readFile(path, 'utf8') !== content) throw new Error(`cockpit contract drift: ${relative}`);
}
const program = ts.createProgram([
  join(root, 'dsh-plugins/analytics-workbench/src/cockpit-contract.generated.d.ts'),
  join(root, 'dsh-plugins/analytics-workbench/test/cockpit-contract.typecheck.ts'),
], {
  strict: true, noEmit: true, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler, types: [], skipLibCheck: false,
});
const diagnostics = ts.getPreEmitDiagnostics(program);
if (diagnostics.length) {
  throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: (name) => name, getCurrentDirectory: () => root, getNewLine: () => '\n',
  }));
}
console.log(`cockpit contract ${mode === '--write' ? 'generated' : 'verified'}; sha256=${digest}; TypeScript checks passed`);
