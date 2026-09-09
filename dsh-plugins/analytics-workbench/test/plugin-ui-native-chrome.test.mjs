/** Source and compiled CSS must follow DSH tokens, not Vue 44px rectangles. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const stylesSource = await readFile(join(root, 'src/client/styles.ts'), 'utf8');
const css = stylesSource.slice(stylesSource.indexOf('export const css'), stylesSource.lastIndexOf('`;'));
const indexSource = await readFile(join(root, 'src/client/index.tsx'), 'utf8');

test('plugin chrome uses native DSH tokens and does not paint Vue 44px rectangles', () => {
  assert.match(css, /--dsw-font-s-14/);
  assert.match(css, /--dsw-font-base-16/);
  assert.match(css, /--dsw-alias-bg-layer-2/);
  assert.match(css, /--dsw-elevation-prominent/);
  assert.match(css, /--dsw-alias-bg-mask-1/);
  assert.match(css, /--dsw-mask-blur/);
  assert.match(css, /--dsw-alias-border-l3/);
  assert.match(css, /border-radius:24px/);
  assert.match(css, /border-radius:18px/);
  assert.match(css, /min-height:36px/);
  assert.doesNotMatch(css, /min-height:44px/);
  assert.doesNotMatch(css, /#09050D|#805D9D|#F2FFDC/);
  assert.doesNotMatch(css, /Outfit|Alibaba PuHuiTi/);
  assert.match(css, /prefers-reduced-motion: reduce/);
});

test('plugin registers additive business keys and does not occupy native tool names', () => {
  assert.match(indexSource, /key: TOOL_NAME/);
  assert.match(indexSource, /key: QUERY_TOOL_NAME/);
  assert.match(indexSource, /key: FIRST_PURCHASE_TOOL_NAME/);
  assert.doesNotMatch(indexSource, /key: 'bash'/);
  assert.doesNotMatch(indexSource, /key: 'skill'/);
  assert.match(indexSource, /name: 'sidebar.footer.action'/);
  assert.match(indexSource, /name: 'shell.overlay'/);
  assert.doesNotMatch(indexSource, /name: 'sidebar'/);
  assert.doesNotMatch(indexSource, /name: 'conversation'/);
});
