/** Selection-only bridge. The untrusted frame can never request a write. */
import { buildSrcdoc } from '../free-page/preview/srcdoc-builder.mjs';
import { buildSourceIndex } from '../free-page/source-index/index.mjs';

export function editableTextNodes(pkg, manifest) {
  if (!pkg) return [];
  const index = buildSourceIndex(pkg);
  const bound = new Set((manifest?.bindings ?? []).map(row => row.node_id));
  return Object.values(index.nodes).filter(node => node.kind === 'static_element' && !bound.has(node.node_id)
    && !node.js_ranges.length && !/<[a-z!/]/i.test(node.html_range.inner_text)).map(node => ({
      node_id: node.node_id, kind: node.kind, mapping: 'valid',
      mapping_token: node.mapping_token, version_hash: index.version_hash,
      text: node.html_range.inner_text, tag: node.tag,
    }));
}

function selectionRuntime(config) {
  const send = nodeId => parent.postMessage({ type: 'cockpit.selection', channel: config.channel,
    pageId: config.pageId, version: config.version, nodeId }, '*');
  const install = () => {
    const allowed = new Set(config.ids);
    const style = document.createElement('style');
    style.textContent = '[data-cockpit-target]{cursor:text!important;outline-offset:3px} [data-cockpit-target]:hover,[data-cockpit-target]:focus-visible{outline:1px dashed #ff6b35!important} [data-cockpit-target][data-cockpit-selected]{outline:2px solid #ff6b35!important;outline-offset:3px}';
    document.head.append(style);
    for (const node of document.querySelectorAll('[data-shine-node]')) {
      const id = node.getAttribute('data-shine-node');
      if (!allowed.has(id)) continue;
      node.setAttribute('data-cockpit-target', '');
      node.tabIndex = 0;
      if (id === config.selected) node.setAttribute('data-cockpit-selected', '');
    }
    window.addEventListener('message', event => {
      const data = event.data;
      if (event.source !== parent || data?.type !== 'cockpit.highlight' || data.channel !== config.channel
        || data.pageId !== config.pageId || data.version !== config.version) return;
      for (const node of document.querySelectorAll('[data-cockpit-target]')) {
        if (node.getAttribute('data-shine-node') === data.nodeId) node.setAttribute('data-cockpit-selected', '');
        else node.removeAttribute('data-cockpit-selected');
      }
    });
    document.addEventListener('click', event => {
      event.preventDefault(); event.stopImmediatePropagation();
      const node = event.target.closest?.('[data-cockpit-target]');
      if (node) send(node.getAttribute('data-shine-node'));
    }, true);
    document.addEventListener('submit', event => { event.preventDefault(); event.stopImmediatePropagation(); }, true);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); send(null); }
      if (event.key === 'Enter' && event.target.matches?.('[data-cockpit-target]')) {
        event.preventDefault(); event.stopImmediatePropagation(); send(event.target.getAttribute('data-shine-node'));
      }
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
}
export function selectionSrcdoc(pkg, { channel, pageId, version, nodes = [], selected = null, editing = false }) {
  const src = buildSrcdoc({ ...pkg, instanceId: channel, pageId, version, nonce: channel });
  if (!editing) return src;
  const config = JSON.stringify({ channel, pageId, version, ids: nodes.map(row => row.node_id), selected }).replace(/</g, '\\u003c');
  return src.replace('</body>', '<script>(' + selectionRuntime.toString() + ')(' + config + ');</script></body>');
}
export function acceptSelection(event, { source, channel, pageId, version, nodes }) {
  if (!source || event.source !== source || event.origin !== 'null') return undefined;
  const data = event.data;
  if (!data || data.type !== 'cockpit.selection' || data.channel !== channel || data.pageId !== pageId || data.version !== version) return undefined;
  if (Object.keys(data).some(key => !['type','channel','pageId','version','nodeId'].includes(key))) return undefined;
  if (data.nodeId === null) return null;
  return nodes.find(node => node.node_id === data.nodeId);
}
