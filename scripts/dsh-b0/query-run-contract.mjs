// Offline channel-follow-up run-store contract generation. Never start CRM/HTTP/DB.
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const [mode, pythonFlag, python, ...extra] = process.argv.slice(2);
if (!['--write', '--check'].includes(mode) || pythonFlag !== '--python' || !python || !isAbsolute(python) || extra.length) {
  throw new Error('Usage: node scripts/dsh-b0/query-run-contract.mjs --check|--write --python /absolute/path/to/python3.14');
}
const generate = String.raw`
import importlib.abc, json, sys
if sys.version_info < (3, 14):
    raise SystemExit('query-run contract generation requires explicit Python 3.14+')
class DenyLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = {
            'backend.config', 'backend.routers', 'backend.main', 'backend.db',
            'backend.analytics_app', 'duckdb', 'dotenv',
        }
        if fullname in blocked:
            raise RuntimeError('offline query-run-contract generation cannot import legacy services')
sys.meta_path.insert(0, DenyLegacy())
def offline_only(event, args):
    if event in {'sqlite3.connect', 'socket.connect', 'subprocess.Popen'}:
        raise RuntimeError('offline generation cannot open state or external services')
sys.addaudithook(offline_only)
from backend.contracts.analytics_query_run import QUERY_RUN_SCHEMA, query_run_contract_openapi
schema = query_run_contract_openapi()
if schema.get('paths'):
    raise SystemExit('query-run contract OpenAPI must have empty paths; this is not an HTTP API')
if schema.get('x-not-an-http-api') is not True or schema.get('x-store-only') is not True:
    raise SystemExit('query-run contract must declare x-not-an-http-api and x-store-only')
if schema.get('info', {}).get('version') != QUERY_RUN_SCHEMA:
    raise SystemExit('query-run contract must use analytics-run-channel-followup/v1')
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
  throw new Error(`Offline query-run schema generation failed: ${result.error?.message ?? result.stderr}`);
}
const schema = JSON.parse(result.stdout);
if (schema.paths && Object.keys(schema.paths).length) {
  throw new Error('Generated query-run contract unexpectedly contains HTTP paths');
}
function assertLocalRefs(value) {
  if (!value || typeof value !== 'object') return;
  if ('$ref' in value && !value.$ref.startsWith('#')) throw new Error('External contract references are forbidden');
  Object.values(value).forEach(assertLocalRefs);
}
assertLocalRefs(schema);
if (schema.components?.schemas?.AnalyticsB0Result || schema.components?.schemas?.AnalyticsRunSnapshot) {
  throw new Error('query-run contract must not publish B0 run snapshot/result types');
}
const digest = createHash('sha256').update(JSON.stringify(schema)).digest('hex');
const buildRequire = createRequire(join(root, 'dsh-plugins/analytics-workbench/build-tools/package.json'));
const { default: openapiTS, astToString } = buildRequire('openapi-typescript');
const ts = buildRequire('typescript');
const generatorVersion = JSON.parse(await readFile(buildRequire.resolve('openapi-typescript/package.json'), 'utf8')).version;
if (generatorVersion !== '7.13.0' || ts.version !== '6.0.3') {
  throw new Error('Expected local openapi-typescript 7.13.0 and TypeScript 6.0.3; review toolchain drift before regeneration');
}
const ast = await openapiTS(schema, { alphabetize: true });
const typed = `/** Generated query-run store contract; do not edit. Not an HTTP API. OpenAPI SHA-256: ${digest} */\n${astToString(ast)}`;
const artifacts = new Map([
  ['backend/contracts/analytics-query-run.openapi.json', JSON.stringify({ ...schema, 'x-schema-sha256': digest }, null, 2) + '\n'],
  ['dsh-plugins/analytics-workbench/src/query-run-contract.generated.d.ts', typed],
]);
for (const [relative, content] of artifacts) {
  const path = join(root, relative);
  if (mode === '--write') await writeFile(path, content);
  else if (await readFile(path, 'utf8') !== content) throw new Error(`query-run contract drift: ${relative}`);
}
const program = ts.createProgram([
  join(root, 'dsh-plugins/analytics-workbench/src/query-run-contract.generated.d.ts'),
  join(root, 'dsh-plugins/analytics-workbench/test/query-run-contract.typecheck.ts'),
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
console.log(`query-run contract ${mode === '--write' ? 'generated' : 'verified'}; sha256=${digest}; TypeScript checks passed; store-only, not an HTTP API`);
