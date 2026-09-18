/** Source offsets for data-shine-* markers. No HTML parser dependency. */

const START_TAG = /<([A-Za-z][\w:-]*)(\s[^>]*?)?(\/?)>/g;
const NODE_ATTR = /data-shine-node\s*=\s*(["'])([^"']+)\1/i;
const REGION_ATTR = /data-shine-region\s*=\s*(["'])([^"']+)\1/i;
const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);

function escapeRe(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function closeRange(html, tag, from) {
  const open = new RegExp(`<${escapeRe(tag)}\\b`, 'gi');
  const close = new RegExp(`<\\/${escapeRe(tag)}\\s*>`, 'gi');
  let depth = 1;
  let cursor = from;
  while (cursor < html.length) {
    open.lastIndex = cursor;
    close.lastIndex = cursor;
    const nextOpen = open.exec(html);
    const nextClose = close.exec(html);
    if (!nextClose) return null;
    if (nextOpen && nextOpen.index < nextClose.index) {
      depth += 1;
      cursor = nextOpen.index + nextOpen[0].length;
      continue;
    }
    depth -= 1;
    if (depth === 0) {
      return { inner_end: nextClose.index, end: nextClose.index + nextClose[0].length };
    }
    cursor = nextClose.index + nextClose[0].length;
  }
  return null;
}

export function scanShineMarkers(html) {
  if (typeof html !== 'string') return [];
  const found = [];
  START_TAG.lastIndex = 0;
  let match;
  while ((match = START_TAG.exec(html))) {
    const attrs = match[2] ?? '';
    const node = attrs.match(NODE_ATTR);
    const region = attrs.match(REGION_ATTR);
    if (!node && !region) continue;
    const tag = match[1].toLowerCase();
    const start = match.index;
    const inner_start = match.index + match[0].length;
    const selfClosing = match[3] === '/' || VOID.has(tag);
    let inner_end = inner_start;
    let end = inner_start;
    if (selfClosing) {
      end = inner_start;
    } else {
      const closed = closeRange(html, tag, inner_start);
      if (!closed) continue;
      inner_end = closed.inner_end;
      end = closed.end;
    }
    if (node) {
      found.push(Object.freeze({
        attr: 'node',
        node_id: node[2],
        tag,
        start,
        inner_start,
        inner_end,
        end,
      }));
    }
    if (region) {
      found.push(Object.freeze({
        attr: 'region',
        node_id: region[2],
        tag,
        start,
        inner_start,
        inner_end,
        end,
      }));
    }
  }
  return found;
}

export function parseCssRules(css) {
  if (typeof css !== 'string' || !css) return [];
  const rules = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let match;
  while ((match = re.exec(css))) {
    rules.push(Object.freeze({
      selector: match[1].trim(),
      body: match[2],
      start: match.index,
      end: match.index + match[0].length,
      text: match[0],
    }));
  }
  return rules;
}

function braceBlock(css, from) {
  let depth = 0;
  let started = false;
  for (let i = from; i < css.length; i += 1) {
    if (css[i] === '{') {
      depth += 1;
      started = true;
    } else if (css[i] === '}') {
      depth -= 1;
      if (started && depth === 0) return css.slice(from, i + 1);
    }
  }
  return css.slice(from);
}

export function partitionCss(css) {
  const text = typeof css === 'string' ? css : '';
  const atBlocks = [];
  const remainder = [];
  const at = /@(media|supports|layer|keyframes|font-face)\b/gi;
  let last = 0;
  let match;
  while ((match = at.exec(text))) {
    remainder.push(text.slice(last, match.index));
    const block = braceBlock(text, match.index);
    atBlocks.push(block);
    last = match.index + block.length;
    at.lastIndex = last;
  }
  remainder.push(text.slice(last));
  return Object.freeze({
    atBlocks: Object.freeze(atBlocks),
    rules: parseCssRules(remainder.join('')),
  });
}

export function mergeRanges(ranges) {
  const sorted = [...ranges].filter(range => range && range.end > range.start)
    .sort((a, b) => a.start - b.start || a.end - b.end);
  const out = [];
  for (const range of sorted) {
    const last = out[out.length - 1];
    if (!last || range.start > last.end) out.push({ start: range.start, end: range.end });
    else last.end = Math.max(last.end, range.end);
  }
  return out;
}

export function unownedParts(source, ranges) {
  const merged = mergeRanges(ranges);
  const parts = [];
  let pos = 0;
  for (const range of merged) {
    parts.push(source.slice(pos, range.start));
    pos = range.end;
  }
  parts.push(source.slice(pos));
  return parts;
}

export function proposedKeepsUnowned(original, proposed, ranges) {
  if (original === proposed) return true;
  if (!ranges.length) return false;
  const parts = unownedParts(original, ranges);
  let rest = proposed;
  if (!rest.startsWith(parts[0])) return false;
  rest = rest.slice(parts[0].length);
  for (let i = 1; i < parts.length; i += 1) {
    const part = parts[i];
    if (part === '') {
      if (i === parts.length - 1) return true;
      continue;
    }
    const index = rest.indexOf(part);
    if (index < 0) return false;
    rest = rest.slice(index + part.length);
  }
  return rest === '';
}

export function jsMentions(js, needles) {
  if (typeof js !== 'string' || !js) return [];
  const ranges = [];
  for (const needle of needles) {
    if (!needle) continue;
    let from = 0;
    while (from < js.length) {
      const index = js.indexOf(needle, from);
      if (index < 0) break;
      let lineStart = js.lastIndexOf('\n', index - 1) + 1;
      let lineEnd = js.indexOf('\n', index);
      if (lineEnd < 0) lineEnd = js.length;
      ranges.push(Object.freeze({ start: lineStart, end: lineEnd, needle }));
      from = index + needle.length;
    }
  }
  return ranges;
}

export function replaceRange(source, start, end, next) {
  return source.slice(0, start) + next + source.slice(end);
}
