import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import zhCN from "./zh-CN.json";
import enUS from "./en-US.json";

/**
 * PRD §1: Localization — zh-CN primary, en-US secondary.
 * 初始语言从 uiStore 持久化快照读取（避免循环依赖，直接解析 localStorage）。
 */
function readPersistedLanguage(): "zh-CN" | "en-US" {
  try {
    const raw = localStorage.getItem("hunter-ui-store");
    if (raw) {
      const lang = (JSON.parse(raw) as { state?: { language?: string } }).state
        ?.language;
      if (lang === "en-US" || lang === "zh-CN") return lang;
    }
  } catch {
    /* ignore corrupted storage */
  }
  return "zh-CN";
}

i18n.use(initReactI18next).init({
  resources: {
    "zh-CN": { translation: zhCN },
    "en-US": { translation: enUS },
  },
  lng: readPersistedLanguage(),
  fallbackLng: "zh-CN",
  interpolation: { escapeValue: false },
});

export default i18n;
