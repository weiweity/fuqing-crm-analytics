export interface SkillPackageManifest {
  schema_version: 'analytics-b0-skill-package/v1';
  name: 'growth-analysis-b0'; version: string; scope: 'B0_SYNTHETIC_ONLY';
  description: string; files: Record<string, string>;
}
export interface SkillPackageInput { manifest: SkillPackageManifest; contents: Record<string, string> }
export function freezeSkillPackage(input: SkillPackageInput): {
  readonly digest: string; readonly manifest: Readonly<SkillPackageManifest>; readonly resources: readonly string[];
  readonly definition: {
    readonly name: string; readonly description: string; readonly source: 'bundled'; readonly provider: string;
    readonly invocation: { readonly modelInvocable: true; readonly userInvocable: false };
    readonly resourceBase: { readonly kind: 'opaque'; readonly description: string }; readonly content: string;
  };
  read(resource: string): { schema_version: 'analytics-b0-skill-resource/v1'; package_digest: string;
    resource: string; content_digest: string; content: string };
};
export const SKILL_NAME: 'growth-analysis-b0';
export const RESOURCE_TOOL_NAME: 'analytics_b0_skill_resource';
export function packageDigest(manifest: SkillPackageManifest): string;
