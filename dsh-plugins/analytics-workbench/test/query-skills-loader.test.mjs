/** Query-family skill loader. Browser NOT RUN. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const load = path => import(pathToFileURL(join(upstream, path, 'lib/index.js')).href);
const { Context } = await load('vendor/cordis');
const { mountAgentLoopTestDependencies } = await load('packages/test-support/agent-loop-testkit');
const { default: AgentLoop } = await load('packages/core/agent-loop');
const { default: SkillRegistry } = await load('packages/skill/skill');
const skillTool = await load('packages/skill/tool-skill');
const { default: ProjectionRegistry } = await load('packages/session/session-projection');
const { default: TokenMeter } = await load('packages/llm/token-meter');
const built = await import(pathToFileURL(join(plugin, 'lib/skills.js')).href);
const sessions = ['session-query-a', 'session-query-b'];

test('query-family Cordis skills register immutable method and deny unknown skill name', async () => {
  const originalFetch = globalThis.fetch;
  const previous = {
    token: process.env.B0_RUNTIME_TOKEN,
    session: process.env.B0_SESSION_ID,
    sessions: process.env.B0_SESSION_IDS,
    family: process.env.B0_RUNTIME_FAMILY,
  };
  process.env.B0_RUNTIME_TOKEN = 'isolated-query-runtime-token-with-no-external-use';
  process.env.B0_RUNTIME_FAMILY = 'channel_followup';
  process.env.B0_SESSION_IDS = sessions.join(',');
  delete process.env.B0_SESSION_ID;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:4315/internal/native/run-context');
    const body = JSON.parse(options.body);
    return Response.json({
      schema_version: 'analytics-channel-followup-runtime-context/v1', session_id: body.session_id, request_id: body.request_id,
      run_id: 'fixture-' + body.request_id, run_status: 'RUNNING', contains_real_data: false,
      versions: { method_package_digest: built.queryMethodPackageDigest, data_digest: 'fixed-data-version' },
      completed_steps: [], remaining_budget: { tool_steps: 6, remaining_ms: 1000 },
      approval_state: 'NOT_AVAILABLE_IN_QUERY_RUN', memory_authority: 'NONE',
    });
  };
  const ctx = new Context();
  try {
    await mountAgentLoopTestDependencies(ctx);
    await ctx.plugin(ProjectionRegistry);
    await ctx.plugin(AgentLoop, { agents: [] });
    await ctx.plugin(TokenMeter);
    await ctx.plugin(SkillRegistry);
    await ctx.plugin(skillTool);
    await ctx.plugin(built);
    const agent = await ctx.agentLoop.create(sessions[0], { provider: 'mock', model: 'mock' });
    assert.deepEqual((await ctx.skills.list({ scope: agent })).map(s => s.name), ['channel-followup-query']);
    assert.deepEqual(ctx.tools.schemas(agent).map(t => t.name).sort(), ['analytics_channel_followup_skill_resource', 'skill']);
    assert.match(built.queryMethodPackageDigest, /^[a-f0-9]{64}$/);
    assert.notEqual(built.queryMethodPackageDigest, built.methodPackageDigest);
  } finally {
    await ctx.fiber.dispose();
    globalThis.fetch = originalFetch;
    if (previous.token === undefined) delete process.env.B0_RUNTIME_TOKEN; else process.env.B0_RUNTIME_TOKEN = previous.token;
    if (previous.session === undefined) delete process.env.B0_SESSION_ID; else process.env.B0_SESSION_ID = previous.session;
    if (previous.sessions === undefined) delete process.env.B0_SESSION_IDS; else process.env.B0_SESSION_IDS = previous.sessions;
    if (previous.family === undefined) delete process.env.B0_RUNTIME_FAMILY; else process.env.B0_RUNTIME_FAMILY = previous.family;
  }
});
