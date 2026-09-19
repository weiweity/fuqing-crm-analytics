import { useEffect, useRef, type ReactNode } from 'react';
export function CockpitSidebar({ visible, onClose, title = '编辑产物', children, busy = false,
  showBoardTools = false, onLayout, onRollback }: {
  visible: boolean; onClose(): void; title?: string; children?: ReactNode; busy?: boolean;
  showBoardTools?: boolean; onLayout?(): void; onRollback?(): void;
}) {
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!visible) return;
    const previous = document.activeElement as HTMLElement | null, node = panel.current;
    return () => { if (previous?.isConnected && (document.activeElement === document.body || node?.contains(document.activeElement))) previous.focus(); };
  }, [visible]);
  if (!visible) return null;
  return <aside ref={panel} className="cockpit-sidebar" data-testid="cockpit-sidebar" aria-label={title}>
    <div className="cockpit-sidebar-header"><h2>{title}</h2>
      <button type="button" className="cockpit-sidebar-close" data-testid="cockpit-sidebar-close" onClick={onClose} aria-label="关闭侧轨">×</button>
    </div>
    <div className="cockpit-sidebar-body">{children}
      {showBoardTools ? <div className="cockpit-sidebar-tools">
        <button data-testid="layout-start" disabled={busy} onClick={onLayout}>调整布局</button>
        <button data-testid="library-rollback-previous" disabled={busy} onClick={onRollback}>预览回退上一版</button>
      </div> : null}
    </div>
  </aside>;
}
