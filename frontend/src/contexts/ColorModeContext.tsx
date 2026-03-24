import { createContext, useContext, useState, useEffect, useMemo, type ReactNode } from "react";

// "cn" = 红涨绿跌 (中国惯例), "us" = 绿涨红跌 (西方惯例)
export type ColorMode = "cn" | "us";

interface ColorModeContextValue {
  colorMode: ColorMode;
  toggleColorMode: () => void;
  positiveClass: string;
  negativeClass: string;
  // Dark mode (user toggle, persisted)
  isDark: boolean;
  toggleDark: () => void;
}

const ColorModeContext = createContext<ColorModeContextValue>({
  colorMode: "cn",
  toggleColorMode: () => {},
  positiveClass: "text-red-600",
  negativeClass: "text-emerald-600",
  isDark: false,
  toggleDark: () => {},
});

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [colorMode, setColorMode] = useState<ColorMode>(() => {
    return (localStorage.getItem("quantgpt_color_mode") as ColorMode) ?? "cn";
  });

  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem("quantgpt_dark_mode") === "true";
  });

  useEffect(() => {
    localStorage.setItem("quantgpt_color_mode", colorMode);
  }, [colorMode]);

  useEffect(() => {
    localStorage.setItem("quantgpt_dark_mode", String(isDark));
  }, [isDark]);

  const toggleColorMode = () => setColorMode((m) => (m === "cn" ? "us" : "cn"));
  const toggleDark = () => setIsDark((d) => !d);

  // Dark mode: boost saturation for dark backgrounds
  const positiveClass = colorMode === "cn"
    ? (isDark ? "text-red-400" : "text-red-600")
    : (isDark ? "text-emerald-400" : "text-emerald-600");
  const negativeClass = colorMode === "cn"
    ? (isDark ? "text-emerald-400" : "text-emerald-600")
    : (isDark ? "text-red-400" : "text-red-600");

  const value = useMemo(() => ({
    colorMode, toggleColorMode, positiveClass, negativeClass,
    isDark, toggleDark,
  }), [colorMode, positiveClass, negativeClass, isDark]);

  return (
    <ColorModeContext.Provider value={value}>
      {children}
    </ColorModeContext.Provider>
  );
}

export function useColorMode() {
  return useContext(ColorModeContext);
}
