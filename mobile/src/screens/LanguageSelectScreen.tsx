import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { translations, SupportedLanguage } from '../i18n/catalogs';

interface LanguageSelectScreenProps {
  onLanguageSelected: (lang: SupportedLanguage) => void;
}

export const LanguageSelectScreen: React.FC<LanguageSelectScreenProps> = ({ onLanguageSelected }) => {
  const [selectedLang, setSelectedLang] = useState<SupportedLanguage>('en');

  const languages: { code: SupportedLanguage; label: string; nativeName: string }[] = [
    { code: 'te', label: 'Telugu', nativeName: 'తెలుగు' },
    { code: 'hi', label: 'Hindi', nativeName: 'हिन्दी' },
    { code: 'en', label: 'English', nativeName: 'English' },
  ];

  return (
    <View style={styles.container}>
      <Text style={styles.title}>PRAMAN</Text>
      <Text style={styles.subtitle}>Select Your Language / మీ భాషను ఎంచుకోండి / अपनी भाषा चुनें</Text>

      <View style={styles.optionsContainer}>
        {languages.map((item) => (
          <TouchableOpacity
            key={item.code}
            style={[styles.button, selectedLang === item.code && styles.buttonSelected]}
            onPress={() => {
              setSelectedLang(item.code);
              onLanguageSelected(item.code);
            }}
          >
            <Text style={[styles.buttonText, selectedLang === item.code && styles.buttonTextSelected]}>
              {item.nativeName} ({item.label})
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    backgroundColor: '#F8F9FA',
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#2E7D32',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#555555',
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 22,
  },
  optionsContainer: {
    gap: 16,
  },
  button: {
    paddingVertical: 16,
    paddingHorizontal: 20,
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: '#DCDCDC',
    alignItems: 'center',
  },
  buttonSelected: {
    borderColor: '#2E7D32',
    backgroundColor: '#E8F5E9',
  },
  buttonText: {
    fontSize: 18,
    color: '#333333',
    fontWeight: '500',
  },
  buttonTextSelected: {
    color: '#2E7D32',
    fontWeight: '700',
  },
});

