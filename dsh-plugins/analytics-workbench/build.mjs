import { readFile } from 'node:fs/promises';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { bindToolchain, checkTypes } from './toolchain.mjs';
import { packSkills } from './pack-skills.mjs';

const root = dirname(fileURLToPath(import.meta.url));
const upstream = resolve(process.argv[2] ?? join(root, '../../.context/dsh-b0/upstream'));
const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
const { build, compiler } = await bindToolchain(root, upstream);
const skillPackage = await packSkills(root);
const querySkillPackage = await packSkills(root, 'channel_followup');
checkTypes(root, compiler);

const external = [
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-store', '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-ui-primitives',
];
const common = { absWorkingDir: root, bundle: true, sourcemap: true, logLevel: 'info' };
await build({
  ...common, entryPoints: ['src/index.ts', 'src/tool.ts', 'src/skills.ts'], outdir: 'lib', platform: 'node',
  target: 'node24', format: 'esm',
  define: {
    __B0_SKILL_PACKAGE__: JSON.stringify(skillPackage),
    __QUERY_SKILL_PACKAGE__: JSON.stringify(querySkillPackage),
  },
  external: ['@deepseek-ai/*'],
});
await build({
  ...common, entryPoints: ['src/client/index.tsx'], outfile: 'lib/client.js',
  platform: 'browser', target: 'es2022', format: 'cjs', jsx: 'automatic', external,
  banner: { js: `window.__ModuleLoader__.load({ id: ${JSON.stringify(manifest.name)}, factory: (require) => {\nvar module = { exports: {} }; var exports = module.exports;` },
  footer: { js: 'return module.exports;\n} });' },
});
// These offline views are built and checked independently until native/HTTP
// registration is implemented. Do not silently exclude them from verification.
await build({
  ...common, entryPoints: ['src/saved-analysis-view.tsx', 'src/cockpit-view.tsx'],
  outdir: 'lib/views', platform: 'browser', target: 'es2022',
  format: 'esm', jsx: 'automatic', external,
});
console.log(`B0 plugin built. Host entry: ${pathToFileURL(join(root, 'lib/index.js')).href}`);
