import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { translations, SupportedLanguage } from '../i18n/catalogs';

interface AuthScreenProps {
  language: SupportedLanguage;
  onAuthSuccess: (farmer: { id: string; fullName: string; phone: string }) => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ language, onAuthSuccess }) => {
  const [isRegistering, setIsRegistering] = useState<boolean>(true);
  const [fullName, setFullName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [pin, setPin] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const t = translations[language] || translations['en'];

  const handleSubmit = async () => {
    setError(null);
    if (!phone || phone.length < 10) {
      setError('Please enter a valid 10-digit mobile number.');
      return;
    }
    if (!pin || pin.length < 4) {
      setError('PIN must be at least 4 digits.');
      return;
    }
    if (isRegistering && !fullName.trim()) {
      setError('Please enter your full name.');
      return;
    }

    setLoading(true);
    try {
      // Simulate/trigger local auth or backend sync
      const mockFarmer = {
        id: 'f_' + Date.now(),
        fullName: isRegistering ? fullName.trim() : 'Registered Farmer',
        phone: phone.trim(),
      };
      onAuthSuccess(mockFarmer);
    } catch (err: any) {
      setError(err?.message || 'Authentication failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{isRegistering ? 'Farmer Registration' : 'Farmer Login'}</Text>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <View style={styles.form}>
        {isRegistering && (
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Full Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Ramesh Kumar"
              value={fullName}
              onChangeText={setFullName}
            />
          </View>
        )}

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Phone Number</Text>
          <TextInput
            style={styles.input}
            placeholder="10-digit mobile number"
            keyboardType="phone-pad"
            maxLength={10}
            value={phone}
            onChangeText={setPhone}
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Security PIN</Text>
          <TextInput
            style={styles.input}
            placeholder="4-6 digit PIN"
            secureTextEntry
            keyboardType="numeric"
            maxLength={6}
            value={pin}
            onChangeText={setPin}
          />
        </View>

        <TouchableOpacity style={styles.submitBtn} onPress={handleSubmit} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.submitBtnText}>{isRegistering ? 'Register & Continue' : 'Log In'}</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.toggleBtn}
          onPress={() => {
            setIsRegistering(!isRegistering);
            setError(null);
          }}
        >
          <Text style={styles.toggleBtnText}>
            {isRegistering
              ? 'Already registered? Log in here'
              : 'New farmer? Create an account'}
          </Text>
        </TouchableOpacity>
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
    fontSize: 26,
    fontWeight: 'bold',
    color: '#1B5E20',
    textAlign: 'center',
    marginBottom: 24,
  },
  form: {
    gap: 16,
  },
  inputGroup: {
    gap: 6,
  },
  label: {
    fontSize: 14,
    color: '#333333',
    fontWeight: '600',
  },
  input: {
    borderWidth: 1,
    borderColor: '#CCCCCC',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    backgroundColor: '#FFFFFF',
  },
  submitBtn: {
    backgroundColor: '#2E7D32',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  toggleBtn: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  toggleBtnText: {
    color: '#2E7D32',
    fontSize: 14,
    fontWeight: '600',
  },
  errorText: {
    color: '#C62828',
    backgroundColor: '#FFEBEE',
    padding: 10,
    borderRadius: 6,
    marginBottom: 12,
    textAlign: 'center',
  },
});

