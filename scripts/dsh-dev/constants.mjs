/** Full DSH base local-dev constants. Not the B0 synthetic verification runner. */

export const PINNED_SHA = '183f08e9c6dde7e36cd2318eaee70b0da08fb35e';
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

/** Competition-track reserved listeners. Vite is documented only; dsh-dev never binds it. */
export const COMPETITION_WEB_PORT = 14327;
export const COMPETITION_VITE_PORT = 15173;

/** Local DSH web for this product. 6666 is Chromium-blocked; 6677 is the browser-safe bind. */
export const DEV_WEB_PORT = 6677;

/**
 * Ports Chromium refuses (`net::ERR_UNSAFE_PORT`). A listener here works with curl
 * but renders nothing in the browser.
 */
export const BROWSER_BLOCKED_PORTS = Object.freeze([
  1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79, 87, 95,
  101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137, 139, 143, 161,
  179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531, 532, 540, 548, 554, 556, 563,
  587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723, 2049, 3659, 4045, 5060, 5061,
  6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697, 10080,
]);

/** Ports this supervisor may bind as --web-port. Does not include Vite 15173. */
export const ALLOWED_WEB_PORTS = Object.freeze([...PORT_RANGE, COMPETITION_WEB_PORT, DEV_WEB_PORT]);

/** Occupied 4327 is the user DSH demo; diagnose/start must not reuse or stop it. */
export const USER_DEMO_PORTS = Object.freeze([4327]);

/** Foreign listeners this track must never stop or reuse. */
export const FOREIGN_PORTS = Object.freeze([8000, 5173, 4315, 4316, 4317, 4318, 4319]);

export const BRAND_DIGESTS = Object.freeze({
  logoPng: '21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000',
  markSvg: '1bcd095360e42081429d23972e25f8d4a831a241df565d920c020d27aab8f4a8',
  outfitTtf: 'fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade',
});

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
