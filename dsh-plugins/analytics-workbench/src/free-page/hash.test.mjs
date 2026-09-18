import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { sha256Hex } from './hash.mjs';

function nodeHex(input) {
  return createHash('sha256').update(input).digest('hex');
}

test('sha256Hex matches node:crypto for empty, ASCII, UTF-8, and JSON payloads', () => {
  const samples = [
    '',
    'abc',
    'html:<h1>标题</h1>\0css:h1{}\0js:',
    JSON.stringify({ shared_css: true, nodes: ['n_title'] }),
    'a'.repeat(64),
    'a'.repeat(65),
    '经营杂志复盘页',
  ];
  for (const sample of samples) {
    assert.equal(sha256Hex(sample), nodeHex(sample), sample.slice(0, 40));
  }
  const bytes = new TextEncoder().encode('bytes');
  assert.equal(sha256Hex(bytes), nodeHex(bytes));
});
