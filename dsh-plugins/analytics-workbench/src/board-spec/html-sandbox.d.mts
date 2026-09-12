export type SandboxFail = { ok: false; error: { code: string; message: string } };
export type HtmlFrame = { ok: true; empty: true } | { ok: true; srcdoc: string; sandbox: string; referrerPolicy: 'no-referrer' };
export type HttpsFrame = { ok: true; src: string; sandbox: string; referrerPolicy: 'no-referrer' };
export type OpenLink = { ok: true; href: string; target: '_blank'; rel: 'noopener noreferrer' };
export function wrapSandboxHtml(html: string): string;
export function htmlSandboxFrame(block: object): HtmlFrame | SandboxFail;
export function httpsSandboxFrame(url: string): HttpsFrame | SandboxFail;
export function openHttpsLink(url: string): OpenLink | SandboxFail;
export function refreshSandboxHtml(url: string, fetchImpl?: typeof fetch): Promise<HtmlFrame | SandboxFail>;
