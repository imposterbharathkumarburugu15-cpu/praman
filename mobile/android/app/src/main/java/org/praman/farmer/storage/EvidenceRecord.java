package org.praman.farmer.storage;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * Data model representing a persistent offline evidence record.
 */
public class EvidenceRecord {
    private String evidenceId;
    private String deviceId;
    private String farmId;
    private int sequenceNumber;
    private String lifecycleStage;
    private String captureSource;
    private String rawFilePath;
    private String imageHash;
    private String envelopeJson;
    private String signatureB64;
    private String status;
    private int retryCount;
    private String serverReceipt;
    private String errorMessage;
    private String createdAt;
    private String updatedAt;

    public EvidenceRecord() {
        this.status = "QUEUED";
        this.retryCount = 0;
    }

    public static EvidenceRecord fromJson(JSONObject json) {
        EvidenceRecord record = new EvidenceRecord();
        record.setEvidenceId(json.optString("evidence_id", ""));
        record.setDeviceId(json.optString("device_id", ""));
        record.setFarmId(json.optString("farm_id", ""));
        record.setSequenceNumber(json.optInt("sequence_number", 1));
        record.setLifecycleStage(json.optString("lifecycle_stage", "SOWING"));
        record.setCaptureSource(json.optString("capture_source", "CAMERA"));
        record.setRawFilePath(json.optString("raw_file_path", ""));
        record.setImageHash(json.optString("image_hash", ""));
        record.setEnvelopeJson(json.optString("envelope_json", ""));
        record.setSignatureB64(json.optString("signature_b64", ""));
        record.setStatus(json.optString("status", "QUEUED"));
        record.setRetryCount(json.optInt("retry_count", 0));
        record.setServerReceipt(json.optString("server_receipt", ""));
        record.setErrorMessage(json.optString("error_message", ""));
        record.setCreatedAt(json.optString("created_at", ""));
        record.setUpdatedAt(json.optString("updated_at", ""));
        return record;
    }

    public JSONObject toJson() {
        JSONObject json = new JSONObject();
        try {
            json.put("evidence_id", evidenceId);
            json.put("device_id", deviceId);
            json.put("farm_id", farmId);
            json.put("sequence_number", sequenceNumber);
            json.put("lifecycle_stage", lifecycleStage);
            json.put("capture_source", captureSource);
            json.put("raw_file_path", rawFilePath);
            json.put("image_hash", imageHash);
            json.put("envelope_json", envelopeJson);
            json.put("signature_b64", signatureB64);
            json.put("status", status);
            json.put("retry_count", retryCount);
            json.put("server_receipt", serverReceipt);
            json.put("error_message", errorMessage);
            json.put("created_at", createdAt);
            json.put("updated_at", updatedAt);
        } catch (JSONException ignored) {
        }
        return json;
    }

    // Getters and Setters
    public String getEvidenceId() { return evidenceId; }
    public void setEvidenceId(String evidenceId) { this.evidenceId = evidenceId; }

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getFarmId() { return farmId; }
    public void setFarmId(String farmId) { this.farmId = farmId; }

    public int getSequenceNumber() { return sequenceNumber; }
    public void setSequenceNumber(int sequenceNumber) { this.sequenceNumber = sequenceNumber; }

    public String getLifecycleStage() { return lifecycleStage; }
    public void setLifecycleStage(String lifecycleStage) { this.lifecycleStage = lifecycleStage; }

    public String getCaptureSource() { return captureSource; }
    public void setCaptureSource(String captureSource) { this.captureSource = captureSource; }

    public String getRawFilePath() { return rawFilePath; }
    public void setRawFilePath(String rawFilePath) { this.rawFilePath = rawFilePath; }

    public String getImageHash() { return imageHash; }
    public void setImageHash(String imageHash) { this.imageHash = imageHash; }

    public String getEnvelopeJson() { return envelopeJson; }
    public void setEnvelopeJson(String envelopeJson) { this.envelopeJson = envelopeJson; }

    public String getSignatureB64() { return signatureB64; }
    public void setSignatureB64(String signatureB64) { this.signatureB64 = signatureB64; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public int getRetryCount() { return retryCount; }
    public void setRetryCount(int retryCount) { this.retryCount = retryCount; }

    public String getServerReceipt() { return serverReceipt; }
    public void setServerReceipt(String serverReceipt) { this.serverReceipt = serverReceipt; }

    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }

    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt; }
}
