export type FunnelGeometry = { empty: boolean; stages: { label: string; count: number; width: number;
  first_ratio: number | null; previous_ratio: number | null }[] };
export function funnelGeometry(data: unknown): FunnelGeometry | null;
