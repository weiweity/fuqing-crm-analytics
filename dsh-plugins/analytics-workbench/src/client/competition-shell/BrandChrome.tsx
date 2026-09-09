import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { trapDialogTab } from '../focus.ts';
import { BRAND_ASSET_URLS, PRODUCT_NAME, PRODUCT_NAME_EN, PRODUCT_TAGLINE } from './tokens.ts';

export const COMPETITION_NAV_ITEMS = [
  { id: 'ask', label: '问数', slot: 'ask' },
  { id: 'analyses', label: '分析', slot: 'analyses' },
  { id: 'cockpit', label: '驾驶舱', slot: 'cockpit' },
  { id: 'actions', label: '行动', slot: 'actions' },
] as const;

export type CompetitionNavId = typeof COMPETITION_NAV_ITEMS[number]['id'];

export const SUGGESTED_PROMPTS = [
  '哪个渠道来的客户，后面更愿意再买？',
  '首次买哪些商品的客户，后面更容易买正装？',
  '哪群客户值得先做一个小范围承接试验？',
] as const;

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? 'sm-brand-mark compact' : 'sm-brand-mark'} aria-label={`${PRODUCT_NAME_EN} ${PRODUCT_NAME}`}>
      <img src={BRAND_ASSET_URLS.logo} alt={PRODUCT_NAME_EN} width={249} height={45} data-testid="sm-brand-logo" />
      <span className="sm-brand-copy">
        <strong>{PRODUCT_NAME}</strong>
        {compact ? null : <small>{PRODUCT_TAGLINE}</small>}
      </span>
    </div>
  );
}

export function BrandNav({
  active = 'ask', onNavigate,
}: {
  active?: CompetitionNavId;
  onNavigate?: (id: CompetitionNavId) => void;
}) {
  return (
    <nav className="sm-brand-nav" aria-label="比赛工作台" data-testid="sm-brand-nav">
      <BrandMark />
      <div className="sm-brand-nav-tabs" role="list">
        {COMPETITION_NAV_ITEMS.map(item => {
          const current = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              role="listitem"
              aria-current={current ? 'page' : undefined}
              data-testid={`sm-nav-${item.id}`}
              onClick={() => onNavigate?.(item.id)}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      <p className="sm-settings-hint" data-testid="sm-native-settings-hint">
        模型、权限与文件设置仍走原生 DSH 入口，不在此关闭或替换。
      </p>
    </nav>
  );
}

export function PageTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <header className="sm-page-title" data-testid="sm-page-title">
      {eyebrow ? <p>{eyebrow}</p> : <p>{PRODUCT_NAME_EN}</p>}
      <h1>{title}</h1>
      {children}
    </header>
  );
}

export function WelcomeHero({ onPick }: { onPick?: (text: string) => void }) {
  return (
    <section className="sm-welcome" data-testid="sm-welcome" aria-labelledby="sm-welcome-heading">
      <h2 id="sm-welcome-heading">先问一个可核验的经营问题</h2>
      <p>建议只填入输入框，仍可编辑后再发送。不是已算好的结论。模型未接通时不会显示“AI 已接通”。</p>
      <ul className="sm-welcome-suggestions">
        {SUGGESTED_PROMPTS.map(text => (
          <li key={text}>
            <button type="button" data-testid="sm-suggest" onClick={() => onPick?.(text)}>{text}</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export type ErrorKind = 'unready' | 'auth' | 'loading' | 'empty' | 'partial' | 'conflict' | 'forbidden' | 'failed';

const ERROR_FALLBACK: Record<ErrorKind, { title: string; detail: string }> = {
  unready: { title: '工作台尚未就绪', detail: '正在准备隔离工作区。不要在本机查找密钥或数据目录。' },
  auth: { title: '需要重新进入', detail: '访问已失效。认证不能关闭；请用启动入口重新兑换会话。' },
  loading: { title: '正在加载', detail: '显示真实阶段，不编造进度百分比。' },
  empty: { title: '没有可展示的结果', detail: '保留条件与空样本原因。缺分母时不显示 0%。' },
  partial: { title: '部分块失败', detail: '成功块仍可查看；失败块可局部重试。整板标记为不完整。' },
  conflict: { title: '版本冲突（409）', detail: '保留本地草案，重读后再保存。不会 last-write-wins。' },
  forbidden: { title: '当前权限不可见', detail: '撤权后停止展示详情。已存草案不能绕过权限。' },
  failed: { title: '本次失败', detail: '已有历史结果与本次失败分开。不把部分数字拼成完整结论。' },
};

export function ErrorState({
  kind, title, detail, actionLabel, onAction,
}: {
  kind: ErrorKind;
  title?: string;
  detail?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const fallback = ERROR_FALLBACK[kind];
  return (
    <section className="sm-error-state" data-kind={kind} data-testid="sm-error-state" role="alert">
      <h2>{title ?? fallback.title}</h2>
      <p>{detail ?? fallback.detail}</p>
      {onAction && actionLabel ? <button type="button" onClick={onAction}>{actionLabel}</button> : null}
    </section>
  );
}

export function ShellDialog({
  open, title, children, onClose, labelledBy,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  onClose: () => void;
  labelledBy?: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingId = useId();
  const label = labelledBy ?? headingId;
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  useEffect(() => () => { dialogRef.current?.close(); }, []);
  return (
    <dialog
      ref={dialogRef}
      className="sm-shell-dialog"
      aria-labelledby={label}
      data-testid="sm-shell-dialog"
      onKeyDown={(event: KeyboardEvent<HTMLDialogElement>) => trapDialogTab(event)}
      onCancel={event => { event.preventDefault(); onClose(); }}
      onClose={onClose}
    >
      <header>
        <h2 id={headingId}>{title}</h2>
        <button type="button" data-testid="sm-shell-dialog-close" onClick={onClose}>关闭</button>
      </header>
      {children}
    </dialog>
  );
}
