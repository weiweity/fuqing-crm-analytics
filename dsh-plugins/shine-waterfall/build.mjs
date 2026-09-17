import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { readFile } from 'node:fs/promises';
import { bindToolchain } from '../analytics-workbench/toolchain.mjs';

const root = dirname(fileURLToPath(import.meta.url));
const workbench = resolve(root, '../analytics-workbench');
const upstream = resolve(process.argv[2] ?? join(root, '../../.context/dsh-b0/upstream'));
const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
const { build } = await bindToolchain(workbench, upstream, process.argv[3] && resolve(process.argv[3]));

const common = { absWorkingDir: root, bundle: true, sourcemap: true, logLevel: 'info', minifyWhitespace: true };
await build({
  ...common, entryPoints: ['src/index.ts'], outdir: 'lib', platform: 'node',
  target: 'node24', format: 'esm', external: ['@deepseek-ai/*'],
});
await build({
  ...common, entryPoints: ['src/client.tsx'], outfile: 'lib/client.js',
  platform: 'browser', target: 'es2022', format: 'cjs', jsx: 'automatic',
  external: ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis'],
  minify: true,
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  banner: { js: `window.__ModuleLoader__.load({ id: ${JSON.stringify(manifest.name)}, factory: (require) => {\nvar module = { exports: {} }; var exports = module.exports;` },
  footer: { js: 'return module.exports;\n} });' },
});
console.log(`shine-waterfall built. Host entry: ${pathToFileURL(join(root, 'lib/index.js')).href}`);
