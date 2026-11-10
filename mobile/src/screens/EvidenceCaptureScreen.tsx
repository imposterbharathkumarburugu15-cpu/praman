import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Alert, ActivityIndicator } from 'react-native';
import { offlineQueue } from '../storage/offlineQueue';
import { syncService } from '../services/syncService';
import { deviceKeystore } from '../crypto/keystore';

type CaptureSource = 'CAMERA' | 'FILE_UPLOAD';
type LifecycleStage = 'SOWING' | 'VEGETATIVE' | 'FLOWERING' | 'HARVEST';

interface EvidenceCaptureScreenProps {
  farmId: string;
  farmerId: string;
  onEvidenceCaptured?: (evidenceId: string) => void;
}

export const EvidenceCaptureScreen: React.FC<EvidenceCaptureScreenProps> = ({ farmId, farmerId, onEvidenceCaptured }) => {
  const [sourceType, setSourceType] = useState<CaptureSource>('CAMERA');
  const [stage, setStage] = useState<LifecycleStage>('SOWING');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [lastSubmissionId, setLastSubmissionId] = useState<string | null>(null);

  const stages: LifecycleStage[] = ['SOWING', 'VEGETATIVE', 'FLOWERING', 'HARVEST'];

  const handleCaptureAndQueue = async () => {
    setIsProcessing(true);
    try {
      // 1. Validate on-device dimension & format requirements
      const mockImagePayload = {
        uri: 'file://storage/emulated/0/DCIM/PRAMAN_' + Date.now() + '.jpg',
        width: 1920,
        height: 1080,
        mimeType: 'image/jpeg',
        sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      };

      if (mockImagePayload.width < 640 || mockImagePayload.height < 480) {
        Alert.alert('Quality Check Failed', 'Image resolution is too low. Minimum required: 640x480.');
        setIsProcessing(false);
        return;
      }

      // 2. Prepare canonical envelope metadata
      const evidenceMetadata = {
        farm_id: farmId,
        farmer_id: farmerId,
        source: sourceType,
        stage: stage,
        timestamp_utc: new Date().toISOString(),
        image_sha256: mockImagePayload.sha256,
        schema_version: '1.0.0',
      };

      // 3. Sign using hardware-backed Android Keystore (P-256)
      const signature = await deviceKeystore.signPayload(evidenceMetadata);

      // 4. Enqueue into persistent SQLite/AsyncStorage offline queue
      const queueItem = {
        id: 'ev_' + Date.now(),
        metadata: evidenceMetadata,
        signature: signature,
        filePath: mockImagePayload.uri,
        createdAt: Date.now(),
        retryCount: 0,
        status: 'PENDING' as const,
      };

      await offlineQueue.enqueue(queueItem);
      setLastSubmissionId(queueItem.id);

      // 5. Attempt immediate opportunistic sync if connected
      await syncService.triggerSync();

      Alert.alert(
        'Evidence Captured',
        `Evidence securely recorded and signed with device hardware key.\nID: ${queueItem.id}`
      );

      if (onEvidenceCaptured) {
        onEvidenceCaptured(queueItem.id);
      }
    } catch (err: any) {
      Alert.alert('Capture Error', err?.message || 'Failed to capture and sign evidence.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Capture Farm Evidence</Text>

      {/* Source Selection */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>1. Capture Source</Text>
        <View style={styles.row}>
          <TouchableOpacity
            style={[styles.toggleBtn, sourceType === 'CAMERA' && styles.toggleBtnActive]}
            onPress={() => setSourceType('CAMERA')}
          >
            <Text style={[styles.toggleBtnText, sourceType === 'CAMERA' && styles.toggleBtnTextActive]}>
              📷 Direct Camera
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.toggleBtn, sourceType === 'FILE_UPLOAD' && styles.toggleBtnActive]}
            onPress={() => setSourceType('FILE_UPLOAD')}
          >
            <Text style={[styles.toggleBtnText, sourceType === 'FILE_UPLOAD' && styles.toggleBtnTextActive]}>
              📁 File Upload
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Crop Lifecycle Stage */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>2. Crop Lifecycle Stage</Text>
        <View style={styles.grid}>
          {stages.map((s) => (
            <TouchableOpacity
              key={s}
              style={[styles.stageBtn, stage === s && styles.stageBtnActive]}
              onPress={() => setStage(s)}
            >
              <Text style={[styles.stageBtnText, stage === s && styles.stageBtnTextActive]}>
                {s}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Capture Action */}
      <TouchableOpacity
        style={styles.captureButton}
        onPress={handleCaptureAndQueue}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.captureButtonText}>
            {sourceType === 'CAMERA' ? '📸 Take Photo & Sign' : '📂 Select File & Sign'}
          </Text>
        )}
      </TouchableOpacity>

      {lastSubmissionId && (
        <View style={styles.statusBox}>
          <Text style={styles.statusTitle}>Last Queued Evidence</Text>
          <Text style={styles.statusId}>{lastSubmissionId}</Text>
          <Text style={styles.statusDesc}>
            Persisted locally. Syncs automatically upon server acknowledgement.
          </Text>
        </View>
      )}
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
  section: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#333333',
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: '#CCCCCC',
    alignItems: 'center',
    backgroundColor: '#FAFAFA',
  },
  toggleBtnActive: {
    borderColor: '#2E7D32',
    backgroundColor: '#E8F5E9',
  },
  toggleBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666666',
  },
  toggleBtnTextActive: {
    color: '#1B5E20',
    fontWeight: '700',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  stageBtn: {
    flexBasis: '48%',
    paddingVertical: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#D0D0D0',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
  },
  stageBtnActive: {
    backgroundColor: '#2E7D32',
    borderColor: '#1B5E20',
  },
  stageBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#444444',
  },
  stageBtnTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  captureButton: {
    backgroundColor: '#2E7D32',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 20,
  },
  captureButtonText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: 'bold',
  },
  statusBox: {
    backgroundColor: '#E8F5E9',
    padding: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#C8E6C9',
    alignItems: 'center',
  },
  statusTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#2E7D32',
    textTransform: 'uppercase',
  },
  statusId: {
    fontSize: 15,
    fontFamily: 'monospace',
    color: '#1B5E20',
    marginVertical: 4,
  },
  statusDesc: {
    fontSize: 12,
    color: '#4E6B50',
    textAlign: 'center',
  },
});

