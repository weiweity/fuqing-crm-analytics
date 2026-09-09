export function decodeCandidateSet(value: unknown): any | null;
export function decodeActionDraft(value: unknown): any | null;
export function createFixtureAudienceTransport(options?: { scenario?: string; principal?: { actor_id: string; permission_scope: string } }): any;
export function createHttpAudienceTransport(options: { fetchImpl: typeof fetch; basePath?: string }): any;
export function createAudienceTransport(options?: { http?: { fetchImpl: typeof fetch; basePath?: string }; scenario?: string }): any;
export function wrapAudiencePreviewPayload(payload?: Record<string, unknown>): Record<string, unknown>;
