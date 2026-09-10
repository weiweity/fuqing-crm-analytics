/** Offline runtime extension; C0 generator bytes are part of its frozen hash. */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const [mode, flag, python, ...extra] = process.argv.slice(2);
assert.ok(['--check', '--write'].includes(mode) && flag === '--python' && isAbsolute(python ?? '') && !extra.length,
  'Usage: competition-chart-contract.mjs --check|--write --python /absolute/python3.14');
const run = spawnSync(python, ['-c', String.raw`
import json, sys
if sys.version_info < (3, 14):
    raise SystemExit('Use Python 3.14+')
def offline(event, args):
    if event in {'socket.connect', 'sqlite3.connect', 'subprocess.Popen'}:
        raise RuntimeError('offline generation cannot open services or state')
sys.addaudithook(offline)
from backend.contracts.competition_chart import chart_openapi
print(json.dumps(chart_openapi()))
`], { cwd: root, encoding: 'utf8', timeout: 30000,
  env: { PATH: `${dirname(python)}:/usr/bin:/bin`, PYTHONPATH: root, PYTHONNOUSERSITE: '1',
    PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' } });
assert.equal(run.status, 0, run.error?.message ?? run.stderr);
const schema = JSON.parse(run.stdout);
const req = createRequire(process.env.B0_PLUGIN_BUILD_TOOLS
  ?? join(root, 'dsh-plugins/analytics-workbench/build-tools/package.json'));
assert.equal(req('openapi-typescript/package.json').version, '7.13.0');
assert.equal(req('typescript/package.json').version, '6.0.3');
const { default: openapiTS, astToString } = req('openapi-typescript');
const artifacts = new Map([
  ['backend/contracts/analytics-competition-chart.openapi.json', JSON.stringify(schema, null, 2) + '\n'],
  ['dsh-plugins/analytics-workbench/src/competition-chart-contract.generated.d.ts',
    '/** Generated competition chart runtime extension; do not edit. */\n' + astToString(await openapiTS(schema, { alphabetize: true }))],
]);
for (const [relative, content] of artifacts) {
  if (mode === '--write') await writeFile(join(root, relative), content);
  else assert.equal(await readFile(join(root, relative), 'utf8'), content, `Chart contract drift: ${relative}`);
}
console.log(`Competition chart runtime contract ${mode.slice(2)} passed`);
