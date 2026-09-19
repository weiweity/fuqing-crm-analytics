import { useEffect } from 'react';
import { attachHoverToIframe, resolveIframe } from './html-hover-layer.mjs';

export type HtmlHoverLayerProps = {
  iframeRef: { current: HTMLIFrameElement | HTMLElement | null };
  editMode: boolean;
};

export function HtmlHoverLayer({ iframeRef, editMode }: HtmlHoverLayerProps) {
  useEffect(() => {
    if (!editMode) return undefined;
    const root = iframeRef.current;
    if (!root) return undefined;
    let stop = attachHoverToIframe(root);
    let current = resolveIframe(root);
    const observer = typeof MutationObserver === 'function'
      ? new MutationObserver(() => {
        const next = resolveIframe(root);
        if (next === current) return;
        current = next;
        stop();
        stop = attachHoverToIframe(root);
      })
      : null;
    observer?.observe(root, { childList: true, subtree: true });
    return () => {
      observer?.disconnect();
      stop();
    };
  }, [editMode, iframeRef]);

  if (!editMode) return null;
  return <span data-testid="html-hover-layer" hidden />;
}
