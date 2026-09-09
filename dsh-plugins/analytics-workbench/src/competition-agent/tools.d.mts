export function liveTransportRefused(): object;
export function liveDiagnosisCall(toolName: string, args?: object, signal?: AbortSignal): Promise<object>;
export function assertRegisteredTool(name: string): void;
