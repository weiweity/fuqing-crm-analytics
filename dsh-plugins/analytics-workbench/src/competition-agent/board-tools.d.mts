export const BOARD_TOOL_PARAMETERS: Readonly<Record<string, object>>;
export function executeBoardTool(name: string, args: Record<string, unknown>, execution: {
  agent?: { session?: { id?: string } }; signal?: AbortSignal;
}): Promise<object>;
