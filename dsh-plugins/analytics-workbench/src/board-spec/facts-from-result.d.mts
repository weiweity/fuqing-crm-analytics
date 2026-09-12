export function catalogFromGsvItems(items: unknown): Record<string, {
  current_gsv: number;
  comparison_gsv: number;
  difference: number;
  change_ratio?: number;
}>;
export function factsFromGsvResult(result: unknown):
  | { ok: true; value: Record<string, { current_gsv: number; comparison_gsv: number; difference: number; change_ratio?: number }> }
  | { ok: false; error: { code: string; message: string } };
