import { createElement, type ReactElement } from 'react';
import { BoardWorkbench } from './BoardWorkbench.tsx';
import { disposeSelectionUi } from './selection.mjs';
import type { BoardMountProps } from './types.ts';

export function mount(el: HTMLElement, props: BoardMountProps = {}): { dispose(): void } {
  if (!props.createRoot) {
    throw new Error('a6.mount 需要 integrator 注入 createRoot（react-dom/client）。client/index.tsx 由总控装配。');
  }
  const root = props.createRoot(el);
  const node: ReactElement = createElement(BoardWorkbench, props);
  root.render(node);
  return {
    dispose() {
      disposeSelectionUi();
      props.onDispose?.();
      root.unmount();
    },
  };
}
