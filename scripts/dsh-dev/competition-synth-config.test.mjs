import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), '..', 'competition-synth-http.py');
const LOADER = `
import importlib.util
import json
import os
import sys

if sys.version_info[:2] != (3, 14):
    raise SystemExit(f"expected Python 3.14, got {sys.version}")

spec = importlib.util.spec_from_file_location("competition_synth_http", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if module.__name__ == "__main__":
    raise SystemExit("importlib loaded the script as __main__")

request = json.load(sys.stdin)
kind = request["kind"]
if kind == "web_origin":
    if "env_origin" in request:
        os.environ["COMPETITION_SYNTH_WEB_ORIGIN"] = request["env_origin"]
    else:
        os.environ.pop("COMPETITION_SYNTH_WEB_ORIGIN", None)
    try:
        print(json.dumps({"ok": True, "value": module.web_origin()}))
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": "ValueError", "message": str(exc)}))
elif kind == "allowed_web_origin":
    try:
        print(json.dumps({"ok": True, "value": module.allowed_web_origin(request["origin"])}))
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": "ValueError", "message": str(exc)}))
elif kind == "refuse_bind":
    try:
        module.refuse_protected_bind_port(int(request["port"]))
        print(json.dumps({"ok": True, "port": int(request["port"])}))
    except SystemExit as exc:
        print(json.dumps({"ok": False, "error": "SystemExit", "message": str(exc), "port": int(request["port"])}))
elif kind == "imported_bind":
    try:
        module.refuse_protected_bind_port(module.PORT)
        print(json.dumps({"ok": True, "port": module.PORT}))
    except SystemExit as exc:
        print(json.dumps({"ok": False, "error": "SystemExit", "message": str(exc), "port": module.PORT}))
elif kind == "import_probe":
    print(json.dumps({
        "ok": True,
        "module_name": module.__name__,
        "has_main": callable(getattr(module, "main", None)),
    }))
else:
    raise SystemExit(f"unknown kind {kind}")
`;

function pythonEnv(extra = {}) {
  return {
    PATH: process.env.PATH ?? '/usr/bin:/bin',
    PYTHONNOUSERSITE: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHON_DOTENV_DISABLED: '1',
    ...extra,
  };
}

function inspectPython(bin, env = process.env) {
  return spawnSync(bin, ['-c', 'import sys; print("%d.%d" % sys.version_info[:2]); print(sys.executable)'], {
    encoding: 'utf8',
    env: pythonEnv({ PATH: env.PATH ?? process.env.PATH ?? '/usr/bin:/bin' }),
    timeout: 5000,
  });
}

function failHard(message) {
  const error = new Error(message);
  error.message = message;
  throw error;
}

function resolvePython(env = process.env) {
  const specified = env.FQ_B0_PYTHON;
  if (specified != null && specified !== '') {
    if (!isAbsolute(specified)) {
      failHard('FQ_B0_PYTHON must name an existing absolute Python executable');
    }
    if (!existsSync(specified)) {
      failHard(`FQ_B0_PYTHON does not exist: ${specified}`);
    }
    const st = statSync(specified);
    if (!st.isFile()) {
      failHard(`FQ_B0_PYTHON is not a file: ${specified}`);
    }
    const child = inspectPython(specified, env);
    if (child.error) {
      failHard(`FQ_B0_PYTHON is not executable: ${specified} (${child.error.code ?? child.error.message})`);
    }
    if (child.status !== 0) {
      failHard(`FQ_B0_PYTHON failed (${child.status}): ${child.stderr || child.stdout}`);
    }
    const version = child.stdout.trim().split('\n')[0];
    if (version !== '3.14') {
      failHard(`expected Python 3.14, got ${version} from ${specified}`);
    }
    return specified;
  }
  const child = inspectPython('python3.14', env);
  if (child.error) {
    if (child.error.code === 'ENOENT') {
      failHard('python3.14 not found on PATH; set FQ_B0_PYTHON to an existing absolute Python 3.14 executable');
    }
    failHard(`python3.14 probe failed: ${child.error.message}`);
  }
  if (child.status !== 0) {
    failHard(`python3.14 failed (${child.status}): ${child.stderr || child.stdout}`);
  }
  const version = child.stdout.trim().split('\n')[0];
  if (version !== '3.14') {
    failHard(`expected Python 3.14, got ${version}`);
  }
  return 'python3.14';
}

function assertHardFailure(fn, pattern) {
  let err;
  try {
    fn();
  } catch (caught) {
    err = caught;
  }
  assert.ok(err, 'expected a hard failure, not success or skip');
  assert.match(String(err.message), pattern);
  assert.doesNotMatch(String(err.message), /\bskip(?:ped|ping)?\b/i);
  assert.doesNotMatch(String(err.message), /\binstall(?:ing|ed)?\b/i);
}

function probeWith(python, request, extraEnv = {}) {
  const child = spawnSync(python, ['-c', LOADER, SCRIPT], {
    encoding: 'utf8',
    input: JSON.stringify(request),
    env: pythonEnv(extraEnv),
    timeout: 15000,
  });
  if (child.error) throw child.error;
  const combined = `${child.stdout}${child.stderr}`;
  assert.equal(combined.includes('COMPETITION_SYNTH_READY'), false);
  assert.doesNotMatch(combined, /uvicorn/i);
  if (child.status !== 0) {
    throw new Error(`python probe failed (${child.status}): ${child.stderr || child.stdout}`);
  }
  return JSON.parse(child.stdout);
}

function probe(request, extraEnv = {}) {
  return probeWith(resolvePython(), request, extraEnv);
}

test('Node 24 drives the specified Python 3.14 interpreter', () => {
  assert.equal(process.versions.node.split('.')[0], '24');
  const python = resolvePython();
  const child = spawnSync(python, ['-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], {
    encoding: 'utf8', env: pythonEnv(), timeout: 5000,
  });
  assert.equal(child.status, 0, child.stderr);
  assert.equal(child.stdout.trim(), '3.14');
});

test('importlib loads the real synth script without starting the HTTP service', () => {
  const got = probe({ kind: 'import_probe' });
  assert.equal(got.ok, true);
  assert.equal(got.module_name, 'competition_synth_http');
  assert.equal(got.has_main, true);
});

test('default COMPETITION_SYNTH_WEB_ORIGIN remains the 14327 loopback origin', () => {
  const got = probe({ kind: 'web_origin' });
  assert.equal(got.ok, true);
  assert.equal(got.value, 'http://127.0.0.1:14327');
});

test('explicit 6677 page origin is accepted by the real web_origin helper', () => {
  const viaEnv = probe({ kind: 'web_origin', env_origin: 'http://127.0.0.1:6677' });
  assert.equal(viaEnv.ok, true);
  assert.equal(viaEnv.value, 'http://127.0.0.1:6677');
  const viaFn = probe({ kind: 'allowed_web_origin', origin: 'http://127.0.0.1:6677' });
  assert.equal(viaFn.ok, true);
  assert.equal(viaFn.value, 'http://127.0.0.1:6677');
});

test('existing isolated loopback origins stay accepted', () => {
  for (const origin of [
    'http://127.0.0.1:4325',
    'http://127.0.0.1:4326',
    'http://127.0.0.1:4328',
    'http://127.0.0.1:4329',
    'http://127.0.0.1:14327',
  ]) {
    const got = probe({ kind: 'allowed_web_origin', origin });
    assert.equal(got.ok, true, origin);
    assert.equal(got.value, origin);
  }
});

test('unauthorized origins stay rejected', () => {
  for (const origin of [
    '*',
    'https://example.com',
    'https://127.0.0.1:6677',
    'http://127.0.0.1:4327',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:18082',
    'http://0.0.0.0:6677',
    'http://192.168.1.2:6677',
    'http://localhost:6677',
    'http://[::1]:6677',
    'http://127.0.0.1:6678',
    'http://127.0.0.1:6677/',
    '',
  ]) {
    const got = probe({ kind: 'allowed_web_origin', origin });
    assert.equal(got.ok, false, origin);
    assert.equal(got.error, 'ValueError');
    assert.match(got.message, /isolated loopback/);
  }
});

test('synth HTTP refuses to bind 6677 and the original protected ports', () => {
  for (const port of [4327, 8000, 5173, 6677, 14327]) {
    const got = probe({ kind: 'refuse_bind', port });
    assert.equal(got.ok, false, String(port));
    assert.equal(got.error, 'SystemExit');
    assert.equal(got.message, `refusing to bind user/demo port ${port}`);
  }
});

test('default synth port 18082 remains bindable and 6677 env is refused before listen', () => {
  const allowed = probe({ kind: 'imported_bind' });
  assert.equal(allowed.ok, true);
  assert.equal(allowed.port, 18082);
  const blocked = probe({ kind: 'imported_bind' }, { COMPETITION_SYNTH_PORT: '6677' });
  assert.equal(blocked.ok, false);
  assert.equal(blocked.port, 6677);
  assert.equal(blocked.message, 'refusing to bind user/demo port 6677');
});

test('explicit missing interpreter fails without fallback, skip, or install', () => {
  const dir = mkdtempSync(join(tmpdir(), 'synth-missing-'));
  const missing = join(dir, 'python3.14');
  try {
    assert.equal(existsSync(missing), false);
    const pathWith314 = process.env.PATH ?? '/usr/bin:/bin';
    assertHardFailure(
      () => resolvePython({ FQ_B0_PYTHON: missing, PATH: pathWith314 }),
      /does not exist/,
    );
    const child = spawnSync(missing, ['-c', LOADER, SCRIPT], {
      encoding: 'utf8',
      input: JSON.stringify({ kind: 'import_probe' }),
      env: pythonEnv(),
      timeout: 5000,
    });
    assert.equal(child.error?.code, 'ENOENT');
    assert.notEqual(child.status, 0);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('explicit relative interpreter is rejected without PATH substitution', () => {
  assertHardFailure(
    () => resolvePython({ FQ_B0_PYTHON: 'python3.14', PATH: process.env.PATH }),
    /absolute Python executable/,
  );
});

test('explicit wrong-version interpreter fails without substitution', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'synth-wrong-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const fake = join(dir, 'python3.14');
  writeFileSync(fake, '#!/bin/sh\nprintf \'3.13\\n%s\\n\' "$0"\n', { mode: 0o755 });
  assertHardFailure(
    () => resolvePython({ FQ_B0_PYTHON: fake, PATH: process.env.PATH }),
    /expected Python 3\.14, got 3\.13/,
  );
  const others = ['python3.13', 'python3.12', 'python3.11', 'python3.9', '/usr/bin/python3'];
  for (const name of others) {
    const other = inspectPython(name, process.env);
    if (other.error || other.status !== 0) continue;
    const [version, executable] = other.stdout.trim().split('\n');
    if (version === '3.14' || !executable) continue;
    assertHardFailure(
      () => resolvePython({ FQ_B0_PYTHON: executable, PATH: process.env.PATH }),
      /expected Python 3\.14/,
    );
    const probeChild = spawnSync(executable, ['-c', LOADER, SCRIPT], {
      encoding: 'utf8',
      input: JSON.stringify({ kind: 'import_probe' }),
      env: pythonEnv(),
      timeout: 15000,
    });
    assert.notEqual(probeChild.status, 0);
    assert.match(`${probeChild.stdout}${probeChild.stderr}`, /expected Python 3\.14/);
    break;
  }
});

test('PATH without python3.14 fails instead of skipping or installing', () => {
  const emptyPath = mkdtempSync(join(tmpdir(), 'synth-empty-path-'));
  try {
    assert.equal(readdirSync(emptyPath).length, 0);
    assert.equal(existsSync(join(emptyPath, 'python3.14')), false);
    assertHardFailure(
      () => resolvePython({ PATH: emptyPath }),
      /python3\.14 not found on PATH/,
    );
  } finally {
    rmSync(emptyPath, { recursive: true, force: true });
  }
});

test('Python 3.14 from a non-fixed install path still loads the real synth script', (t) => {
  const configured = resolvePython(process.env);
  const inspected = inspectPython(configured, process.env);
  assert.equal(inspected.status, 0, inspected.stderr);
  const [version, real] = inspected.stdout.trim().split('\n');
  assert.equal(version, '3.14');
  assert.ok(real);
  const dir = mkdtempSync(join(tmpdir(), 'synth-alias-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const alias = join(dir, 'python');
  symlinkSync(real, alias);
  assert.equal(alias.includes('python@3.14'), false);
  assert.equal(resolvePython({ FQ_B0_PYTHON: alias, PATH: '/usr/bin:/bin' }), alias);
  const got = probeWith(alias, { kind: 'import_probe' });
  assert.equal(got.ok, true);
  assert.equal(got.module_name, 'competition_synth_http');
  assert.equal(got.has_main, true);
  const origin = probeWith(alias, { kind: 'web_origin' });
  assert.equal(origin.ok, true);
  assert.equal(origin.value, 'http://127.0.0.1:14327');
  const blocked = probeWith(alias, { kind: 'imported_bind' }, { COMPETITION_SYNTH_PORT: '6677' });
  assert.equal(blocked.ok, false);
  assert.equal(blocked.port, 6677);
});

test('this file does not pin a machine-local Python prefix', () => {
  const source = readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const pinned = ['Users', 'hutou', 'homebrew', 'opt', 'python@3.14'].join('/');
  assert.equal(source.includes(`/${pinned}`), false);
  assert.equal(source.includes(pinned), false);
});
