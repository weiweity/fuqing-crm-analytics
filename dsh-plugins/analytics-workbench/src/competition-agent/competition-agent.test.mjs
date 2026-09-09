import test from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { FORBIDDEN_EXPANSIONS, REGISTERED_TOOLS, SKILL_NAME } from './family.mjs';
import { packCompetitionSkill } from './pack-skill.mjs';
import { freezeCompetitionSkillPackage, packageDigest } from './skill-package.mjs';
import { planPatch } from './patch.mjs';
import { selectedEditEvent, bindInFlight } from './selected-edit.mjs';
import { assertRegisteredTool, liveTransportRefused } from './tools.mjs';
import { runOfflineEval } from './offline.mjs';

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

test('competition skill package freezes without numeric evidence', async () => {
  const input = await packCompetitionSkill(plugin);
  const pack = freezeCompetitionSkillPackage(input);
  assert.equal(pack.skillName, SKILL_NAME);
  assert.equal(pack.digest, packageDigest(input.manifest));
  assert.deepEqual(pack.resources, ['assets/result-example.json', 'references/evidence-policy.md']);
  assert.equal(JSON.parse(pack.read('assets/result-example.json').content).numeric_values, null);
  assert.match(pack.definition.content, /不是生产经营 SOP/);
  assert.equal(pack.definition.invocation.userInvocable, false);
});

for (const key of ['../SKILL.md', '/etc/passwd', 'https://example.com/private', 'scripts/run.sh', 'SKILL.md']) {
  test(`resource key denies ${key}`, async () => {
    const pack = freezeCompetitionSkillPackage(await packCompetitionSkill(plugin));
    assert.throws(() => pack.read(key), /not registered/);
  });
}

test('registered tools do not include old routes', () => {
  for (const item of FORBIDDEN_EXPANSIONS) {
    assert.equal(REGISTERED_TOOLS.includes(item), false);
    assert.throws(() => assertRegisteredTool(item), /PROMPT_INJECTION_REFUSED/);
  }
  assert.equal(liveTransportRefused().live_transport, 'NOT_CONNECTED');
});

test('STYLE_ONLY does not query; FILTER_CHANGE is a new run', () => {
  const selection = { board_id: 'dash_c0_board_a', block_id: 'card_c0_block_1', base_version: 4 };
  const style = planPatch({
    intent: 'STYLE_ONLY', payload: { display_op: { op: 'display' } }, selection, inFlight: null,
  });
  assert.equal(style.queries, false);
  assert.equal(style.creates_new_run, false);
  const filter = planPatch({
    intent: 'FILTER_CHANGE',
    payload: { filter_change: { op: 'filter_change', card_id: 'card_c0_block_1', local_filters: { channel_ids: ['A'] } } },
    selection, inFlight: null,
  });
  assert.equal(filter.queries, true);
  assert.equal(filter.creates_new_run, true);
  assert.equal(filter.apply_status, 'NOT_CONNECTED');
});

test('illegal script patch and in-flight selection', () => {
  const selection = { board_id: 'dash_c0_board_a', block_id: 'card_c0_block_1', base_version: 4 };
  assert.throws(() => planPatch({
    intent: 'STYLE_ONLY',
    payload: { display_op: { display_overrides: { title: '<script>x</script>' } } },
    selection, inFlight: null,
  }), /MODEL_INVALID_PATCH/);
  const bound = bindInFlight(selection, { ...selection, block_id: 'card_c0_block_2' });
  assert.equal(bound.ignored_ui_selection, true);
  assert.equal(bound.target.block_id, 'card_c0_block_1');
  const event = selectedEditEvent({ ...selection, intent: 'STYLE_ONLY' });
  assert.equal(event.port_id, 'a7.selected_edit');
});

test('offline python eval suite', () => {
  const report = runOfflineEval();
  assert.equal(report.t13_real_model, 'NOT_RUN');
  assert.deepEqual(report.failed, []);
  assert.equal(report.passed, report.total);
});

test('built native diagnosis tools forward trusted session IDs over model-supplied values', async () => {
  const built = await import(pathToFileURL(resolve(plugin, 'lib/skills.js')).href);
  const keys = ['B0_RUNTIME_FAMILY', 'COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'];
  const previous = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  const originalFetch = globalThis.fetch;
  const requests = [];
  try {
    process.env.B0_RUNTIME_FAMILY = 'competition_growth';
    process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:18082';
    process.env.COMPETITION_HTTP_TOKEN = 'isolated-test-token-no-network';
    globalThis.fetch = async (_url, options) => {
      requests.push(JSON.parse(options.body));
      return Response.json({ live_transport: 'HTTP_CONNECTED' });
    };
    const registered = [];
    built.apply({ skills: { register() {} }, tools: { register(tool) { registered.push(tool); } } });
    const tools = registered.filter(tool => !tool.name.endsWith('_resource'));
    assert.equal(tools.length, 3);
    for (const session_id of ['native_one', 'native_two']) {
      for (const tool of tools) {
        await tool.execute({ request_id: 'request_one', session_id: 'model_cannot_choose' },
          { agent: { session: { id: session_id } } });
      }
    }
    assert.deepEqual(requests.map(body => body.session_id),
      ['native_one', 'native_one', 'native_one', 'native_two', 'native_two', 'native_two']);
  } finally {
    globalThis.fetch = originalFetch;
    for (const key of keys) {
      if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key];
    }
  }
});
