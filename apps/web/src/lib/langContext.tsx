import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

type UILang = "en" | "bn";

interface LangContextValue {
  uiLang: UILang;
  setUiLang: (lang: UILang) => void;
}

const LangContext = createContext<LangContextValue>({
  uiLang: "en",
  setUiLang: () => undefined,
});

export function LangProvider({ children }: { children: ReactNode }) {
  const [uiLang, setUiLangState] = useState<UILang>(
    () => (localStorage.getItem("bd-legal-rag-lang") as UILang | null) ?? "en",
  );

  function setUiLang(lang: UILang) {
    localStorage.setItem("bd-legal-rag-lang", lang);
    setUiLangState(lang);
  }

  return (
    <LangContext.Provider value={{ uiLang, setUiLang }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang(): LangContextValue {
  return useContext(LangContext);
}
