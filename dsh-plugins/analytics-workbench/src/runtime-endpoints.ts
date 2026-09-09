/** Explicit synthetic port blocks; never accept arbitrary service URLs. */
export function runtimePortBase(): number {
  const raw = process.env.B0_PORT_BASE ?? '4315';
  if (!['4315', '4325', '4335'].includes(raw)) throw new Error('Invalid isolated analytics port block');
  return Number(raw);
}
export function kernelUrl(path: string): string {
  if (!path.startsWith('/internal/native/')) throw new Error('Invalid native kernel path');
  return `http://127.0.0.1:${runtimePortBase()}${path}`;
}
