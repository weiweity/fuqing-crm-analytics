export interface CompetitionBoundaryExecution {
  readonly name: string;
  readonly agent?: object;
}

export interface CompetitionToolBoundary {
  readonly mark: (execution: CompetitionBoundaryExecution) => undefined;
  readonly clear: (agent: object) => void;
  readonly guard: (execution: CompetitionBoundaryExecution) => string | undefined;
}

export function createCompetitionToolBoundary(): CompetitionToolBoundary;
