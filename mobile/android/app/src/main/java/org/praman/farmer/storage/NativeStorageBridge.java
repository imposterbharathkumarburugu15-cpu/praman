package org.praman.farmer.storage;

import android.content.Context;
import android.webkit.JavascriptInterface;

import org.json.JSONArray;
import org.json.JSONObject;
import org.praman.farmer.sync.EvidenceSyncEngine;

import java.util.List;

/**
 * JavaScript interface bridge connecting WebView with native SQLite persistence
 * and network synchronization.
 */
public class NativeStorageBridge {

    private final Context context;
    private final EvidenceDbHelper dbHelper;
    private final EvidenceSyncEngine syncEngine;

    public NativeStorageBridge(Context context, EvidenceSyncEngine syncEngine) {
        this.context = context.getApplicationContext();
        this.dbHelper = EvidenceDbHelper.getInstance(this.context);
        this.syncEngine = syncEngine;
    }

    @JavascriptInterface
    public String saveEvidence(String recordJsonStr) {
        try {
            JSONObject obj = new JSONObject(recordJsonStr);
            EvidenceRecord record = EvidenceRecord.fromJson(obj);

            if (record.getCreatedAt() == null || record.getCreatedAt().isEmpty()) {
                record.setCreatedAt(String.valueOf(System.currentTimeMillis()));
            }
            record.setUpdatedAt(String.valueOf(System.currentTimeMillis()));

            long rowId = dbHelper.insertOrUpdate(record);

            JSONObject res = new JSONObject();
            res.put("success", rowId != -1);
            res.put("evidence_id", record.getEvidenceId());
            res.put("sequence_number", record.getSequenceNumber());
            return res.toString();
        } catch (Exception e) {
            return "{\"success\": false, \"error\": \"" + e.getMessage() + "\"}";
        }
    }

    @JavascriptInterface
    public String getAllEvidence() {
        try {
            List<EvidenceRecord> list = dbHelper.getAllEvidence();
            JSONArray arr = new JSONArray();
            for (EvidenceRecord r : list) {
                arr.put(r.toJson());
            }
            return arr.toString();
        } catch (Exception e) {
            return "[]";
        }
    }

    @JavascriptInterface
    public String getPendingQueue() {
        try {
            List<EvidenceRecord> list = dbHelper.getPendingQueue();
            JSONArray arr = new JSONArray();
            for (EvidenceRecord r : list) {
                arr.put(r.toJson());
            }
            return arr.toString();
        } catch (Exception e) {
            return "[]";
        }
    }

    @JavascriptInterface
    public int getNextSequenceNumber(String deviceId) {
        return dbHelper.getNextSequenceNumber(deviceId);
    }

    @JavascriptInterface
    public void triggerSync(String customUrl) {
        if (customUrl != null && !customUrl.trim().isEmpty()) {
            syncEngine.setBackendBaseUrl(customUrl.trim());
        }
        syncEngine.triggerSync();
    }

    @JavascriptInterface
    public void setBackendUrl(String url) {
        syncEngine.setBackendBaseUrl(url);
    }

    @JavascriptInterface
    public String getBackendUrl() {
        return syncEngine.getBackendBaseUrl();
    }

    @JavascriptInterface
    public void saveFarmerProfile(String farmerId, String name, String phone, String lang) {
        syncEngine.saveFarmerProfile(farmerId, name, phone, lang);
    }

    @JavascriptInterface
    public boolean enrollDevice(String deviceId) {
        return syncEngine.ensureDeviceEnrolled(deviceId);
    }

    @JavascriptInterface
    public boolean deleteEvidence(String evidenceId) {
        try {
            dbHelper.deleteEvidence(evidenceId);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public boolean clearAll() {
        try {
            dbHelper.clearAll();
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
