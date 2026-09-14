/** Pure, non-executing diagram content. Dates are calendar days, not inferred timestamps. */
export function validCalendarDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

export function structuredContentError(kind, props) {
  const items = kind === 'PROCESS' ? props.nodes : kind === 'TIMELINE' ? props.events : null;
  if (items && new Set(items.map(item => item.id)).size !== items.length) return '节点或事件 ID 不能重复';
  if (kind === 'PROCESS' && props.nodes && props.edges) {
    const ids = new Set(props.nodes.map(node => node.id));
    if (props.edges.some(edge => !ids.has(edge.from) || !ids.has(edge.to))) return '流程连线指向不存在的节点';
    const edges = props.edges.map(edge => JSON.stringify([edge.from, edge.to, edge.label ?? '']));
    if (new Set(edges).size !== edges.length) return '流程不能重复登记相同连线';
  }
  return null;
}

/** Deterministic directed diagram. Side lanes keep every edge outside all node boxes.
 * Node order is document order, not an inferred executable/topological sequence.
 * Overlapping edge intervals never share a lane; cycles and self-loops remain explicit.
 */
export function processGeometry(content) {
  const issue = structuredContentError('PROCESS', content);
  if (issue) throw new Error(issue);
  const indices = new Map(content.nodes.map((node, index) => [node.id, index]));
  const lanes = { left: [], right: [] };
  const routes = content.edges.map((edge, index) => {
    const from = indices.get(edge.from), to = indices.get(edge.to);
    const side = to > from ? 'left' : 'right';
    const low = Math.min(from, to), high = Math.max(from, to);
    let lane = lanes[side].findIndex(intervals => intervals.every(([a, b]) => high < a || low > b));
    if (lane < 0) { lane = lanes[side].length; lanes[side].push([]); }
    lanes[side][lane].push([low, high]);
    return { ...edge, index, fromIndex: from, toIndex: to, side, lane };
  });
  const nodeX = 32 + lanes.left.length * 28, nodeWidth = 220;
  const nodes = content.nodes.map((node, index) => ({ ...node, number: index + 1, x: nodeX, y: 20 + index * 84, w: nodeWidth, h: 52 }));
  const byId = new Map(nodes.map(node => [node.id, node]));
  // Separate the incoming/outgoing endpoints at each node, including self-loops.
  const ports = new Map();
  for (const route of routes) for (const end of ['from', 'to']) {
    const key = `${route[end]}:${route.side}`;
    if (!ports.has(key)) ports.set(key, []);
    ports.get(key).push(`${route.index}:${end}`);
  }
  const portY = (route, end) => {
    const node = byId.get(route[end]), siblings = ports.get(`${route[end]}:${route.side}`);
    return node.y + (siblings.indexOf(`${route.index}:${end}`) + 1) * node.h / (siblings.length + 1);
  };
  return { width: nodeX + nodeWidth + 32 + lanes.right.length * 28,
    height: Math.max(92, nodes.length * 84 + 8), nodes,
    edges: routes.map(route => {
      const x = route.side === 'left' ? nodeX : nodeX + nodeWidth;
      const laneX = x + (route.side === 'left' ? -1 : 1) * (route.lane + 1) * 28;
      const fromY = portY(route, 'from'), toY = portY(route, 'to');
      return { from: route.from, to: route.to, label: route.label ?? '', number: route.index + 1,
        side: route.side, lane: route.lane, x: laneX, y: (fromY + toY) / 2,
        path: `M ${x} ${fromY} H ${laneX} V ${toY} H ${x}` };
    }) };
}

/** Same-day events share a marker. Nearby markers use separate lanes, never fake date spacing. */
export function timelineGeometry(events) {
  if (events.some(event => !validCalendarDate(event.date))) throw new Error('时间线含无效日期');
  const sorted = [...events].sort((a, b) => a.date.localeCompare(b.date));
  const groups = [];
  for (const event of sorted) {
    const previous = groups.at(-1);
    if (previous?.date === event.date) previous.events.push({ ...event });
    else groups.push({ date: event.date, events: [{ ...event }] });
  }
  if (!groups.length) return { groups: [], lanes: 0 };
  const day = date => Date.parse(`${date}T00:00:00Z`) / 86400000;
  const first = day(groups[0].date), span = day(groups.at(-1).date) - first;
  const ends = [];
  return { groups: groups.map((group, index) => {
    const position = span ? (day(group.date) - first) / span : .5;
    let lane = ends.findIndex(end => position - end >= .085);
    if (lane < 0) lane = ends.length;
    ends[lane] = position;
    return { ...group, position, lane, number: index + 1 };
  }), get lanes() { return ends.length; } };
}
