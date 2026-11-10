export type SupportedLanguage = "en" | "te" | "hi";

export interface TranslationCatalog {
  app_title: string;
  welcome: string;
  select_language: string;
  register_farm: string;
  capture_evidence: string;
  sync_pending: string;
  retake_requested: string;
  approved: string;
}

export const translations: Record<SupportedLanguage, TranslationCatalog> = {
  en: {
    app_title: "PRAMAN Evidence Platform",
    welcome: "Welcome Farmer",
    select_language: "Select Language",
    register_farm: "Register Farm Parcel",
    capture_evidence: "Capture Evidence",
    sync_pending: "Syncing pending offline evidence",
    retake_requested: "Retake requested by reviewer",
    approved: "Evidence verified and approved",
  },
  te: {
    app_title: "ప్రమాణ్ ఆధార వేదిక",
    welcome: "రైతు స్వాగతం",
    select_language: "భాషను ఎంచుకోండి",
    register_farm: "పొలం వివరాలను నమోదు చేయండి",
    capture_evidence: "సాక్ష్యాన్ని సేకరించండి",
    sync_pending: "ఆఫ్‌లైన్ ఆధారాలు సర్వర్‌కు సమకాలీకరించబడుతున్నాయి",
    retake_requested: "సమీక్షకుడు ఫోటోను మళ్ళీ తీయమని కోరారు",
    approved: "ఆధారం విజయవంతంగా ధృవీకరించబడింది",
  },
  hi: {
    app_title: "प्रमाण साक्ष्य मंच",
    welcome: "किसान स्वागत है",
    select_language: "भाषा चुनें",
    register_farm: "खेत पंजीकृत करें",
    capture_evidence: "साक्ष्य कैप्चर करें",
    sync_pending: "ऑफ़लाइन साक्ष्य सिंक हो रहे हैं",
    retake_requested: "समीक्षक द्वारा दोबारा फोटो का अनुरोध किया गया",
    approved: "साक्ष्य सत्यापित और स्वीकृत",
  },
};

export const I18N_CATALOGS = translations;

export function translate(key: keyof TranslationCatalog, locale: SupportedLanguage): string {
  const cat = translations[locale] || translations.en;
  return cat[key] || translations.en[key] || key;
}


