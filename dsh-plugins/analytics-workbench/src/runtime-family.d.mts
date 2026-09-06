export const QUERY_FAMILY: 'channel_followup';
export function runtimeFamily(): 'b0' | 'channel_followup';
export function registeredSessionIds(): string[];
export function isRegisteredSession(id: string): boolean;
