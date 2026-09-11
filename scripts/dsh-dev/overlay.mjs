/** Optional business-plugin overlay. Does not copy B0 demo disables. */
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { join } from 'node:path';
import { B0_DEMO_DISABLE_IDS, PLUGIN_UI_ID } from './constants.mjs';

export function pluginEnabled(value) {
  if (value === true || value === 'on') return true;
  if (value === false || value === 'off' || value === undefined) return false;
  throw new Error('Usage: --plugin on|off');
}

export async function assertPluginRoot(pluginRoot) {
  assert.ok(pluginRoot && pluginRoot.startsWith('/'), 'plugin path must be absolute');
  await access(join(pluginRoot, 'lib/index.js'));
  await access(join(pluginRoot, 'package.json'));
  return pluginRoot;
}

/**
 * Native dev overlay: the brand-assets row only.
 *
 * The business plugin installs through `dsh plugin add` as a profile bundle
 * (`@shine-mage/dsh-analytics-workbench-b0`), so this overlay must not insert
 * a second `analytics-workbench-ui` row: two rows share the id and the later
 * one wins, which would silently shadow the installed bundle with a stale
 * copied artifact.
 *
 * The brand-assets row stays here because it resolves repository paths
 * (logo, favicon, Outfit font) outside any publishable package.
 */
export function buildPluginOverlay(pluginRoot) {
  if (pluginRoot !== undefined) {
    assert.ok(pluginRoot.startsWith('/'), 'plugin path must be absolute');
  }
  const rows = [{ id: 'analytics-dev-brand-assets', name: new URL('./brand.mjs', import.meta.url).href }];
  const patch = [{ insert: rows }];
  assertNoB0Disables(patch);
  return patch;
}

/**
 * `--plugin off` layer: switch the installed bundle row off by id.
 * The bundle is a persistent profile layer; dropping the brand overlay is not enough.
 */
export function buildPluginDisable() {
  const patch = [{ id: PLUGIN_UI_ID, disabled: true }];
  assertNoB0Disables(patch);
  return patch;
}

/** Presence alone cannot tell off from on: off keeps the row and sets disabled. */
export function pluginRowState(dump) {
  const lines = String(dump).split('\n');
  const start = lines.findIndex(line => line.trim() === `- id: ${PLUGIN_UI_ID}`);
  if (start === -1) return { present: false, disabled: false };
  let disabled = false;
  for (const line of lines.slice(start + 1)) {
    if (/^- /.test(line)) break;
    if (/^\s+disabled:\s*true\s*$/.test(line)) disabled = true;
  }
  return { present: true, disabled };
}

export function assertNoB0Disables(patch) {
  const disabled = new Set();
  const visit = (value) => {
    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }
    if (!value || typeof value !== 'object') return;
    if (typeof value.id === 'string' && value.disabled === true) disabled.add(value.id);
    for (const item of Object.values(value)) visit(item);
  };
  visit(patch);
  for (const id of B0_DEMO_DISABLE_IDS) {
    assert.equal(disabled.has(id), false, `dsh-dev overlay must not disable native row ${id}`);
  }
}

export { B0_DEMO_DISABLE_IDS, PLUGIN_UI_ID };
