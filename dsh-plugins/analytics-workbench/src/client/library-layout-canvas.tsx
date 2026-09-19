import { useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent, PointerEvent as ReactPointerEvent } from 'react';
import { GRID, gestureBox, gridMetrics, validatePlacement } from '../board-spec/grid-layout.mjs';
import type { GridBlock, GridBox, GridMetrics } from '../board-spec/grid-layout.mjs';
import { interpretBoard } from '../board-spec/interpret.mjs';
import { LibraryComponentBody, libraryComponentCss } from './library-components.tsx';
import type { LibrarySnapshot } from './library-board-client.mjs';

const css = `
.sm-layout-surface { container:sm-layout / inline-size; min-width:0; }
.sm-layout-scroll { overflow:auto; min-height:160px; max-height:65vh; overscroll-behavior:contain; scrollbar-gutter:stable; position:relative; }
/* The following ghost must not create scrollable columns/rows outside the grid. */
.sm-layout-grid { display:grid; position:relative; min-width:560px; isolation:isolate; overflow:clip; }
.sm-layout-block { min-width:0; min-height:0; overflow:auto; border:1px solid var(--sm-line); border-radius:8px; padding:16px; background:var(--sm-surface,var(--sm-bg)); }
.sm-layout-block h2 { margin:0 0 12px; font-size:14px; font-weight:500; overflow-wrap:anywhere; }
.sm-layout-block[data-active=true] { outline:2px solid var(--sm-purple); outline-offset:-2px; }
.sm-layout-handles { display:flex; gap:8px; justify-content:space-between; margin-bottom:12px; flex-wrap:wrap; }
.sm-layout-handles button { touch-action:none; user-select:none; font-size:12px; }
.sm-layout-handles [data-layout-mode=move] { cursor:grab; }
.sm-layout-handles [data-layout-mode=resize] { cursor:nwse-resize; }
.sm-layout-target { position:absolute; border:2px dashed var(--sm-purple); box-sizing:border-box; pointer-events:none; z-index:2; }
.sm-layout-target[data-valid=false] { border-color:var(--sm-danger); }
.sm-layout-ghost { position:absolute; border:2px solid var(--sm-purple); background:var(--sm-bg); opacity:.65; box-sizing:border-box; padding:12px; overflow:hidden; pointer-events:none; z-index:3; }
.sm-layout-status { min-height:1.5em; font-size:12px; }
@container sm-layout (max-width:560px) {
  .sm-layout-grid[data-editing=false] { display:flex; flex-direction:column; min-width:0; }
  .sm-layout-grid[data-editing=false] .sm-layout-block { min-height:160px; max-height:480px; }
}
`;

type Mode = 'move' | 'resize';
type Gesture = { block: GridBlock; mode: Mode; metrics: GridMetrics; pointer: number; button: HTMLButtonElement;
  startX: number; startY: number; x: number; y: number; scrollX: number; scrollY: number; regionX: number; regionY: number };
type DragView = { block: GridBlock; mode: Mode; metrics: GridMetrics; box: GridBox; dx: number; dy: number; valid: boolean };
const description = (box: GridBox) => `第 ${box.x + 1} 列，第 ${box.y + 1} 行，宽 ${box.w} 列，高 ${box.h} 行`;
const boxStyle = (box: GridBox, metrics: GridMetrics): CSSProperties => ({ left: box.x * metrics.columnPitch,
  top: box.y * metrics.rowPitch, width: box.w * metrics.columnPitch - metrics.gap, height: box.h * metrics.rowPitch - metrics.gap });

/** A panel can extend below the window or be clipped by the native shell. Only
 * its visible client area is a reachable drag edge (not its off-screen border). */
function visibleScrollBounds(region: HTMLElement) {
  const clientRect = (element: HTMLElement) => {
    const rect = element.getBoundingClientRect(), left = rect.left + element.clientLeft, top = rect.top + element.clientTop;
    return { left, top, right: left + element.clientWidth, bottom: top + element.clientHeight };
  };
  const rect = clientRect(region), viewport = window.visualViewport;
  rect.left = Math.max(rect.left, viewport?.offsetLeft ?? 0);
  rect.top = Math.max(rect.top, viewport?.offsetTop ?? 0);
  rect.right = Math.min(rect.right, viewport ? viewport.offsetLeft + viewport.width : window.innerWidth);
  rect.bottom = Math.min(rect.bottom, viewport ? viewport.offsetTop + viewport.height : window.innerHeight);
  for (let parent = region.parentElement; parent; parent = parent.parentElement) {
    const style = window.getComputedStyle(parent), bounds = clientRect(parent);
    if (/^(auto|scroll|hidden|clip)$/.test(style.overflowX)) {
      rect.left = Math.max(rect.left, bounds.left); rect.right = Math.min(rect.right, bounds.right);
    }
    if (/^(auto|scroll|hidden|clip)$/.test(style.overflowY)) {
      rect.top = Math.max(rect.top, bounds.top); rect.bottom = Math.min(rect.bottom, bounds.bottom);
    }
  }
  return rect;
}

/** Pointer gestures only edit a local draft. The parent owns server preview and confirmation. */
export function LibraryLayoutCanvas({ snapshot, editing = false, disabled = false, updateLayout, selectedBlockId, selectBlock }: {
  snapshot: LibrarySnapshot; editing?: boolean; disabled?: boolean; updateLayout?(id: string, box: GridBox): void;
  selectedBlockId?: string; selectBlock?(id: string): void;
}) {
  const scroll = useRef<HTMLDivElement>(null), grid = useRef<HTMLDivElement>(null);
  const active = useRef<Gesture | null>(null);
  const latest = useRef({ snapshot, editing, disabled, updateLayout });
  latest.current = { snapshot, editing, disabled, updateLayout };
  const [drag, setDrag] = useState<DragView | null>(null), [message, setMessage] = useState('');
  const helpId = useId();
  const controller = useRef<{ cancel(): void; paint(): void } | null>(null);

  useEffect(() => {
    let frame = 0, lastTime = 0;
    const currentView = (): DragView | null => {
      const gesture = active.current, region = scroll.current;
      if (!gesture || !region) return null;
      // Pointer coordinates are viewport-relative. An ancestor can move the whole
      // canvas without changing its own scroll offsets (e.g. page/DSH panel scroll).
      const rect = region.getBoundingClientRect();
      const dx = gesture.x - gesture.startX + region.scrollLeft - gesture.scrollX + gesture.regionX - rect.left;
      const dy = gesture.y - gesture.startY + region.scrollTop - gesture.scrollY + gesture.regionY - rect.top;
      const box = gestureBox(gesture.block, gesture.mode, dx, dy, gesture.metrics);
      const placement = validatePlacement(latest.current.snapshot.spec.blocks, gesture.block.block_id, box);
      return { ...gesture, box, dx, dy, valid: placement.ok };
    };
    const paint = () => {
      const view = currentView();
      if (!view) return;
      setDrag(view);
      const placement = validatePlacement(latest.current.snapshot.spec.blocks, view.block.block_id, view.box);
      setMessage(placement.ok ? `${description(view.box)}。松开后暂存到布局草稿。` : placement.message);
    };
    const stop = (cancelled: boolean, reason = '') => {
      const gesture = active.current, view = currentView();
      if (!gesture) return;
      active.current = null;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0; lastTime = 0;
      if (gesture.button.hasPointerCapture?.(gesture.pointer)) gesture.button.releasePointerCapture(gesture.pointer);
      setDrag(null);
      if (cancelled || !latest.current.editing || latest.current.disabled) {
        setMessage(`${reason}已取消本次手势，布局草稿保持原样。`); return;
      }
      if (!view) return;
      const placement = validatePlacement(latest.current.snapshot.spec.blocks, gesture.block.block_id, view.box);
      if (!placement.ok) { setMessage(placement.message); return; }
      latest.current.updateLayout?.(gesture.block.block_id, placement.value);
      setMessage(`${gesture.block.title}：${description(view.box)}。尚未保存。`);
    };
    // Pointer capture handles leaving a card; scrolling uses the same pointer origin and grid pitch.
    const autoScroll = (time: number) => {
      const gesture = active.current, region = scroll.current;
      if (!gesture || !region) { frame = 0; return; }
      const rect = visibleScrollBounds(region), elapsed = lastTime ? Math.min(time - lastTime, 32) : 16;
      lastTime = time;
      const speed = (point: number, start: number, end: number) => {
        const edge = Math.min(40, (end - start) / 2);
        return edge <= 0 ? 0 : point < start + edge ? -Math.min(1, (start + edge - point) / edge)
          : point > end - edge ? Math.min(1, (point - end + edge) / edge) : 0;
      };
      const x = region.scrollLeft, y = region.scrollTop;
      if (rect.right > rect.left && rect.bottom > rect.top) {
        region.scrollLeft += speed(gesture.x, rect.left, rect.right) * elapsed * .6;
        region.scrollTop += speed(gesture.y, rect.top, rect.bottom) * elapsed * .6;
      }
      if (x !== region.scrollLeft || y !== region.scrollTop) paint();
      frame = window.requestAnimationFrame(autoScroll);
    };
    const move = (event: PointerEvent) => {
      if (active.current?.pointer !== event.pointerId) return;
      if (event.pointerType === 'mouse' && event.buttons === 0) { stop(true, '鼠标已松开但未收到完整结束事件。'); return; }
      active.current.x = event.clientX; active.current.y = event.clientY;
      paint();
      if (!frame) frame = window.requestAnimationFrame(autoScroll);
    };
    const up = (event: PointerEvent) => {
      if (active.current?.pointer !== event.pointerId) return;
      active.current.x = event.clientX; active.current.y = event.clientY;
      stop(false);
    };
    const cancelPointer = (event: PointerEvent) => { if (active.current?.pointer === event.pointerId) stop(true, event.type === 'lostpointercapture' ? '拖动已被浏览器中断。' : '指针操作已中断。'); };
    const cancel = () => stop(true);
    const blur = () => stop(true, '窗口已失去焦点。');
    const resize = () => stop(true, '画布尺寸已变化。');
    const key = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' && active.current) { event.preventDefault(); event.stopPropagation(); cancel(); }
    };
    controller.current = { cancel, paint };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', cancelPointer);
    window.addEventListener('lostpointercapture', cancelPointer);
    window.addEventListener('blur', blur);
    window.addEventListener('resize', resize);
    window.addEventListener('keydown', key, true);
    // Scroll does not bubble; update the held candidate even with no pointermove.
    window.addEventListener('scroll', paint, true);
    // Native panel/side rail resizing may not trigger a window resize.
    let width = grid.current?.getBoundingClientRect().width;
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(entries => {
      const next = entries[0]?.contentRect.width;
      if (width !== undefined && next !== undefined && Math.abs(next - width) > .5) resize();
      width = next;
    });
    if (grid.current) observer?.observe(grid.current);
    return () => {
      controller.current = null; active.current = null;
      if (frame) window.cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', cancelPointer); window.removeEventListener('lostpointercapture', cancelPointer);
      window.removeEventListener('blur', blur); window.removeEventListener('resize', resize);
      window.removeEventListener('keydown', key, true);
      window.removeEventListener('scroll', paint, true);
    };
  }, []);
  useEffect(() => {
    if (!editing || disabled) controller.current?.cancel();
    if (!editing) setMessage(''); // A later edit must not announce a discarded layout as still unsaved.
  }, [editing, disabled]);

  const start = (event: ReactPointerEvent<HTMLButtonElement>, block: GridBlock, mode: Mode) => {
    if (!editing || disabled || active.current || event.button !== 0 || event.isPrimary === false || !grid.current || !scroll.current) return;
    event.preventDefault(); event.currentTarget.focus();
    try {
      const metrics = gridMetrics(grid.current.getBoundingClientRect().width);
      const rect = scroll.current.getBoundingClientRect();
      event.currentTarget.setPointerCapture(event.pointerId);
      active.current = { block, mode, metrics, pointer: event.pointerId, button: event.currentTarget,
        startX: event.clientX, startY: event.clientY, x: event.clientX, y: event.clientY,
        scrollX: scroll.current.scrollLeft, scrollY: scroll.current.scrollTop, regionX: rect.left, regionY: rect.top };
      controller.current?.paint();
    } catch { setMessage('未能开始拖动，请重试或用方向键调整。'); }
  };
  const keyboard = (event: KeyboardEvent<HTMLButtonElement>, block: GridBlock, mode: Mode) => {
    if (!editing || disabled || active.current || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    const step = event.shiftKey ? 5 : 1;
    // Grid units, not display pixels; keyboard also works before the first ResizeObserver callback.
    const metrics = gridMetrics(1000);
    const dx = (event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0) * metrics.columnPitch;
    const dy = (event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0) * metrics.rowPitch;
    const box = gestureBox(block, mode, dx, dy, metrics), placement = validatePlacement(snapshot.spec.blocks, block.block_id, box);
    if (placement.ok) { updateLayout?.(block.block_id, placement.value); setMessage(`${block.title}：${description(box)}。尚未保存。`); }
    else setMessage(placement.message);
  };
  const view = interpretBoard(snapshot.spec, snapshot.facts_by_result_id);
  if (!view.ok) return <p role="alert">{view.error.message}</p>;
  const settings = GRID;
  const rows = Math.min(settings.max_rows, Math.max(...snapshot.spec.blocks.map(block => block.layout.y + block.layout.h),
    drag ? drag.box.y + drag.box.h : 0) + (editing ? 8 : 0));
  const ghost: CSSProperties | undefined = drag ? { ...boxStyle(drag.block.layout, drag.metrics),
    ...(drag.mode === 'move' ? { transform: `translate(${drag.dx}px, ${drag.dy}px)` }
      : { width: Math.max(24, drag.block.layout.w * drag.metrics.columnPitch - drag.metrics.gap + drag.dx),
        height: Math.max(24, drag.block.layout.h * drag.metrics.rowPitch - drag.metrics.gap + drag.dy) }) } : undefined;
  return <>
    <style>{css}{libraryComponentCss}</style>
    {editing ? <p id={helpId}>拖动手柄移动或缩放。方向键每次调整一格，Shift 加方向键调整五格；Esc 取消正在拖动的手势。重叠位置不能落位。</p> : null}
    <div className="sm-layout-surface"><div ref={scroll} className="sm-layout-scroll" role="region" aria-label="看板画布，可横向和纵向滚动" tabIndex={0}>
      <div ref={grid} className="sm-layout-grid" data-testid="library-board-grid" data-editing={editing}
        style={{ gridTemplateColumns: `repeat(${settings.columns},minmax(0,1fr))`, gridAutoRows: settings.row_height_px,
          gridTemplateRows: `repeat(${rows},${settings.row_height_px}px)`, gap: settings.gap_px }}>
        {view.value.blocks.map(block => {
          const spec = snapshot.spec.blocks.find(item => item.block_id === block.block_id)!;
          return <section className="sm-layout-block" key={block.block_id}
            tabIndex={selectBlock && !disabled ? 0 : undefined} aria-label={selectBlock ? '组件：' + block.title : undefined}
            onClick={event => { if (!editing && !disabled && selectBlock && !(event.target as Element).closest('button,a,input,select,textarea,summary,details')) selectBlock(block.block_id); }}
            onKeyDown={event => { if (!editing && !disabled && selectBlock && event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) { event.preventDefault(); selectBlock(block.block_id); } }} data-block-id={block.block_id} data-active={drag?.block.block_id === block.block_id || selectedBlockId === block.block_id}
            style={{ gridColumn: `${spec.layout.x + 1} / span ${spec.layout.w}`, gridRow: `${spec.layout.y + 1} / span ${spec.layout.h}` }}>
            {editing ? <div className="sm-layout-handles">{(['move', 'resize'] as const).map(mode => <button key={mode} type="button"
              data-layout-mode={mode} aria-label={`${mode === 'move' ? '移动' : '缩放'} ${spec.title}`} aria-describedby={helpId}
              disabled={disabled} onPointerDown={event => start(event, spec, mode)} onKeyDown={event => keyboard(event, spec, mode)}>
              {mode === 'move' ? '⠿ 移动' : '↘ 缩放'}</button>)}</div> : null}
            <h2>{block.title}</h2>
            {!editing && selectBlock ? <button type="button" disabled={disabled || selectedBlockId === block.block_id}
              aria-label={`选择组件 ${block.title}`} onClick={() => selectBlock(block.block_id)}>
              {selectedBlockId === block.block_id ? '当前选中组件' : '编辑组件'}</button> : null}
            {block.library ? <LibraryComponentBody view={block.library} /> : <p>此组件版本尚未支持。</p>}
          </section>;
        })}
        {drag ? <><div className="sm-layout-target" data-testid="layout-target" data-valid={drag.valid} style={boxStyle(drag.box, drag.metrics)} aria-hidden="true" />
          <div className="sm-layout-ghost" data-testid="layout-ghost" style={ghost} aria-hidden="true">{drag.block.title}</div></> : null}
      </div>
    </div></div>
    {editing ? <p className="sm-layout-status" role="status" aria-live="polite" data-testid="layout-status">{message}</p> : null}
  </>;
}
