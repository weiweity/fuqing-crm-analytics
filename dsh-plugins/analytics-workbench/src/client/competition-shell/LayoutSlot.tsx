import type { ReactNode } from 'react';
import { ThemeProvider } from './ThemeProvider.tsx';
import type { CompetitionColorScheme } from './tokens.ts';
import {
  BrandNav, ErrorState, PageTitle, ShellDialog, WelcomeHero,
  type CompetitionNavId, type ErrorKind,
} from './BrandChrome.tsx';
import { StatusBanner, type StatusKind } from './StatusEvidence.tsx';

export const LAYOUT_SLOT_NAMES = [
  'welcome', 'nav', 'title', 'error', 'dialog', 'ask', 'analyses', 'cockpit', 'actions',
] as const;

export type LayoutSlotName = typeof LAYOUT_SLOT_NAMES[number];

export type LayoutSlotProps = {
  name: LayoutSlotName;
  children?: ReactNode;
  className?: string;
};

export function LayoutSlot({ name, children, className }: LayoutSlotProps) {
  return (
    <section
      className={['sm-layout-slot', `sm-layout-slot-${name}`, className].filter(Boolean).join(' ')}
      data-sm-slot={name}
      data-testid={`sm-slot-${name}`}
    >
      {children}
    </section>
  );
}

export type CompetitionShellProps = {
  active?: CompetitionNavId;
  onNavigate?: (id: CompetitionNavId) => void;
  onSuggest?: (text: string) => void;
  title?: string;
  eyebrow?: string;
  children?: ReactNode;
  slots?: Partial<Record<LayoutSlotName, ReactNode>>;
  status?: { kind: StatusKind; message: string };
  error?: { kind: ErrorKind; title: string; detail: string; actionLabel?: string; onAction?: () => void } | null;
  dialog?: { open: boolean; title: string; children: ReactNode; onClose: () => void };
  colorScheme?: CompetitionColorScheme;
};

export function CompetitionShell({
  active = 'ask', onNavigate, onSuggest, title, eyebrow, children, slots, status, error, dialog,
  colorScheme,
}: CompetitionShellProps) {
  return (
    <ThemeProvider colorScheme={colorScheme}>
      <LayoutSlot name="nav">{slots?.nav ?? <BrandNav active={active} onNavigate={onNavigate} />}</LayoutSlot>
      <div className="sm-competition-main">
        <LayoutSlot name="title">
          {slots?.title ?? <PageTitle eyebrow={eyebrow} title={title ?? '伸美 AI 增长董事会'} />}
        </LayoutSlot>
        {status ? <StatusBanner kind={status.kind} message={status.message} /> : null}
        <LayoutSlot name="welcome">{slots?.welcome ?? <WelcomeHero onPick={onSuggest} />}</LayoutSlot>
        {error ? (
          <LayoutSlot name="error">
            {slots?.error ?? (
              <ErrorState
                kind={error.kind}
                title={error.title}
                detail={error.detail}
                actionLabel={error.actionLabel}
                onAction={error.onAction}
              />
            )}
          </LayoutSlot>
        ) : slots?.error ? <LayoutSlot name="error">{slots.error}</LayoutSlot> : null}
        <LayoutSlot name="ask">{slots?.ask}</LayoutSlot>
        <LayoutSlot name="analyses">{slots?.analyses}</LayoutSlot>
        <LayoutSlot name="cockpit">{slots?.cockpit}</LayoutSlot>
        <LayoutSlot name="actions">{slots?.actions}</LayoutSlot>
        {children}
      </div>
      <LayoutSlot name="dialog">
        {slots?.dialog ?? (
          dialog
            ? <ShellDialog open={dialog.open} title={dialog.title} onClose={dialog.onClose}>{dialog.children}</ShellDialog>
            : null
        )}
      </LayoutSlot>
    </ThemeProvider>
  );
}
