export const PRODUCT_NAME: string;
export const PRODUCT_HEADLINE: string;
export const PRODUCT_GREETING: string;
export function applyCompetitionBrandSurface(doc?: Document): { title: string; greeting: boolean };
export function watchCompetitionBrandSurface(doc?: Document): () => void;
