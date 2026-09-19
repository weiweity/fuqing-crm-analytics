import { useEffect, useState } from 'react';
import './cockpit-theme.css';

const SIDEBAR_MS = 300;

export function CockpitSidebar({
  visible, onClose, busy = false, showBoardTools = false, onLayout, onRollback,
}: {
  visible: boolean;
  onClose: () => void;
  busy?: boolean;
  showBoardTools?: boolean;
  onLayout?: () => void;
  onRollback?: () => void;
}) {
  const [rendered, setRendered] = useState(visible);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (visible) {
      setRendered(true);
      setLeaving(false);
      return;
    }
    if (!rendered) return;
    setLeaving(true);
    const timer = window.setTimeout(() => {
      setRendered(false);
      setLeaving(false);
    }, SIDEBAR_MS);
    return () => window.clearTimeout(timer);
  }, [visible, rendered]);

  if (!rendered) return null;

  return (
    <aside
      className={leaving ? 'cockpit-sidebar cockpit-sidebar-leave' : 'cockpit-sidebar'}
      data-testid="cockpit-sidebar"
      aria-label="编辑侧轨"
      aria-hidden={leaving}
    >
      <div className="cockpit-sidebar-header">
        <button type="button" className="cockpit-sidebar-close" data-testid="cockpit-sidebar-close"
          onClick={onClose} aria-label="关闭侧轨">
          ✕
        </button>
      </div>
      <div className="cockpit-sidebar-body">
        {showBoardTools ? (
          <div className="cockpit-sidebar-tools">
            <button type="button" data-testid="layout-start" disabled={busy} onClick={onLayout}>调整布局</button>
            <button type="button" data-testid="library-rollback-previous" disabled={busy} onClick={onRollback}>回退这一版</button>
          </div>
        ) : null}
      </div>
      <div className="cockpit-sidebar-footer">
        <p className="cockpit-sidebar-placeholder">{showBoardTools
          ? '布局在画布上拖，检查后再确认。'
          : '选中节点或板块后，在此编辑'}</p>
      </div>
    </aside>
  );
}
