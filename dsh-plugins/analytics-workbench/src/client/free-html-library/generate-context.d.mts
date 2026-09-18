export const GENERATE_CONTEXT_SCHEMA: 'free-page-generate-context/v1';
export const SHINE_INVARIANTS: readonly string[];
export const ANTI_TEMPLATE: readonly string[];
export const HOST_CHROME_BOUNDS: {
  maxResidentShells: number;
  contextPanels: number;
  statusSpine: readonly string[];
  preview: string;
  nativeChat: string;
};
export const SAMPLE_PROMPTS: readonly string[];
export type GenerateContext = {
  schema_version: typeof GENERATE_CONTEXT_SCHEMA;
  prompt: string;
  invariants: readonly string[];
  antiTemplate: readonly string[];
  hostChromeBounds: typeof HOST_CHROME_BOUNDS;
  themeCopy: ReturnType<typeof themeValueCopy>;
  designGuide: { kind: string | null; loaded: boolean; excerpt: string; error: string };
  skill: { kind?: string | null; loaded: boolean; excerpt: string; error: string };
  claimedFollowed: { designGuide: boolean; skill: boolean };
  nativeRuntime: 'dsh-native-agent-only';
};
export function themeValueCopy(scheme?: 'dark' | 'light'): {
  scheme: string;
  note: string;
  color: { background: string; ink: string; lilac: string; purpleEmphasisOnly: string; signal: string; danger: string };
  font: { body: string; display: string; mono: string };
};
export function buildGenerateContext(input?: {
  prompt?: string;
  designGuide?: { kind?: string; loaded?: boolean; excerpt?: string; error?: string } | null;
  skill?: { loaded?: boolean; excerpt?: string; error?: string } | null;
  scheme?: 'dark' | 'light';
}): GenerateContext;
