import test from 'node:test';
import assert from 'node:assert/strict';
import { boardPackEnabled, queryPackEnabled } from '../feature-pack-gate.mjs';

test('query and board packs default on in node', () => {
  const prevQ = process.env.SHINE_QUERY;
  const prevB = process.env.SHINE_BOARD;
  delete process.env.SHINE_QUERY;
  delete process.env.SHINE_BOARD;
  delete globalThis.__SHINE_QUERY__;
  delete globalThis.__SHINE_BOARD__;
  try {
    assert.equal(queryPackEnabled(), true);
    assert.equal(boardPackEnabled(), true);
  } finally {
    if (prevQ === undefined) delete process.env.SHINE_QUERY; else process.env.SHINE_QUERY = prevQ;
    if (prevB === undefined) delete process.env.SHINE_BOARD; else process.env.SHINE_BOARD = prevB;
  }
});

test('SHINE_QUERY=off disables query independently of board', () => {
  const prevQ = process.env.SHINE_QUERY;
  const prevB = process.env.SHINE_BOARD;
  process.env.SHINE_QUERY = 'off';
  delete process.env.SHINE_BOARD;
  try {
    assert.equal(queryPackEnabled(), false);
    assert.equal(boardPackEnabled(), true);
  } finally {
    if (prevQ === undefined) delete process.env.SHINE_QUERY; else process.env.SHINE_QUERY = prevQ;
    if (prevB === undefined) delete process.env.SHINE_BOARD; else process.env.SHINE_BOARD = prevB;
  }
});

test('SHINE_BOARD=off disables board independently of query', () => {
  const prevQ = process.env.SHINE_QUERY;
  const prevB = process.env.SHINE_BOARD;
  delete process.env.SHINE_QUERY;
  process.env.SHINE_BOARD = 'off';
  try {
    assert.equal(queryPackEnabled(), true);
    assert.equal(boardPackEnabled(), false);
  } finally {
    if (prevQ === undefined) delete process.env.SHINE_QUERY; else process.env.SHINE_QUERY = prevQ;
    if (prevB === undefined) delete process.env.SHINE_BOARD; else process.env.SHINE_BOARD = prevB;
  }
});
