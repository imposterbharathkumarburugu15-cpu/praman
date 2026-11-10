/**
 * Shared cryptographic TypeScript types and schemas for PRAMAN.
 */

export type LifecycleStage =
  | "SOWING"
  | "INPUT_APPLICATION"
  | "CROP_GROWTH"
  | "HARVEST"
  | "STORAGE";

export type CaptureSource = "CAMERA" | "FILE_UPLOAD";

export interface EvidenceMetadata {
  capture_source: CaptureSource;
  capture_timestamp: string; // ISO 8601 UTC timestamp
  gps_accuracy: number;
  latitude: number;
  longitude: number;
}

export interface EvidenceEnvelope {
  device_id: string;
  evidence_id: string;
  farm_id: string;
  image_hash: string;
  lifecycle_stage: LifecycleStage;
  metadata: EvidenceMetadata;
  schema_version: string;
  sequence_number: number;
}

export interface InclusionProofStep {
  position: "left" | "right";
  hash: string; // 64-character lowercase hex string
}
