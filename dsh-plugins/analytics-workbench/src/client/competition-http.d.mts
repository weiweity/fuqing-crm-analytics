export const COMPETITION_API_PREFIX: '/api/v1/analytics/competition';
export const FORBIDDEN_HTTP_PORTS: readonly number[];
export function assertCompetitionHttpBase(base: string): string;
export function competitionHttpOptions(): {
  fetchImpl: typeof fetch;
  basePath: string;
} | null;
