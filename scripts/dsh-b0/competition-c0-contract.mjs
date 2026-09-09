/** Offline competition C0 contract generation. Never start CRM/HTTP/DB. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const [mode, pythonFlag, python, ...extra] = process.argv.slice(2);
if (!['--write', '--check'].includes(mode) || pythonFlag !== '--python' || !python || !isAbsolute(python) || extra.length) {
  throw new Error('Usage: node scripts/dsh-b0/competition-c0-contract.mjs --check|--write --python /absolute/path/to/python3.14');
}

function runPython(code, { maxBuffer = 8 * 1024 * 1024, input = undefined } = {}) {
  const result = spawnSync(python, ['-c', code], {
    cwd: root, encoding: 'utf8', timeout: 30000, maxBuffer, input,
    env: {
      PATH: `${dirname(python)}:/usr/bin:/bin`, PYTHONPATH: root,
      PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1',
    },
  });
  if (result.error || result.status !== 0) {
    throw new Error(`Offline C0 python failed: ${result.error?.message ?? result.stderr}`);
  }
  return result.stdout;
}

const generate = String.raw`
import importlib.abc, json, sys
if sys.version_info < (3, 14):
    raise SystemExit('C0 contract generation requires explicit Python 3.14+')
class DenyLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = {
            'backend.config', 'backend.routers', 'backend.main', 'backend.db',
            'backend.analytics_app', 'backend.analytics_cockpit_app', 'duckdb', 'dotenv',
        }
        if fullname in blocked:
            raise RuntimeError('offline C0 generation cannot import legacy services')
sys.meta_path.insert(0, DenyLegacy())
def offline_only(event, args):
    if event in {'sqlite3.connect', 'socket.connect', 'subprocess.Popen'}:
        raise RuntimeError('offline generation cannot open state or external services')
sys.addaudithook(offline_only)
from backend.contracts.competition_c0 import emit_bundle_json
print(emit_bundle_json())
`;
const bundle = JSON.parse(runPython(generate));
const schema = bundle.openapi;
if (schema.paths && Object.keys(schema.paths).length) {
  throw new Error('C0 OpenAPI must have empty paths; this is not an HTTP API');
}
if (schema['x-not-an-http-api'] !== true || schema['x-c0-schema'] !== 'competition-c0/v1') {
  throw new Error('C0 OpenAPI must declare x-not-an-http-api and x-c0-schema');
}
if (schema['x-b0-run-schema-untouched'] !== 'analytics-run-b0/v1') {
  throw new Error('C0 must leave analytics-run-b0/v1 untouched');
}
function assertLocalRefs(value) {
  if (!value || typeof value !== 'object') return;
  if ('$ref' in value && !value.$ref.startsWith('#/')) throw new Error('External contract references are forbidden');
  Object.values(value).forEach(assertLocalRefs);
}
assertLocalRefs(schema);
if (!schema.components?.schemas?.CompetitionCondition) throw new Error('missing CompetitionCondition');
if (!schema.components?.schemas?.CompetitionResultRef) throw new Error('missing CompetitionResultRef');
if (!schema.components?.schemas?.CompetitionBoardSpec) throw new Error('missing CompetitionBoardSpec');
if (!schema.components?.schemas?.AnalyticsCockpitAddOp) throw new Error('C0 must reuse AnalyticsCockpitAddOp');

function resolveBuildRequire() {
  const candidates = [
    process.env.B0_PLUGIN_BUILD_TOOLS,
    join(root, 'dsh-plugins/analytics-workbench/build-tools/package.json'),
    resolve(root, '../../fuqing-crm-analytics/dsh-plugins/analytics-workbench/build-tools/package.json'),
  ].filter(Boolean);
  for (const pkg of candidates) {
    if (!existsSync(pkg)) continue;
    try {
      const req = createRequire(pkg);
      req.resolve('openapi-typescript');
      return req;
    } catch {
      continue;
    }
  }
  throw new Error('openapi-typescript 7.13.0 not found; reuse main-repo build-tools, do not pnpm install');
}

const buildRequire = resolveBuildRequire();
const { default: openapiTS, astToString } = buildRequire('openapi-typescript');
const ts = buildRequire('typescript');
const generatorVersion = JSON.parse(await readFile(buildRequire.resolve('openapi-typescript/package.json'), 'utf8')).version;
if (generatorVersion !== '7.13.0' || ts.version !== '6.0.3') {
  throw new Error('Expected local openapi-typescript 7.13.0 and TypeScript 6.0.3; review toolchain drift before regeneration');
}
const digest = createHash('sha256').update(JSON.stringify(schema)).digest('hex');
const ast = await openapiTS(schema, { alphabetize: true });
const typed = `/** Generated competition C0 contract; do not edit. Not an HTTP API. OpenAPI SHA-256: ${digest} */\n${astToString(ast)}`;
const artifacts = new Map([
  ['backend/contracts/analytics-competition-c0.openapi.json', JSON.stringify({ ...schema, 'x-schema-sha256': digest }, null, 2) + '\n'],
  ['dsh-plugins/analytics-workbench/src/competition-c0-contract.generated.d.ts', typed],
]);
for (const [rel, content] of Object.entries(bundle.docs)) {
  artifacts.set(`docs/hackathon/parallel-competition-2026-09-09/contracts/${rel}`, content);
}

async function syncArtifacts(pending) {
  for (const [relative, content] of pending) {
    const path = join(root, relative);
    if (mode === '--write') {
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, content);
    } else {
      const existing = await readFile(path, 'utf8');
      if (existing !== content) throw new Error(`C0 contract drift: ${relative}`);
    }
  }
}
await syncArtifacts(artifacts);

const hashPy = String.raw`
import json, sys
from pathlib import Path
from backend.contracts.competition_c0 import stable_contract_hash
payload = json.loads(sys.stdin.read())
print(stable_contract_hash(Path(payload['root']), payload['manifest']))
`;
const contractHash = runPython(hashPy, {
  input: JSON.stringify({ root, manifest: bundle.manifest }),
}).trim();

const manifest = { ...bundle.manifest, contract_hash: contractHash, openapi_sha256: digest };
const manifestRel = 'docs/hackathon/parallel-competition-2026-09-09/contracts/C0-MANIFEST.json';
const manifestText = JSON.stringify(manifest, null, 2) + '\n';
await syncArtifacts(new Map([[manifestRel, manifestText]]));

const typecheck = join(root, 'docs/hackathon/parallel-competition-2026-09-09/contracts/competition-c0-contract.typecheck.ts');
const generated = join(root, 'dsh-plugins/analytics-workbench/src/competition-c0-contract.generated.d.ts');
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
console.log(`competition C0 contract ${mode === '--write' ? 'generated' : 'verified'}; sha256=${digest}; contract_hash=${contractHash}; TypeScript checks passed`);
