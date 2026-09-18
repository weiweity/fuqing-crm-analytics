// Compiler-only free-page contract; not a BoardSpec catalogue.
import type { components } from './page-contract.generated.js';

type Doc = components['schemas']['PageDocument'];
type Patch = components['schemas']['PagePatchPreview'];
type Save = components['schemas']['PageSavePreview'];
type Read = components['schemas']['PageDataReadRequest'];

const pack: Doc['package'] = {
  html: '<!doctype html><html><body><h1>示例</h1></body></html>',
  css: 'h1{font:600 28px/1.3 sans-serif}',
  js: 'void 0',
  resources: [],
  node_map: [],
};
const manifest: Doc['binding_manifest'] = { bindings: [], result_refs: [] };

export const sample: Doc = {
  schema_version: 'free-page/v1',
  page_id: 'page_fixture_unbound',
  session_id: 'native_session_fixture',
  title: '未绑定经营复盘夹具',
  version: 1,
  binding_state: 'UNBOUND_SAMPLE',
  package: pack,
  binding_manifest: manifest,
};

export const d6: Patch = { base_version: 1, package: pack };
// @ts-expect-error D6 omits fields; explicit null is not a patch change.
export const d6NullTitle: Patch = { base_version: 1, package: pack, title: null };
export const d9: Save = {
  base_version: 1,
  title: '显式保存',
  package: pack,
  binding_manifest: manifest,
};
export const read: Read = {
  protocol: 'free-page-bridge/v1',
  instance_id: 'inst_1',
  request_id: 'req_1',
  nonce: 'nonce_1',
  seq: 0,
  op: 'data.read',
  result_ref: 'result_fixture_1',
  mode: 'summary',
  cursor: null,
  limit: 50,
};

export function isUnbound(row: Doc) {
  return row.binding_state === 'UNBOUND_SAMPLE' && row.schema_version === 'free-page/v1';
}

// @ts-expect-error BoardSpec blocks are outside this contract.
export const forgedBlocks: Doc = { ...sample, blocks: [] };
// @ts-expect-error binding_state is a closed enum.
export const forgedState: Doc['binding_state'] = 'BOUND_SAMPLE';
// @ts-expect-error SQL is not a page-to-host op.
export const forgedOp: Read['op'] = 'sql';
// @ts-expect-error exit-edit is not a save operation.
export const exitIsNotSave: components['schemas']['PagePreview']['operation'] = 'EXIT_EDIT';
