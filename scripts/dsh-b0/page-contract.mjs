/** Offline free-page contract generation. Never start CRM/HTTP/DB. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const [mode, flag, python, ...extra] = process.argv.slice(2);
assert.ok(['--check', '--write'].includes(mode) && flag === '--python' && isAbsolute(python ?? '') && !extra.length,
  'Usage: page-contract.mjs --check|--write --python /absolute/python3.14');
assert.equal(process.versions.node.split('.')[0], '24', 'Use the pinned Node 24 toolchain');
const run = spawnSync(python, ['-c', String.raw`
import json, sys
if sys.version_info < (3, 14):
    raise SystemExit('Use Python 3.14+')
class DenyLegacy:
    def find_spec(self, fullname, path=None, target=None):
        blocked = {
            'backend.config', 'backend.routers', 'backend.main', 'backend.db',
            'backend.analytics_app', 'duckdb', 'dotenv',
        }
        if fullname in blocked:
            raise RuntimeError('offline page generation cannot import legacy services')
        return None
sys.meta_path.insert(0, DenyLegacy())
def offline(event, args):
    if event in {'socket.connect', 'sqlite3.connect', 'subprocess.Popen'}:
        raise RuntimeError('offline generation cannot open services or state')
sys.addaudithook(offline)
from backend.contracts.page_documents import page_documents_openapi, PAGE_ERRORS, SCHEMA_VERSION
schema = page_documents_openapi()
assert schema.get('x-page-http') is True
assert schema.get('x-free-page-schema') == SCHEMA_VERSION
assert schema.get('x-b0-board-spec-untouched') == 'board-spec/v1'
assert 'INVALID_BOARD' not in PAGE_ERRORS
assert PAGE_ERRORS['INVALID_PAGE'] == 422
print(json.dumps(schema))
`], { cwd: root, encoding: 'utf8', timeout: 30000, maxBuffer: 4 * 1024 * 1024,
  env: { PATH: `${dirname(python)}:/usr/bin:/bin`, PYTHONPATH: root, PYTHONNOUSERSITE: '1',
    PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' } });
assert.equal(run.status, 0, run.error?.message ?? run.stderr);
const schema = JSON.parse(run.stdout);
function assertLocalRefs(value) {
  if (!value || typeof value !== 'object') return;
  if ('$ref' in value && !value.$ref.startsWith('#/')) throw new Error('External contract references are forbidden');
  Object.values(value).forEach(assertLocalRefs);
}
assertLocalRefs(schema);
for (const name of ['PageDocument', 'PagePackage', 'PageBindingManifest', 'PagePatchPreview',
  'PageSavePreview', 'PageDataReadRequest', 'PageBridgeHandshake']) {
  if (!schema.components?.schemas?.[name]) throw new Error(`missing ${name}`);
}
if (schema.components.schemas.BoardDraft) throw new Error('free-page contract must not publish BoardDraft');
if (schema.components.schemas.BoardDocument) throw new Error('free-page contract must not publish BoardDocument');
function resolveBuildRequire() {
  const candidates = [
    process.env.B0_PLUGIN_BUILD_TOOLS,
    join(root, 'dsh-plugins/analytics-workbench/build-tools/package.json'),
    resolve(root, '../fuqing-crm-analytics/dsh-plugins/analytics-workbench/build-tools/package.json'),
    resolve(root, '../../fuqing-crm-analytics/dsh-plugins/analytics-workbench/build-tools/package.json'),
  ].filter(Boolean);
  for (const pkg of candidates) {
    if (!existsSync(pkg)) continue;
    try {
      const req = createRequire(pkg);
      req.resolve('openapi-typescript');
      req.resolve('typescript');
      return req;
    } catch {
      continue;
    }
  }
  throw new Error('openapi-typescript 7.13.0 not found; reuse pinned build-tools, do not pnpm install');
}
const req = resolveBuildRequire();
assert.equal(req('openapi-typescript/package.json').version, '7.13.0');
assert.equal(req('typescript/package.json').version, '6.0.3');
const { default: openapiTS, astToString } = req('openapi-typescript');
const ts = req('typescript');
const digest = createHash('sha256').update(JSON.stringify(schema)).digest('hex');
const artifacts = new Map([
  ['backend/contracts/analytics-page.openapi.json', JSON.stringify({ ...schema, 'x-schema-sha256': digest }, null, 2) + '\n'],
  ['dsh-plugins/analytics-workbench/src/free-page/contract/page-contract.generated.d.ts',
    `/** Generated free-page contract; do not edit. OpenAPI SHA-256: ${digest} */\n` + astToString(await openapiTS(schema, { alphabetize: true }))],
]);
for (const [relative, content] of artifacts) {
  const path = join(root, relative);
  if (mode === '--write') {
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, content);
  } else {
    assert.equal(await readFile(path, 'utf8'), content, `free-page contract drift: ${relative}`);
  }
}
const generated = join(root, 'dsh-plugins/analytics-workbench/src/free-page/contract/page-contract.generated.d.ts');
const typecheck = join(root, 'dsh-plugins/analytics-workbench/src/free-page/contract/page-contract.typecheck.ts');
const program = ts.createProgram([generated, typecheck], {
  strict: true, noEmit: true, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler, types: [], skipLibCheck: false,
});
const diagnostics = ts.getPreEmitDiagnostics(program);
if (diagnostics.length) {
  throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: (name) => name, getCurrentDirectory: () => root, getNewLine: () => '\n',
  }));
}
console.log(`free-page contract ${mode.slice(2)} passed; sha256=${digest}`);
