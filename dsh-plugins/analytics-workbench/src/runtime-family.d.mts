export const QUERY_FAMILY: 'channel_followup';
export const FIRST_PURCHASE_FAMILY: 'first_purchase';
export const COMPETITION_FAMILY: 'competition_growth';
export function runtimeFamily(): 'b0' | 'channel_followup' | 'first_purchase' | 'competition_growth';
export function registeredSessionIds(): string[];
export function isRegisteredSession(id: string): boolean;
