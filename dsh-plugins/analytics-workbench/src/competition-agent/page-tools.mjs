/** Native page-package delivery tool. Delivery only: no SQL, token, or outbound HTTP. */
import { parsePagePackage } from '../free-page/contract/schema.mjs';
import { PAGE_GENERATE_TOOL_NAME, PAGE_REQUEST_ID_PATTERN, PAGE_TOOL_RESULT_SCHEMA } from './page-family.mjs';

const identity = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
const refused = (code, message) => ({ schema_version: PAGE_TOOL_RESULT_SCHEMA, status: 'REFUSED', error: { code, message } });

export const PAGE_TOOL_PARAMETERS = Object.freeze({
  [PAGE_GENERATE_TOOL_NAME]: {
    request_id: {
      type: 'string', required: true,
      description: 'Copy the page-gen request id from the user message verbatim; never invent one.',
    },
    package: {
      type: 'object', required: true, additionalProperties: false, properties: {
        html: { type: 'string', required: true },
        css: { type: 'string' },
        js: { type: 'string' },
        resources: { type: 'array', items: { type: 'object', additionalProperties: true } },
        node_map: { type: 'array', items: { type: 'object', additionalProperties: true } },
      },
      description: 'One free-page/v1 source package authored in this reply. Free HTML/CSS/JS; not a BoardSpec. Page scripts may only read data the user explicitly authorized in this session.',
    },
  },
});

export async function executePageTool(name, args, execution) {
  if (name !== PAGE_GENERATE_TOOL_NAME) throw new Error('UNREGISTERED_PAGE_TOOL');
  execution.signal?.throwIfAborted();
  const sessionId = execution.agent?.session?.id;
  if (!identity(sessionId)) return refused('SESSION_REQUIRED', '需要当前原生会话，不接受模型指定的会话。');
  if (!args || typeof args !== 'object' || Array.isArray(args)) {
    return refused('INVALID_REQUEST', '页面工具参数必须为对象。');
  }
  if (typeof args.request_id !== 'string' || !PAGE_REQUEST_ID_PATTERN.test(args.request_id)) {
    return refused('INVALID_REQUEST', 'request_id 必须逐字复制用户消息中的 page-gen 标识。');
  }
  const pack = parsePagePackage(args.package);
  if (!pack.ok) {
    return { ...refused(pack.error.code, `${pack.error.message}。仅按本次错误修正页面源码包后重提一次；不得使用 bash、文件、脚本或其他工具排查，不得回退到示例页面。`),
      next_action: '仅修正 package 字段后重新调用本工具一次。' };
  }
  // Delivery receipt only. Persisting the page (isolated documents HTTP) stays
  // with the browser workbench; this tool never writes or forwards the package.
  return {
    schema_version: PAGE_TOOL_RESULT_SCHEMA,
    status: 'PACKAGE_RECEIVED',
    request_id: args.request_id,
    session_id: sessionId,
    package: pack.value,
    published: false,
    next_action: '页面源码包已交付工作台；由用户在工作台检查并保存，本工具不保存页面。',
  };
}
