import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, Alert } from 'react-native';
import { SupportedLanguage } from '../i18n/catalogs';

interface FarmBoundaryScreenProps {
  language: SupportedLanguage;
  farmerId: string;
  onFarmCreated: (farm: { id: string; name: string; coordinates: [number, number]; boundary: [number, number][] }) => void;
}

export const FarmBoundaryScreen: React.FC<FarmBoundaryScreenProps> = ({ farmerId, onFarmCreated }) => {
  const [farmName, setFarmName] = useState<string>('');
  const [latitude, setLatitude] = useState<string>('17.385044');
  const [longitude, setLongitude] = useState<string>('78.486671');
  const [points, setPoints] = useState<[number, number][]>([
    [17.385044, 78.486671],
    [17.385500, 78.486671],
    [17.385500, 78.487200],
    [17.385044, 78.487200],
    [17.385044, 78.486671],
  ]);

  const handleCaptureGPS = () => {
    // Simulating GPS acquisition (e.g. from react-native-geolocation-service or Expo Location)
    const simulatedLat = 17.385044 + (Math.random() - 0.5) * 0.001;
    const simulatedLng = 78.486671 + (Math.random() - 0.5) * 0.001;
    setLatitude(simulatedLat.toFixed(6));
    setLongitude(simulatedLng.toFixed(6));
  };

  const validateAndSubmit = () => {
    const lat = parseFloat(latitude);
    const lng = parseFloat(longitude);

    if (isNaN(lat) || lat < -90 || lat > 90) {
      Alert.alert('Validation Error', 'Latitude must be between -90 and 90 (WGS84).');
      return;
    }
    if (isNaN(lng) || lng < -180 || lng > 180) {
      Alert.alert('Validation Error', 'Longitude must be between -180 and 180 (WGS84).');
      return;
    }
    if (!farmName.trim()) {
      Alert.alert('Validation Error', 'Please enter a farm name.');
      return;
    }
    if (points.length < 4) {
      Alert.alert('Validation Error', 'Boundary polygon must contain at least 3 distinct vertices and be closed.');
      return;
    }

    onFarmCreated({
      id: 'farm_' + Date.now(),
      name: farmName.trim(),
      coordinates: [lat, lng],
      boundary: points,
    });
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Farm Registration & Boundary</Text>

      <View style={styles.fieldGroup}>
        <Text style={styles.label}>Farm Name / Title</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Green Acres Plot 1"
          value={farmName}
          onChangeText={setFarmName}
        />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>WGS84 GPS Coordinates</Text>
        <Text style={styles.helper}>Accurate location coordinates ensure tamper-evident provenance.</Text>
        
        <View style={styles.coordRow}>
          <View style={styles.coordCol}>
            <Text style={styles.label}>Latitude</Text>
            <TextInput
              style={styles.input}
              value={latitude}
              onChangeText={setLatitude}
              keyboardType="numeric"
            />
          </View>
          <View style={styles.coordCol}>
            <Text style={styles.label}>Longitude</Text>
            <TextInput
              style={styles.input}
              value={longitude}
              onChangeText={setLongitude}
              keyboardType="numeric"
            />
          </View>
        </View>

        <TouchableOpacity style={styles.gpsButton} onPress={handleCaptureGPS}>
          <Text style={styles.gpsButtonText}>📍 Capture Current GPS Location</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Polygon Boundary Vertices ({points.length} points)</Text>
        <Text style={styles.helper}>Boundary forms a closed polygon geometry under EPSG:4326.</Text>
        {points.map((pt, idx) => (
          <Text key={idx} style={styles.pointText}>
            Point {idx + 1}: [{pt[0].toFixed(6)}, {pt[1].toFixed(6)}]
          </Text>
        ))}
      </View>

      <TouchableOpacity style={styles.submitBtn} onPress={validateAndSubmit}>
        <Text style={styles.submitBtnText}>Save Farm & Proceed</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: 20,
    backgroundColor: '#F8F9FA',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1B5E20',
    marginBottom: 20,
    textAlign: 'center',
  },
  fieldGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333333',
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D0D0D0',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
  },
  card: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#2E7D32',
    marginBottom: 4,
  },
  helper: {
    fontSize: 12,
    color: '#666666',
    marginBottom: 12,
  },
  coordRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  coordCol: {
    flex: 1,
  },
  gpsButton: {
    backgroundColor: '#E8F5E9',
    paddingVertical: 10,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#A5D6A7',
    alignItems: 'center',
  },
  gpsButtonText: {
    color: '#1B5E20',
    fontWeight: '600',
    fontSize: 14,
  },
  pointText: {
    fontSize: 13,
    color: '#444444',
    fontFamily: 'monospace',
    marginVertical: 2,
  },
  submitBtn: {
    backgroundColor: '#2E7D32',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 32,
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
});

