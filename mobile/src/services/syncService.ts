import { offlineQueue, QueuedEvidence } from "../storage/offlineQueue";

export interface SyncResult {
  evidence_id: string;
  status: "DURABLY_ACKED" | "FAILED" | "RETRY_QUEUED";
  http_status?: number;
  error?: string;
}

export class OfflineSyncService {
  private backendBaseUrl: string;

  constructor(baseUrl: string = "http://localhost:8000/api/v1") {
    this.backendBaseUrl = baseUrl;
  }

  async syncItem(item: QueuedEvidence, mockFetch?: typeof fetch): Promise<SyncResult> {
    const fetchFn = mockFetch || fetch;
    offlineQueue.updateState(item.evidence_id, "SYNCING");

    try {
      const formData = new FormData();
      formData.append("envelope", item.envelope_json);
      formData.append("signature", item.signature_b64);
      // Mock or real blob
      formData.append("image", new Blob([new Uint8Array([0x01, 0x02])]), "evidence.jpg");

      const response = await fetchFn(`${this.backendBaseUrl}/evidence/ingest`, {
        method: "POST",
        body: formData,
      });

      if (response.ok || response.status === 200 || response.status === 201) {
        offlineQueue.markDurablyAcked(item.evidence_id);
        return {
          evidence_id: item.evidence_id,
          status: "DURABLY_ACKED",
          http_status: response.status,
        };
      } else {
        offlineQueue.recordFailure(item.evidence_id);
        return {
          evidence_id: item.evidence_id,
          status: "FAILED",
          http_status: response.status,
          error: `Server responded with ${response.status}`,
        };
      }
    } catch (err: unknown) {
      offlineQueue.recordFailure(item.evidence_id);
      return {
        evidence_id: item.evidence_id,
        status: "RETRY_QUEUED",
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  async syncAllPending(deviceId?: string): Promise<SyncResult[]> {
    const pending = offlineQueue.getPendingItems(deviceId);
    const results: SyncResult[] = [];
    for (const item of pending) {
      const res = await this.syncItem(item);
      results.push(res);
    }
    return results;
  }
}

export const syncService = new OfflineSyncService();

