import { createContext, useContext, type CSSProperties, type ReactNode } from 'react';
import ConfigProvider from 'antd/es/config-provider';
import antdAlgorithms from 'antd/es/theme';
import { competitionShellCss } from './css.ts';
import { competitionThemeFor, competitionTokens, type CompetitionTokens, type CompetitionColorScheme } from './tokens.ts';

const CompetitionThemeContext = createContext<CompetitionTokens>(competitionTokens);
const ColorSchemeContext = createContext<CompetitionColorScheme>('dark');

export function useCompetitionTheme(): CompetitionTokens {
  return useContext(CompetitionThemeContext);
}

export type ThemeProviderProps = {
  children: ReactNode;
  className?: string;
  /** Nested business views inherit the mode resolved by the native runtime. */
  colorScheme?: CompetitionColorScheme;
  /** Main-panel root; overlay still prefers the nearest dialog. */
  popupRoot?: HTMLElement | null;
};

export function ThemeProvider({ children, className, colorScheme, popupRoot }: ThemeProviderProps) {
  const inherited = useContext(ColorSchemeContext);
  const mode = colorScheme ?? inherited;
  const tokens = competitionThemeFor(mode);
  const theme = { ...tokens.antd, algorithm: mode === 'dark' ? antdAlgorithms.darkAlgorithm : antdAlgorithms.defaultAlgorithm };
  return (
    <ColorSchemeContext.Provider value={mode}>
    <ConfigProvider theme={theme} getPopupContainer={trigger => trigger?.closest('dialog') ?? popupRoot ?? trigger?.parentElement ?? document.body}>
    <CompetitionThemeContext.Provider value={tokens}>
      <style>{competitionShellCss}</style>
      <div
        className={['sm-competition-root', className].filter(Boolean).join(' ')}
        data-sm-theme="competition"
        data-sm-color-scheme={mode}
        data-testid="sm-theme-root"
        style={tokens.cssVars as CSSProperties}
      >
        {children}
      </div>
    </CompetitionThemeContext.Provider>
    </ConfigProvider>
    </ColorSchemeContext.Provider>
  );
}
