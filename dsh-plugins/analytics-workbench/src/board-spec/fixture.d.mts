export const BOARD_SPEC_FIXTURE: {
  board_id: string;
  version: number;
  session_id?: string;
  blocks: readonly object[];
};
export const BOARD_SPEC_FACTS: Record<string, {
  current_gsv?: number;
  comparison_gsv?: number;
  difference?: number;
  change_ratio?: number;
}>;
