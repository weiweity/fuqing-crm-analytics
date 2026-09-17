import type { Context } from '@deepseek-ai/dsh-client-core';

export function apply(_ctx: Context): void {
  (globalThis as { __SHINE_BOARD__?: boolean }).__SHINE_BOARD__ = true;
}
