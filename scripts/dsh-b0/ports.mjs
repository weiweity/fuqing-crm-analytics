import assert from 'node:assert/strict';
export function portBlock(value = 4315) {
  assert.ok([4315, 4325, 4335].includes(value), 'port base must be 4315, 4325 or 4335');
  return { kernel: value, bridge: value + 1, web: value + 2, gateway: value + 3, mock: value + 4 };
}
export function currentPorts(current) {
  const ports = portBlock(current.portBase ?? 4315);
  assert.equal(current.webPort, ports.web);
  assert.equal(current.mockPort, ports.mock);
  return ports;
}
