export function freezeCompetitionSkillPackage(input: {
  manifest: object;
  contents: Record<string, string>;
}): {
  definition: object;
  resources: readonly string[];
  digest: string;
  read: (resource: string) => object;
};
