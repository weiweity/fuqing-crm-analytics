/** Exact upstream closure. No registry install, source rewrite or absolute URL in artifacts. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, mkdir, symlink, lstat, realpath } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';

export async function bindToolchain(plugin, upstream) {
  const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));
  assert.equal(Number(process.versions.node.split('.')[0]), pin.node_major, 'Use the pinned Node major');
  const git = args => execFileSync('git', ['-C', upstream, ...args], { encoding: 'utf8' }).trim();
  assert.equal(git(['rev-parse', 'HEAD']), pin.upstream_sha, 'Upstream SHA drift');
  assert.equal(git(['status', '--porcelain', '--untracked-files=no']), '', 'Fixed upstream contains local source edits');
  assert.equal(createHash('sha256').update(await readFile(join(upstream, 'pnpm-lock.yaml'))).digest('hex'), pin.upstream_lock_sha256, 'Upstream lock drift');
  const upstreamManifest = JSON.parse(await readFile(join(upstream, 'package.json'), 'utf8'));
  assert.equal(upstreamManifest.packageManager, `pnpm@${pin.pnpm}`);
  const readJson = async path => JSON.parse(await readFile(path, 'utf8'));
  const web = createRequire(join(upstream, 'apps/web/package.json'));
  const vite = createRequire(web.resolve('vite/package.json'));
  const req = createRequire(join(upstream, 'package.json'));
  const conversation = createRequire(join(upstream, 'packages/client/ui-conversation/package.json'));
  const compiler = req('typescript');
  assert.equal(compiler.version, pin.typescript);
  const esbuild = vite('esbuild');
  assert.equal(esbuild.version, pin.esbuild);
  const bindings = new Map();
  for (const [name, path] of Object.entries(pin.sdk_bindings)) {
    const target = join(upstream, path);
    const manifest = await readJson(join(target, 'package.json'));
    assert.equal(manifest.name, name);
    if (name.startsWith('@deepseek-ai/dsh-')) assert.equal(manifest.version, pin.sdk_version);
    bindings.set(name, target);
  }
  for (const [name, resolver, version] of [['react', web, pin.react], ['@types/react', conversation, pin.react_types], ['@types/node', req, pin.node_types]]) {
    const packagePath = resolver.resolve(`${name}/package.json`);
    assert.equal((await readJson(packagePath)).version, version);
    bindings.set(name, dirname(packagePath));
  }
  for (const [name, target] of bindings) {
    const link = join(plugin, 'node_modules', name);
    await mkdir(dirname(link), { recursive: true });
    try {
      const existing = await lstat(link);
      assert.ok(existing.isSymbolicLink(), `Refusing to replace existing dependency: ${name}`);
      assert.equal(await realpath(link), await realpath(target), `Existing SDK binding differs: ${name}`);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      await symlink(relative(dirname(link), target), link, 'dir');
    }
  }
  return { pin, compiler, build: esbuild.build };
}

export function checkTypes(plugin, compiler) {
  const ts = compiler;
  for (const [face, entries, types] of [
    ['host', ['src/index.ts', 'src/tool.ts', 'src/skills.ts'], ['node']],
    ['client', ['src/client/index.tsx', 'src/client/platform.d.ts', 'src/saved-analysis-view.tsx', 'test/run-contract.typecheck.ts'], ['react']],
  ]) {
    const program = ts.createProgram(entries.map(entry => join(plugin, entry)), {
      strict: true, noEmit: true, skipLibCheck: false, target: ts.ScriptTarget.ES2023,
      module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler,
      jsx: ts.JsxEmit.ReactJSX, allowImportingTsExtensions: true,
      lib: ['lib.esnext.d.ts', 'lib.dom.d.ts', 'lib.dom.iterable.d.ts'],
      types, typeRoots: [join(plugin, 'node_modules/@types')],
      // The pinned session-controller declaration imports this SDK type but
      // omits its direct dependency. Supply it in our consumer type closure;
      // keep the upstream pristine and still check every declaration.
      paths: { '@deepseek-ai/dsh-util-values': [join(plugin, 'node_modules/@deepseek-ai/dsh-util-values/lib/types/index.d.ts')] },
    });
    const diagnostics = ts.getPreEmitDiagnostics(program);
    if (diagnostics.length) throw new Error(`${face} typecheck failed:\n` + ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCanonicalFileName: name => name, getCurrentDirectory: () => plugin, getNewLine: () => '\n',
    }));
    console.log(`B0 ${face} full typecheck passed`);
  }
}
