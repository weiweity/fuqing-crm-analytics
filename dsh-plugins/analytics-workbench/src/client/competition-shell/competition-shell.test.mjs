import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const dir = fileURLToPath(new URL('.', import.meta.url));
const stylesPath = join(dir, '../styles.ts');

async function source(name) {
  return readFile(join(dir, name), 'utf8');
}

test('competition shell exports the A6 contract names with the locked AntD provider', async () => {
  const index = await source('index.ts');
  for (const name of [
    'ThemeProvider', 'LayoutSlot', 'CompetitionShell', 'BrandMark', 'BrandNav', 'WelcomeHero',
    'PageTitle', 'ErrorState', 'ShellDialog', 'StatusBanner', 'EvidenceBlock', 'ConditionChips',
    'useCompetitionTheme', 'antdTheme', 'antdSeedToken', 'competitionTokens', 'LAYOUT_SLOT_NAMES',
  ]) {
    assert.match(index, new RegExp(name));
  }
  assert.doesNotMatch(index, /from 'antd'|from "antd"/);
  const provider = await source('ThemeProvider.tsx');
  assert.match(provider, /from 'antd\/es\/config-provider'/);
  assert.doesNotMatch(provider, /ConfigProvider\?:/);
});

test('brand tokens follow DESIGN.md and keep original asset URLs', async () => {
  const tokens = await source('tokens.ts');
  assert.match(tokens, /#09050D/);
  assert.match(tokens, /#805D9D/);
  assert.match(tokens, /#D3C3E8/);
  assert.match(tokens, /#F2FFDC/);
  assert.match(tokens, /#FEFCFF/);
  assert.match(tokens, /#FF7D91/);
  assert.match(tokens, /21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000/);
  assert.match(tokens, /\/b0\/brand\/logo\.png/);
  assert.match(tokens, /brightness\(0\) invert\(1\)/);
  assert.match(tokens, /controlHeight: 44/);
  assert.doesNotMatch(tokens, /frontend-vue3\/src\/theme/);
});

test('competition CSS covers welcome/nav/title/error/dialog and reduced motion', async () => {
  const css = await source('css.ts');
  assert.match(css, /sm-welcome/);
  assert.match(css, /sm-brand-nav/);
  assert.match(css, /sm-page-title/);
  assert.match(css, /sm-error-state/);
  assert.match(css, /sm-shell-dialog/);
  assert.match(css, /min-height: var\(--sm-touch\)/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /max-width: 390px/);
  assert.match(css, /max-width: 768px/);
  assert.doesNotMatch(css, /linear-gradient\([^)]*#805D9D[^)]*\)/);
});

test('native chrome export const css is not painted with Vue brand literals', async () => {
  const stylesSource = await readFile(stylesPath, 'utf8');
  const css = stylesSource.slice(stylesSource.indexOf('export const css'), stylesSource.lastIndexOf('`;'));
  assert.doesNotMatch(css, /#09050D|#805D9D|#F2FFDC/);
  assert.doesNotMatch(css, /Outfit|Alibaba PuHuiTi/);
  assert.match(stylesSource, /competitionShellCss/);
});

test('layout slots include A6 mount points and do not register native DSH keys', async () => {
  const layout = await source('LayoutSlot.tsx');
  assert.match(layout, /'welcome', 'nav', 'title', 'error', 'dialog', 'ask', 'analyses', 'cockpit', 'actions'/);
  assert.doesNotMatch(layout, /sidebar\.brand|tool\.call\.toolview|conversation\.input/);
  const chrome = await source('BrandChrome.tsx');
  assert.match(chrome, /模型、权限与文件设置仍走原生 DSH 入口/);
});
