import type { ISessions, SessionListState } from '@deepseek-ai/dsh-api-session-controller/client';
import type { SessionId } from '@deepseek-ai/dsh-session/types';
export const B0_PRIMARY_SESSION_ID: 'session-b0-synthetic-primary';
export function configuredSession(snapshot: SessionListState): SessionId | null;
export function bindInitialSession(sessions: Pick<ISessions, 'list' | 'open'>, onFailure: () => void): () => void;
