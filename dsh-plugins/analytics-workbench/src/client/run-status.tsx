import { useEffect, useState } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import type {} from '@deepseek-ai/dsh-client-ui-conversation/client';
import { loadRunView, type RunView } from '../run-view.mjs';
import { css } from './styles.ts';

const labels = { QUEUED: '排队中', RUNNING: '运行中', NEEDS_INPUT: '需要补充信息', SUCCEEDED: '已完成', FAILED: '失败',
  CANCELLING: '已请求停止，正在确认退出', CANCELLED: '已停止', UNKNOWN: '状态待核对，不会自动重发' };
const phases = { ACCEPTED: '已受理', PLANNING: '规划', EXECUTING: '执行工具', FINALIZING: '已核对退出' };

export function RunStatus(props: PropsRuntime<'conversation.input.dock'>) {
  const [view, setView] = useState<RunView>({ ready: false, runs: [] });
  const [problem, setProblem] = useState('正在读取任务内核…');
  const sessionId = props.session.sessionId;
  useEffect(() => {
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
        if (lost) setView({ ready: false, runs: [] });
        setProblem(lost ? '访问已失效，请重新进入本次演示。' : '任务状态连接中断；仅展示上次快照，正在只读重连。');
      }
      if (!abort.signal.aborted) timer = setTimeout(read, delay);
    }
    void read();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [sessionId]);
  return <><style>{css}</style><section className="analytics-b0-runs" aria-label="B0 任务内核状态" data-testid="analytics-b0-runs">
    <small>B0 / STUB / SYNTHETIC · {problem || (view.ready ? '任务内核已连接' : '运行时未就绪，暂不接收新任务')}</small>
    <div role="status" aria-live="polite">
      {view.runs.map(run => <div key={run.run_id} data-run-id={run.run_id} data-run-status={run.status}>
        <abbr title={run.run_id}>{run.run_id.slice(-8)}</abbr> · {labels[run.status]} · {phases[run.phase]} · 工具 {run.diagnostics.tool_steps_used}/8
        {problem && ' · 上次快照'}
      </div>)}
      {!problem && view.runs.length === 0 && <div>尚无任务；发送后显示真实受理和执行状态。</div>}
    </div>
  </section></>;
}
