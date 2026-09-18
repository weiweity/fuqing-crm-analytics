import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { ANTI_TEMPLATE, buildGenerateContext, SHINE_INVARIANTS, themeValueCopy } from './generate-context.mjs';

const tokens = await readFile(join(fileURLToPath(new URL('../competition-shell/tokens.ts', import.meta.url))), 'utf8');

test('generate context always carries SHINE invariants and never a component whitelist', () => {
  const none = buildGenerateContext({ prompt: '做一张复盘页' });
  assert.equal(none.schema_version, 'free-page-generate-context/v1');
  assert.equal(none.nativeRuntime, 'dsh-native-agent-only');
  assert.ok(SHINE_INVARIANTS.every(item => none.invariants.includes(item)));
  assert.ok(ANTI_TEMPLATE.length >= 2);
  assert.equal(none.claimedFollowed.designGuide, false);
  assert.equal(none.claimedFollowed.skill, false);
  assert.doesNotMatch(JSON.stringify(none), /COMPONENT_CATALOG|只能使用下列组件/);
  assert.match(none.invariants.join(''), /自由 HTML/);
});

test('DESIGN.md and skill are optional and must not be claimed when unread', () => {
  const withDesign = buildGenerateContext({
    prompt: 'x',
    designGuide: { kind: 'design.md', loaded: true, excerpt: '首屏用杂志排版' },
  });
  assert.equal(withDesign.claimedFollowed.designGuide, true);
  assert.equal(withDesign.designGuide.excerpt, '首屏用杂志排版');
  const unread = buildGenerateContext({
    prompt: 'x',
    designGuide: { kind: 'design.md', loaded: false, error: 'offline' },
    skill: { loaded: false },
  });
  assert.equal(unread.claimedFollowed.designGuide, false);
  assert.equal(unread.claimedFollowed.skill, false);
  assert.match(unread.designGuide.error, /不能声称已遵循/);
  const both = buildGenerateContext({
    prompt: 'x',
    designGuide: { loaded: true, excerpt: 'DESIGN' },
    skill: { loaded: true, excerpt: 'skill-brief' },
  });
  assert.equal(both.claimedFollowed.designGuide, true);
  assert.equal(both.claimedFollowed.skill, true);
});

test('theme value copy matches competition-shell declared Noto stack and is not PuHuiTi default', () => {
  const copy = themeValueCopy('dark');
  assert.match(copy.font.body, /Noto Sans SC/);
  assert.doesNotMatch(copy.font.body, /PuHuiTi/);
  assert.match(tokens, /Noto Sans SC/);
  assert.match(tokens, /candidateChinese/);
  assert.doesNotMatch(tokens.slice(tokens.indexOf('body:')), /^[\s\S]*body: "'Alibaba PuHuiTi/);
  assert.equal(copy.color.purpleEmphasisOnly, '#805D9D');
  assert.match(copy.note, /Not a second palette/);
});
