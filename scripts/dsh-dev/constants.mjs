/** Full DSH base local-dev constants. Not the B0 synthetic verification runner. */

export const PINNED_SHA = 'd347e703908d0406b7a7ef80e3a0e594d86b2215';
export const NODE_MAJOR = 24;
export const HOST = '127.0.0.1';

export const PORTS = Object.freeze({
  kernel: 4325,
  bridge: 4326,
  web: 4327,
  gateway: 4328,
  mock: 4329,
});

export const PORT_RANGE = Object.freeze([4325, 4326, 4327, 4328, 4329]);

/** Foreign listeners this track must never stop or reuse. */
export const FOREIGN_PORTS = Object.freeze([8000, 5173, 4315, 4316, 4317, 4318, 4319]);

/**
 * Extra Host-row disables applied by scripts/dsh-b0/serve.mjs.
 * These are synthetic-demo isolation, not upstream product defaults.
 * dsh-dev overlays must not copy them.
 */
export const B0_DEMO_DISABLE_IDS = Object.freeze([
  'session-title-llm',
  'llm-pi-ai',
  'web-search-deepseek',
  'web-fetch-http',
  'session-telemetry-otel',
  'session-log-deepseek',
  'plugin-package-inventory-deepseek',
  'agent-instructions',
  'skill-filesystem',
  'client-hmr',
  'directory-picker',
]);

/** Host rows the web profile is expected to keep addressable (enabled or not). */
export const NATIVE_WEB_IDS = Object.freeze([
  'directory-picker',
  'session-controller',
  'settings-controller',
  'workspace-controller',
  'agent-presets',
  'settings',
  'credentials',
  'llm-deepseek',
  'session-title-llm',
  'skill-filesystem',
  'web-search-deepseek',
  'web-fetch-http',
  'session-title',
  'plugin-inventory',
  'webserver',
  'web-runtime',
  'session',
  'workspace',
]);

export const PLUGIN_UI_ID = 'analytics-workbench-ui';

export const API_KEY_ENV = Object.freeze([
  'DEEPSEEK_API_KEY',
  'OPENAI_API_KEY',
  'ANTHROPIC_API_KEY',
  'B0_MOCK_KEY',
  'OPENROUTER_API_KEY',
]);
