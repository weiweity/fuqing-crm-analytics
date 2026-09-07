export type SkillFamily = 'b0' | 'channel_followup';
export interface SkillPackageManifest {
  schema_version: 'analytics-b0-skill-package/v1' | 'analytics-channel-followup-skill-package/v1';
  name: 'growth-analysis-b0' | 'channel-followup-query'; version: string;
  scope: 'B0_SYNTHETIC_ONLY' | 'CHANNEL_FOLLOWUP_SYNTHETIC_ONLY';
  description: string; files: Record<string, string>;
}
export interface SkillPackageInput { manifest: SkillPackageManifest; contents: Record<string, string> }
export function freezeSkillPackage(input: SkillPackageInput, family?: SkillFamily): {
  readonly digest: string; readonly manifest: Readonly<SkillPackageManifest>; readonly resources: readonly string[];
  readonly family: SkillFamily; readonly skillName: string; readonly resourceToolName: string;
  readonly definition: {
    readonly name: string; readonly description: string; readonly source: 'bundled'; readonly provider: string;
    readonly invocation: { readonly modelInvocable: true; readonly userInvocable: false };
    readonly resourceBase: { readonly kind: 'opaque'; readonly description: string }; readonly content: string;
  };
  read(resource: string): { schema_version: 'analytics-b0-skill-resource/v1' | 'analytics-channel-followup-skill-resource/v1';
    package_digest: string; resource: string; content_digest: string; content: string };
};
export const SKILL_NAME: 'growth-analysis-b0';
export const RESOURCE_TOOL_NAME: 'analytics_b0_skill_resource';
export const QUERY_SKILL_NAME: 'channel-followup-query';
export const QUERY_RESOURCE_TOOL_NAME: 'analytics_channel_followup_skill_resource';
export function validateManifest(manifest: SkillPackageManifest, family?: SkillFamily): void;
export function packageDigest(manifest: SkillPackageManifest, family?: SkillFamily): string;
