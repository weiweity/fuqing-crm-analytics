export const DEMO_BOARD_SPEC: {
  board_id: string;
  version: number;
  session_id?: string;
  blocks: readonly object[];
};
export const DEMO_BOARD_FACTS: Record<string, {
  current_gsv?: number;
  comparison_gsv?: number;
  difference?: number;
  change_ratio?: number;
}>;
export const DEMO_BOARD: { spec: object; facts: object | null };
