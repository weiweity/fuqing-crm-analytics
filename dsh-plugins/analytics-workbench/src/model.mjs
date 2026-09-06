/** B0 fixture and UI-only preferences. No IO, model, database, or business run. */
export const TOOL_NAME = 'analytics_b0_query';
export const TITLE_STORAGE_KEY = 'shine-mage:analytics-b0:ui-title:v1';
export const DEFAULT_TITLE = '渠道复购 · 合成样例';
export const MAX_TITLE_LENGTH = 40;
export const FIXTURE = Object.freeze({
  schema_version: 'analytics-b0/v1',
  answer_mode: 'STUB',
  data_source: 'SYNTHETIC_FIXTURE',
  fixture_id: 'b0-channel-repeat-2026-09-01',
  data_as_of: '2026-09-01',
  channel: '合成渠道 A',
  customers: 100,
  repeat_customers: 25,
  repeat_rate: 0.25,
});

/** Strict fixture codec, not a production AnalysisResult parser. */
export function decodeFixture(meta) {
  if (!meta || typeof meta !== 'object' || Array.isArray(meta)) return null;
  const keys = Object.keys(FIXTURE);
  if (Object.keys(meta).length !== keys.length) return null;
  return keys.every(key => Object.hasOwn(meta, key) && meta[key] === FIXTURE[key])
    ? { ...FIXTURE }
    : null;
}

export function normalizeTitle(value) {
  if (typeof value !== 'string') throw new Error('标题必须是文字。');
  const title = value.trim();
  if (!title || [...title].length > MAX_TITLE_LENGTH || /[\u0000-\u001f\u007f]/u.test(title)) {
    throw new Error(`标题须为 1–${MAX_TITLE_LENGTH} 个字符，不含控制字符。`);
  }
  return title;
}

export function createEditor(title = DEFAULT_TITLE) {
  const accepted = normalizeTitle(title);
  return { title: accepted, draft: accepted, revision: 0, preview: null };
}

export function changeDraft(editor, draft) {
  return { ...editor, draft, preview: null };
}

export function previewTitle(editor) {
  return {
    ...editor,
    preview: { title: normalizeTitle(editor.draft), baseRevision: editor.revision },
  };
}

export function applyTitle(editor) {
  if (!editor.preview || editor.preview.baseRevision !== editor.revision
    || editor.preview.title !== normalizeTitle(editor.draft)) {
    throw new Error('预览已失效，请重新预览后应用。');
  }
  return { title: editor.preview.title, draft: editor.preview.title, revision: editor.revision + 1, preview: null };
}

/** Serialize only a cosmetic title. Never cache the fixture or model output. */
export function serializeTitle(title) {
  return JSON.stringify({ schema_version: 'analytics-b0-ui/v1', title: normalizeTitle(title) });
}

export function restoreTitle(raw) {
  if (raw === null) return { title: DEFAULT_TITLE, restored: false, invalid: false };
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).length !== 2 || value.schema_version !== 'analytics-b0-ui/v1') {
      throw new Error('unsupported UI preference');
    }
    return { title: normalizeTitle(value.title), restored: true, invalid: false };
  } catch {
    return { title: DEFAULT_TITLE, restored: false, invalid: true };
  }
}

/** Respect cancellation even though this B0 result is immediate and deterministic. */
export async function executeFixture(query, signal) {
  signal.throwIfAborted();
  if (query !== 'channel_repeat_rate') throw new Error('B0_UNSUPPORTED_QUERY');
  return { ...FIXTURE };
}
