import { useEffect, useState } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import type {} from '@deepseek-ai/dsh-client-ui-conversation/client';
import { QUERY_SESSION_IDS } from '../initial-session.mjs';
import { emptyRunView, loadRunView, visibleRunView, type RunView } from '../run-view.mjs';
import { css } from './styles.ts';

const labels = { QUEUED: '排队中', RUNNING: '运行中', NEEDS_INPUT: '需要补充信息', SUCCEEDED: '已完成', FAILED: '失败',
  CANCELLING: '已请求停止，正在确认退出', CANCELLED: '已停止', UNKNOWN: '状态待核对，不会自动重发' };
const phases = { ACCEPTED: '已受理', PLANNING: '规划', EXECUTING: '执行工具', FINALIZING: '已核对退出' };

export function RunStatus(props: PropsRuntime<'conversation.input.dock'>) {
  const sessionId = props.session.sessionId;
  const [view, setView] = useState<RunView>(() => emptyRunView(sessionId));
  const [problem, setProblem] = useState('正在读取任务内核…');
  const shown = visibleRunView(view, sessionId);
  const querySession = QUERY_SESSION_IDS.some(id => id === sessionId);
  const kind = querySession ? '合成查询 / SYNTHETIC' : 'B0 / STUB / SYNTHETIC';
  useEffect(() => {
    setView(emptyRunView(sessionId));
    setProblem('正在读取任务内核…');
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function read() {
      let delay = 1000;
      try {
        const next = await loadRunView(fetch, sessionId, abort.signal);
        if (abort.signal.aborted) return;
        setView(next); setProblem('');
        delay = next.runs.some(run => ['QUEUED', 'RUNNING', 'CANCELLING', 'UNKNOWN'].includes(run.status)) ? 400 : 1500;
      } catch (error) {
        if (abort.signal.aborted) return;
        const lost = error instanceof Error && error.message === 'ACCESS_LOST';
        if (lost) setView(emptyRunView(sessionId));
        setProblem(lost ? '访问已失效，请重新进入本次演示。' : '任务状态连接中断；仅展示上次快照，正在只读重连。');
      }
      if (!abort.signal.aborted) timer = setTimeout(read, delay);
    }
    void read();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [sessionId]);
  return <><style>{css}</style><section className="analytics-b0-runs" aria-label={querySession ? '合成查询任务状态' : 'B0 任务内核状态'} data-testid="analytics-b0-runs" data-session-id={sessionId}>
    <small>{kind} · {problem || (shown.ready ? '任务内核已连接' : '运行时未就绪，暂不接收新任务')}</small>
    <div role="status" aria-live="polite">
      {shown.runs.map(run => <div key={run.run_id} data-run-id={run.run_id} data-run-status={run.status}>
        <abbr title={run.run_id}>{run.run_id.slice(-8)}</abbr> · {labels[run.status]} · {phases[run.phase]} · 工具 {run.diagnostics.tool_steps_used}/8
        {problem && ' · 上次快照'}
      </div>)}
      {!problem && shown.runs.length === 0 && <div>尚无任务；发送后显示真实受理和执行状态。</div>}
    </div>
  </section></>;
}
