import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

// "cn" = 红涨绿跌 (中国惯例), "us" = 绿涨红跌 (西方惯例)
export type ColorMode = "cn" | "us";

interface ColorModeContextValue {
  colorMode: ColorMode;
  toggleColorMode: () => void;
  // 正收益颜色 class
  positiveClass: string;
  // 负收益颜色 class
  negativeClass: string;
}

const ColorModeContext = createContext<ColorModeContextValue>({
  colorMode: "cn",
  toggleColorMode: () => {},
  positiveClass: "text-red-600",
  negativeClass: "text-emerald-600",
});

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [colorMode, setColorMode] = useState<ColorMode>(() => {
    return (localStorage.getItem("quantgpt_color_mode") as ColorMode) ?? "cn";
  });

  useEffect(() => {
    localStorage.setItem("quantgpt_color_mode", colorMode);
  }, [colorMode]);

  const toggleColorMode = () => setColorMode((m) => (m === "cn" ? "us" : "cn"));

  const positiveClass = colorMode === "cn" ? "text-red-600" : "text-emerald-600";
  const negativeClass = colorMode === "cn" ? "text-emerald-600" : "text-red-600";

  return (
    <ColorModeContext.Provider value={{ colorMode, toggleColorMode, positiveClass, negativeClass }}>
      {children}
    </ColorModeContext.Provider>
  );
}

export function useColorMode() {
  return useContext(ColorModeContext);
}
