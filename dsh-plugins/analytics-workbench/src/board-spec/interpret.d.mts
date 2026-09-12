export type InterpretedBlock = {
  block_id: string;
  kind: string;
  title: string;
  metric_ref: string | null;
  source_result_id: string | null;
  bind: string;
  paint: Record<string, unknown>;
};
export function interpretBoard(spec: unknown, factsByResultId?: object | null):
  | { ok: true; value: { board_id: string; version: number; blocks: InterpretedBlock[] } }
  | { ok: false; error: { code: string; message: string } };
