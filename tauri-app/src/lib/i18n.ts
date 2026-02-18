import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Import locale files directly (Vite handles JSON imports)
import en from "../locales/en.json";
import ja from "../locales/ja.json";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ja: { translation: ja },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: {
    // React already handles XSS
    escapeValue: false,
  },
  // Support nested keys with dot notation
  keySeparator: ".",
  // Default namespace
  defaultNS: "translation",
});

export default i18n;
