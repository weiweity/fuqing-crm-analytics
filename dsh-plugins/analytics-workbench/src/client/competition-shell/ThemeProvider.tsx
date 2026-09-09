import { createContext, useContext, type ComponentType, type CSSProperties, type ReactNode } from 'react';
import { competitionShellCss } from './css.ts';
import { antdTheme, competitionCssVars, competitionTokens, type CompetitionTokens } from './tokens.ts';

const CompetitionThemeContext = createContext<CompetitionTokens>(competitionTokens);

export function useCompetitionTheme(): CompetitionTokens {
  return useContext(CompetitionThemeContext);
}

export type AntdConfigProvider = ComponentType<{ theme?: unknown; children?: ReactNode }>;

export type ThemeProviderProps = {
  children: ReactNode;
  className?: string;
  /** Injected by the integrator after antd is locked. A4 does not import antd. */
  ConfigProvider?: AntdConfigProvider;
  /** antd.theme.darkAlgorithm or equivalent. Optional until antd is a dependency. */
  algorithm?: unknown;
};

export function ThemeProvider({ children, className, ConfigProvider, algorithm }: ThemeProviderProps) {
  const theme = { ...antdTheme, algorithm: algorithm ?? undefined };
  const inner = (
    <CompetitionThemeContext.Provider value={competitionTokens}>
      <style>{competitionShellCss}</style>
      <div
        className={['sm-competition-root', className].filter(Boolean).join(' ')}
        data-sm-theme="competition"
        data-testid="sm-theme-root"
        style={competitionCssVars as CSSProperties}
      >
        {children}
      </div>
    </CompetitionThemeContext.Provider>
  );
  if (!ConfigProvider) return inner;
  return <ConfigProvider theme={theme}>{inner}</ConfigProvider>;
}
