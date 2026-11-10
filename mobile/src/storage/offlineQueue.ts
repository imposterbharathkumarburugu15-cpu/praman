export interface QueuedEvidence {
  evidence_id: string;
  device_id: string;
  sequence_number: number;
  envelope_json: string;
  signature_b64: string;
  image_path: string;
  image_hash: string;
  sync_state: "QUEUED" | "SYNCING" | "DURABLY_ACKED" | "FAILED";
  retries: number;
  created_at: string;
}

export class OfflineStorageQueue {
  private queue: Map<string, QueuedEvidence> = new Map();

  enqueue(item: Omit<QueuedEvidence, "sync_state" | "retries" | "created_at">): QueuedEvidence {
    const entry: QueuedEvidence = {
      ...item,
      sync_state: "QUEUED",
      retries: 0,
      created_at: new Date().toISOString(),
    };
    this.queue.set(entry.evidence_id, entry);
    return entry;
  }

  getPendingItems(deviceId?: string): QueuedEvidence[] {
    const items = Array.from(this.queue.values()).filter(
      (i) => i.sync_state === "QUEUED" && (!deviceId || i.device_id === deviceId)
    );
    // Strict FIFO ordering by sequence number
    return items.sort((a, b) => a.sequence_number - b.sequence_number);
  }

  getItem(evidenceId: string): QueuedEvidence | undefined {
    return this.queue.get(evidenceId);
  }

  updateState(evidenceId: string, state: QueuedEvidence["sync_state"]): void {
    const item = this.queue.get(evidenceId);
    if (item) {
      item.sync_state = state;
    }
  }

  recordFailure(evidenceId: string): void {
    const item = this.queue.get(evidenceId);
    if (item) {
      item.retries += 1;
      if (item.retries >= 3) {
        item.sync_state = "FAILED";
      } else {
        item.sync_state = "QUEUED";
      }
    }
  }

  markDurablyAcked(evidenceId: string): void {
    const item = this.queue.get(evidenceId);
    if (item) {
      item.sync_state = "DURABLY_ACKED";
    }
  }
}

export const offlineQueue = new OfflineStorageQueue();

