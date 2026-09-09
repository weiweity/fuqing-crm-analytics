import { useEffect, useRef, useState } from 'react';
import {
  ConditionChips, ErrorState, EvidenceBlock, LayoutSlot, StatusBanner, ThemeProvider,
} from '../competition-shell/index.ts';
import { DEFAULT_PRINCIPAL } from '../competition-board/c0-fixtures.mjs';
import { competitionBoardCss } from '../competition-board/css.ts';
import { createAudienceTransport } from './transport.mjs';
import { competitionHttpOptions } from '../competition-http.mjs';
import { NON_REPURCHASE } from './c0-fixtures.mjs';

type CombineOp = 'AND' | 'OR';
type AudienceTransport = ReturnType<typeof createAudienceTransport>;

export type ActionsMountProps = {
  transport?: AudienceTransport;
  modelAvailable?: boolean;
  principal?: { actor_id: string; permission_scope: string };
  createRoot?: (el: HTMLElement) => { render(node: unknown): void; unmount(): void };
  onDispose?: () => void;
};

function errorKind(status: number): 'conflict' | 'forbidden' | 'failed' | 'empty' {
  if (status === 409) return 'conflict';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'empty';
  return 'failed';
}

export function ActionsWorkbench(props: ActionsMountProps) {
  const httpOptions = competitionHttpOptions();
  const transportRef = useRef<AudienceTransport>(props.transport ?? createAudienceTransport(httpOptions ? { http: httpOptions } : {}));
  const transport = props.transport ?? transportRef.current;
  const principal = props.principal ?? DEFAULT_PRINCIPAL;
  const [combine, setCombine] = useState<CombineOp>('AND');
  const [rules, setRules] = useState<string[]>(['ORIGIN_CHANNEL_ABSENT']);
  const [pack, setPack] = useState<{ candidates?: any; cohort?: any; draft?: any; partial?: any } | null>(null);
  const [error, setError] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [copy, setCopy] = useState({ control_design: '', stop_condition: '' });
  const [reviewBy, setReviewBy] = useState('2026-09-15');

  async function reload() {
    const row = await transport.loadDraft();
    if (!row.ok) { setError(row.body.error); setPack(null); return; }
    setError(null);
    setPack(row.body);
    setCopy({
      control_design: row.body.draft?.control_design ?? '',
      stop_condition: row.body.draft?.stop_condition ?? '',
    });
  }

  useEffect(() => { void reload(); }, []);

  async function preview() {
    const row = await transport.previewCandidates(principal, {
      combine,
      rules,
      force_empty: rules.length === 0,
    });
    if (!row.ok) { setError(row.body.error); return; }
    setError(null);
    setPack(current => ({ ...current, ...row.body }));
    const count = row.body.candidates?.unique_count ?? 0;
    setMessage(count === 0
      ? '零候选。可改规则，不得伪造建议名单。'
      : `去重后 ${count} 人。combine=${row.body.candidates.combine}。`);
  }

  async function save(kind: 'copy' | 'rule' | 'review') {
    const payload = kind === 'copy'
      ? { copy_only_change: true, ...copy }
      : kind === 'review'
        ? { copy_only_change: true, status: 'REVIEW_PENDING', review_by: reviewBy, reviewer_id: 'reviewer.ops', ...copy }
        : { rule_changed: true, ...copy };
    const row = await transport.saveDraft(principal, payload);
    if (!row.ok) { setError(row.body.error); return; }
    setPack(current => ({ ...current, draft: row.body }));
    setMessage(kind === 'copy'
      ? '仅文案变更，证据与人数未改，草稿未过期。'
      : kind === 'review'
        ? '已提交复核。不自动发送。'
        : '规则或来源已变，草稿过期，需重新计算并复核。');
  }

  const candidates = pack?.candidates;
  const cohort = pack?.cohort;
  const draft = pack?.draft;
  const zero = candidates && candidates.unique_count === 0;
  const expired = draft?.status === 'EXPIRED';

  return (
    <ThemeProvider>
      <style>{competitionBoardCss}</style>
      <LayoutSlot name="actions">
        <div className="sm-competition-actions" data-testid="sm-competition-actions" data-transport={transport.kind}
          data-combine={combine} data-zero={zero ? '1' : '0'} data-expired={expired ? '1' : '0'}
          data-auto-send="0">
          <h2>召回候选与行动草稿</h2>
          <p data-testid="sm-no-auto-send">不自动发送 · auto_send=false · 不是 Mission DRAFT_EXPORT</p>
          <StatusBanner
            kind={props.modelAvailable ? 'synthetic' : 'model_unavailable'}
            message="auto_send=false。不是 Mission DRAFT_EXPORT。合成 customer_key，不导出真实名单。"
          />
          {error ? (
            <ErrorState
              kind={errorKind(error.http_status)}
              title={error.code}
              detail={`${error.message} param=${error.param ?? '—'}`}
            />
          ) : null}
          {message ? <p role="status" data-testid="sm-actions-status">{message}</p> : null}

          <section className="sm-candidate-card" data-testid="sm-candidate-panel">
            <h3>候选规则</h3>
            {cohort ? (
              <>
                <ConditionChips items={[
                  { id: 'enroll', label: '入组', value: `${cohort.enrollment_window.start_date}–${cohort.enrollment_window.end_date}` },
                  { id: 'observe', label: '观察', value: `${cohort.observation_window.start_date}–${cohort.observation_window.end_date}` },
                  { id: 'member', label: '会员历史', value: cohort.member_history_status },
                  { id: 'family', label: '已有 family', value: cohort.existing_family },
                ]} />
                <EvidenceBlock
                  asOf={cohort.as_of}
                  source={cohort.source_tense}
                  limitations={cohort.limitations}
                  unknowns={['MEMBER_HISTORY', 'F_ORDER_GRAIN_OLD_CRM']}
                />
              </>
            ) : null}
            <fieldset>
              <legend>未回购规则（可多选，合并去重）</legend>
              {NON_REPURCHASE.map(kind => (
                <label key={kind}>
                  <input
                    type="checkbox"
                    checked={rules.includes(kind)}
                    onChange={event => setRules(current => event.target.checked
                      ? [...current, kind]
                      : current.filter(row => row !== kind))}
                  />
                  {kind}
                </label>
              ))}
            </fieldset>
            <fieldset>
              <legend>组合</legend>
              <label><input type="radio" name="combine" checked={combine === 'AND'} onChange={() => setCombine('AND')} /> AND</label>
              <label><input type="radio" name="combine" checked={combine === 'OR'} onChange={() => setCombine('OR')} /> OR</label>
            </fieldset>
            <p>F 粒度 {cohort?.rules?.[0]?.f_grain_status ?? 'UNKNOWN'}，禁止填写 f_threshold。</p>
            <button type="button" data-testid="sm-preview-candidates" onClick={() => void preview()}>预览候选人数</button>
            {pack?.partial ? (
              <ErrorState kind="partial" title="部分规则失败"
                detail={`${pack.partial.note} 拒绝 ${pack.partial.rejected?.rule_id}，不得把失败规则人数加进成功集合。`} />
            ) : null}
            {zero ? (
              <ErrorState kind="empty" title="零人群" detail="零候选不得伪造建议名单。可调整规则后重新预览。" />
            ) : null}
            {candidates ? (
              <p data-testid="sm-candidate-count">
                unique_count={candidates.unique_count} · keys={candidates.customer_keys.length} · auto_send={String(candidates.auto_send)}
              </p>
            ) : null}
            <ul className="sm-candidate-list" data-testid="sm-candidate-explanations">
              {(candidates?.explanations ?? []).map((row: { customer_key: string; reasons: string[] }) => (
                <li key={row.customer_key}>
                  {row.customer_key}：{row.reasons.join('、')}
                </li>
              ))}
            </ul>
          </section>

          <section className="sm-draft-card" data-testid="sm-draft-panel">
            <h3>行动草稿</h3>
            {draft ? (
              <>
                <p>draft {draft.draft_id} · v{draft.version} · {draft.status}
                  {draft.expired_reason ? ` · ${draft.expired_reason}` : ''}</p>
                <p>负责人 {draft.owner_id} · 复核人 {draft.reviewer_id ?? '—'} · 复盘 {draft.review_by ?? '—'}</p>
                <p>预算上限 {draft.budget_cap_minor} {draft.currency} · 渠道 {draft.channel ?? '—'}</p>
                <p>未知项：{(draft.unknowns ?? []).join('；')}</p>
                <p>局限：{(draft.limitations ?? []).join('；')}</p>
                {expired ? (
                  <ErrorState kind="failed" title="草稿已过期"
                    detail="规则或来源变更后草稿过期，需重新计算候选并复核。文案变更不会过期。" />
                ) : null}
                <label>对照设计
                  <textarea value={copy.control_design} onChange={event => setCopy(current => ({ ...current, control_design: event.target.value }))} />
                </label>
                <label>停止条件
                  <textarea value={copy.stop_condition} onChange={event => setCopy(current => ({ ...current, stop_condition: event.target.value }))} />
                </label>
                <label>复盘日期
                  <input type="text" value={reviewBy} onChange={event => setReviewBy(event.target.value)} />
                </label>
                <div className="sm-competition-toolbar">
                  <button type="button" data-testid="sm-save-copy" onClick={() => void save('copy')}>保存文案（不过期）</button>
                  <button type="button" data-testid="sm-mark-rule-change" onClick={() => void save('rule')}>标记规则已变</button>
                  <button type="button" data-testid="sm-submit-review" onClick={() => void save('review')}>提交复核</button>
                  <button type="button" disabled data-testid="sm-auto-send">不自动发送</button>
                </div>
              </>
            ) : <p>尚无草稿。</p>}
          </section>
        </div>
      </LayoutSlot>
    </ThemeProvider>
  );
}
