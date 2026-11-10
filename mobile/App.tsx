import React, { useState } from 'react';
import { SafeAreaView, StyleSheet, StatusBar } from 'react-native';
import { SupportedLanguage } from './src/i18n/catalogs';
import { LanguageSelectScreen } from './src/screens/LanguageSelectScreen';
import { AuthScreen } from './src/screens/AuthScreen';
import { FarmBoundaryScreen } from './src/screens/FarmBoundaryScreen';
import { EvidenceCaptureScreen } from './src/screens/EvidenceCaptureScreen';

type AppStep = 'LANGUAGE' | 'AUTH' | 'FARM_SETUP' | 'CAPTURE';

export default function App() {
  const [step, setStep] = useState<AppStep>('LANGUAGE');
  const [language, setLanguage] = useState<SupportedLanguage>('en');
  const [farmer, setFarmer] = useState<{ id: string; fullName: string; phone: string } | null>(null);
  const [farm, setFarm] = useState<{ id: string; name: string } | null>(null);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor="#F8F9FA" />

      {step === 'LANGUAGE' && (
        <LanguageSelectScreen
          onLanguageSelected={(selectedLang) => {
            setLanguage(selectedLang);
            setStep('AUTH');
          }}
        />
      )}

      {step === 'AUTH' && (
        <AuthScreen
          language={language}
          onAuthSuccess={(authenticatedFarmer) => {
            setFarmer(authenticatedFarmer);
            setStep('FARM_SETUP');
          }}
        />
      )}

      {step === 'FARM_SETUP' && farmer && (
        <FarmBoundaryScreen
          language={language}
          farmerId={farmer.id}
          onFarmCreated={(createdFarm) => {
            setFarm(createdFarm);
            setStep('CAPTURE');
          }}
        />
      )}

      {step === 'CAPTURE' && farmer && farm && (
        <EvidenceCaptureScreen
          farmId={farm.id}
          farmerId={farmer.id}
          onEvidenceCaptured={(evidenceId) => {
            console.log('Successfully captured & queued evidence:', evidenceId);
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8F9FA',
  },
});

