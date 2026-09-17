export type WaterfallGeometry = { width: number; height: number; min: number; max: number; zero: number;
  bars: { label: string; value: number; role: string; from: number; to: number;
    x: number; width: number; top: number; bottom: number; carry: number }[] };
export function waterfallGeometry(data: unknown): WaterfallGeometry | null;
