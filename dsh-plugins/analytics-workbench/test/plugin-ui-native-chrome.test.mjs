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
const chromeSource = await readFile(join(root, 'src/client/account-chrome.tsx'), 'utf8');

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
  assert.match(indexSource, /id: 'shine-mage.account.login'/);
  assert.match(indexSource, /id: 'shine-mage.account.theme'/);
  assert.match(indexSource, /name: 'sidebar.footer.action'/);
  assert.match(indexSource, /name: 'shell.overlay'/);
  assert.match(indexSource, /id: 'shine-mage.analytics-b0.generate-cockpit'/);
  assert.match(indexSource, /name: 'conversation.composer.dock', id: 'shine-mage.analytics-b0.generate-cockpit'/);
  assert.match(indexSource, /name: 'sidebar.panellist'/);
  assert.match(indexSource, /name: 'main'/);
  assert.match(indexSource, /name: 'conversation.hero.brand.mark'/);
  assert.doesNotMatch(indexSource, /name: 'conversation.view'/);
  assert.doesNotMatch(indexSource, /name: 'sidebar'(?![\w.])/);
  assert.doesNotMatch(indexSource, /name: 'conversation'(?![\w.])/);
});

test('account chrome frosts the sidebar against a tinted frame and paints chat white', () => {
  assert.match(chromeSource, /:has\(> \[class\*="sidebarCol"\]\) \{/);
  assert.match(chromeSource, /background: #DCDCE1;/);
  assert.match(chromeSource, /rgba\(255, 255, 255, 0\.28\)/);
  assert.match(chromeSource, /backdrop-filter: blur\(40px\) saturate\(1\.15\)/);
  assert.match(chromeSource, /\[class\*="centerCol"\] \{/);
  assert.match(chromeSource, /--dsw-alias-bg-base: #fff;/);
  assert.match(chromeSource, /rgba\(255, 255, 255, 0\.10\)/);
  assert.doesNotMatch(chromeSource, /#e8dff4|#EFEAF6|#cbb8e4|#805D9D/);
  assert.doesNotMatch(chromeSource, /\[class\*="frame"\]/);
  assert.doesNotMatch(chromeSource, /isolation: isolate/);
  assert.doesNotMatch(chromeSource, /\[class\*="sidebarCol"\]::before/);
  assert.match(chromeSource, /停止生成/);
  assert.match(chromeSource, /Stop generating/);
  assert.match(chromeSource, /requestAnimationFrame/);
  assert.match(chromeSource, /\[class\*="footerActions"\]:has\(\.sm-login\[data-wide="0"\]\)/);
  assert.doesNotMatch(chromeSource, /\[class\*="collapsed"\] \[class\*="footerActions"\]/);
  assert.match(chromeSource, /\.sm-login\[data-wide="0"\] \.sm-login-text \{ display:none; \}/);
  assert.match(chromeSource, /writeAccountIdentity/);
  assert.match(chromeSource, /Canvas 86%/);
  assert.match(chromeSource, /未登录/);
  assert.doesNotMatch(css, /composerHero/);
  assert.doesNotMatch(css, /heroWorkspaceRow/);
});
