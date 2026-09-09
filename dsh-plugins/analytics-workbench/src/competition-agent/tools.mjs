/** Method tool metadata and the bounded, explicitly configured HTTP transport. */

import {
  CAPABILITIES_TOOL_NAME, FORBIDDEN_EXPANSIONS, PATCH_TOOL_NAME, REGISTERED_TOOLS,
  RESOURCE_SCHEMA, RESOURCE_TOOL_NAME, STEP_CAPABILITIES, STEP_TOOL_NAME,
} from './family.mjs';

export const TOOL_SPECS = Object.freeze({
  [RESOURCE_TOOL_NAME]: Object.freeze({
    name: RESOURCE_TOOL_NAME,
    description: 'Read one exact registered competition-growth method resource. Examples are not evidence. No filesystem or script capability.',
    parameters: { resource: { type: 'string', required: true } },
  }),
  [CAPABILITIES_TOOL_NAME]: Object.freeze({
    name: CAPABILITIES_TOOL_NAME,
    description: 'Actor-filtered C0 capability catalog. Does not expose old CRM routes. Backend still re-checks.',
    parameters: { request_id: { type: 'string', required: true } },
  }),
  [STEP_TOOL_NAME]: Object.freeze({
    name: STEP_TOOL_NAME,
    description: 'Run one registered diagnosis step against C0 conditions. GSV only. Inherit or explicit change. No arbitrary SQL.',
    parameters: {
      capability_id: { type: 'string', enum: [...STEP_CAPABILITIES], required: true },
      condition_mode: { type: 'string', enum: ['INHERIT', 'EXPLICIT'], required: true },
      request_id: { type: 'string', required: true },
      condition: { type: 'object', additionalProperties: true },
      condition_patch: { type: 'object', additionalProperties: true },
    },
  }),
  [PATCH_TOOL_NAME]: Object.freeze({
    name: PATCH_TOOL_NAME,
    description: 'Plan a controlled board patch for the in-flight selection. STYLE_ONLY does not query. FILTER_CHANGE creates a new run.',
    parameters: {
      intent: { type: 'string', enum: ['STYLE_ONLY', 'FILTER_CHANGE', 'STRUCTURE'], required: true },
      request_id: { type: 'string', required: true },
      selection: { type: 'object', additionalProperties: true },
      payload: { type: 'object', additionalProperties: true },
    },
  }),
});

export function assertRegisteredTool(name) {
  if (!REGISTERED_TOOLS.includes(name) || FORBIDDEN_EXPANSIONS.includes(name)) {
    throw new Error('PROMPT_INJECTION_REFUSED');
  }
}

export async function liveDiagnosisCall(toolName, args = {}, signal) {
  assertRegisteredTool(toolName);
  signal?.throwIfAborted();
  const base = String(process.env.COMPETITION_HTTP_BASE || '').replace(/\/$/, '');
  const token = String(process.env.COMPETITION_HTTP_TOKEN || '');
  if (!base || !token) return liveTransportRefused();
  if (/:(4327|8000|5173)(\/|$)/.test(base)) {
    throw new Error('competition diagnosis HTTP must not target 4327/8000/5173');
  }
  const path = toolName === CAPABILITIES_TOOL_NAME
    ? '/diagnosis/capabilities'
    : toolName === PATCH_TOOL_NAME
      ? '/diagnosis/patch'
      : '/diagnosis/step';
  const response = await fetch(`${base}/api/v1/analytics/competition${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: JSON.stringify(args),
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000),
    redirect: 'error',
  });
  try {
    return await response.json();
  } catch {
    return liveTransportRefused();
  }
}

export function liveTransportRefused() {
  return Object.freeze({
    live_transport: 'NOT_CONNECTED',
    schema_version: 'competition-error/v1',
    error: Object.freeze({
      code: 'NOT_CONNECTED',
      message: 'A3/A5/A8 HTTP 未接线。离线 eval 走 C0 fixture，不访问 4327/8000/5173。',
      retryable: true,
      http_status: 503,
      maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
    }),
  });
}

export { RESOURCE_SCHEMA };
