import { createElement, type ReactElement } from 'react';
import { ActionsWorkbench, type ActionsMountProps } from './ActionsWorkbench.tsx';

export function mount(el: HTMLElement, props: ActionsMountProps = {}): { dispose(): void } {
  if (!props.createRoot) {
    throw new Error('a6.actions.mount 需要 integrator 注入 createRoot（react-dom/client）。client/index.tsx 由总控装配。');
  }
  const root = props.createRoot(el);
  const node: ReactElement = createElement(ActionsWorkbench, props);
  root.render(node);
  return {
    dispose() {
      props.onDispose?.();
      root.unmount();
    },
  };
}
