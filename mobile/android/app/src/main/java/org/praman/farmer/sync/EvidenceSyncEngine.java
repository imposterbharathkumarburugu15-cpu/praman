package org.praman.farmer.sync;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONObject;
import org.praman.farmer.crypto.AndroidKeystoreBridge;
import org.praman.farmer.storage.EvidenceDbHelper;
import org.praman.farmer.storage.EvidenceRecord;

import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Real Network Sync Engine.
 * Replaces simulated timeouts with real HTTP multipart/form-data ingestion
 * targeting backend /api/v1/evidence/ingest.
 * 
 * Includes proactive device & farmer auto-enrollment to resolve HTTP 403 Forbidden
 * "Unregistered device" barriers. Supports dynamic development host URLs.
 */
public class EvidenceSyncEngine {

    private static final String TAG = "EvidenceSyncEngine";
    public static final String DEFAULT_BACKEND_URL = "http://10.90.215.142:8000";
    public static final String PREFS_NAME = "praman_farmer_prefs";
    public static final String KEY_BACKEND_URL = "praman_backend_url";
    public static final String KEY_FARMER_ID = "farmer_id";
    public static final String KEY_FARMER_NAME = "farmer_name";
    public static final String KEY_FARMER_PHONE = "farmer_phone";
    public static final String KEY_FARMER_LANG = "farmer_lang";

    private final Context context;
    private final EvidenceDbHelper dbHelper;
    private final ExecutorService executor;
    private final Handler mainHandler;
    private final SharedPreferences prefs;
    private String backendBaseUrl;
    private boolean isSyncing = false;

    public interface SyncListener {
        void onSyncStarted();
        void onItemSynced(String evidenceId, boolean success, String resultOrError);
        void onSyncFinished(int successCount, int failureCount);
    }

    private SyncListener listener;

    public EvidenceSyncEngine(Context context) {
        this.context = context.getApplicationContext();
        this.dbHelper = EvidenceDbHelper.getInstance(this.context);
        this.executor = Executors.newSingleThreadExecutor();
        this.mainHandler = new Handler(Looper.getMainLooper());
        this.prefs = this.context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

        // Load persisted backend URL or fallback to DEFAULT_BACKEND_URL
        String saved = prefs.getString(KEY_BACKEND_URL, null);
        if (saved != null && !saved.trim().isEmpty()) {
            this.backendBaseUrl = saved.trim().replaceAll("/+$", "");
        } else {
            this.backendBaseUrl = DEFAULT_BACKEND_URL;
        }
    }

    public void setBackendBaseUrl(String url) {
        if (url != null && !url.trim().isEmpty()) {
            this.backendBaseUrl = url.trim().replaceAll("/+$", "");
            prefs.edit().putString(KEY_BACKEND_URL, this.backendBaseUrl).apply();
            Log.i(TAG, "Backend base URL updated to: " + this.backendBaseUrl);
        }
    }

    public String getBackendBaseUrl() {
        return backendBaseUrl;
    }

    public void saveFarmerProfile(String farmerId, String name, String phone, String lang) {
        SharedPreferences.Editor editor = prefs.edit();
        if (farmerId != null) editor.putString(KEY_FARMER_ID, farmerId);
        if (name != null) editor.putString(KEY_FARMER_NAME, name);
        if (phone != null) editor.putString(KEY_FARMER_PHONE, phone);
        if (lang != null) editor.putString(KEY_FARMER_LANG, lang);
        editor.apply();
    }

    public void setListener(SyncListener listener) {
        this.listener = listener;
    }

    public synchronized void triggerSync() {
        if (isSyncing) {
            Log.d(TAG, "Sync already in progress, skipping trigger.");
            return;
        }
        isSyncing = true;
        if (listener != null) {
            mainHandler.post(() -> listener.onSyncStarted());
        }

        executor.execute(this::executeSyncBatch);
    }

    private void executeSyncBatch() {
        List<EvidenceRecord> pending = dbHelper.getPendingQueue();
        int successCount = 0;
        int failureCount = 0;

        for (EvidenceRecord record : pending) {
            boolean success = syncSingleItem(record);
            if (success) {
                successCount++;
            } else {
                failureCount++;
            }
        }

        isSyncing = false;
        final int finalSuccess = successCount;
        final int finalFailure = failureCount;
        if (listener != null) {
            mainHandler.post(() -> listener.onSyncFinished(finalSuccess, finalFailure));
        }
    }

    /**
     * Proactively verifies that the device and bound farmer are enrolled in backend
     * PostgreSQL database. If not found, calls POST /api/v1/farmers and POST /api/v1/devices/register
     * with genuine hardware public key PEM.
     * 
     * Resolves DEF-MOB-07 (HTTP 403 Forbidden: Unregistered device).
     */
    public boolean ensureDeviceEnrolled(String deviceId) {
        if (deviceId == null || deviceId.trim().isEmpty()) {
            Log.w(TAG, "Cannot enroll device: deviceId is null or empty");
            return false;
        }

        try {
            // 1. Check if device is already registered on backend via GET /api/v1/devices/{deviceId}
            URL checkUrl = new URL(backendBaseUrl + "/api/v1/devices/" + deviceId);
            HttpURLConnection checkConn = (HttpURLConnection) checkUrl.openConnection();
            checkConn.setConnectTimeout(4000);
            checkConn.setReadTimeout(4000);
            checkConn.setRequestMethod("GET");
            int checkCode = checkConn.getResponseCode();
            checkConn.disconnect();

            if (checkCode == HttpURLConnection.HTTP_OK) {
                Log.d(TAG, "Device " + deviceId + " is already enrolled on backend.");
                return true;
            }

            Log.i(TAG, "Device " + deviceId + " not enrolled (HTTP " + checkCode + "). Auto-enrolling now...");

            // 2. Obtain device NIST P-256 public key
            AndroidKeystoreBridge keystore = new AndroidKeystoreBridge();
            String keyJsonStr = keystore.getPublicKeyPEM("praman_device_key");
            JSONObject keyObj = new JSONObject(keyJsonStr);
            String publicKeyPem = keyObj.optString("publicKeyPem");
            if (publicKeyPem.isEmpty()) {
                Log.e(TAG, "Cannot auto-enroll device: public key is empty");
                return false;
            }

            // 3. Obtain or synthesize valid farmer profile
            String farmerId = prefs.getString(KEY_FARMER_ID, null);
            String fullName = prefs.getString(KEY_FARMER_NAME, "PRAMAN Farmer");
            String phone = prefs.getString(KEY_FARMER_PHONE, "+919848012345");
            String lang = prefs.getString(KEY_FARMER_LANG, "te");

            if (farmerId == null || farmerId.trim().isEmpty()) {
                farmerId = "farmer_" + deviceId.replaceAll("[^a-zA-Z0-9_-]", "");
            }
            if (!phone.startsWith("+91")) {
                phone = "+91" + phone.replaceAll("[^0-9]", "");
            }

            // 4. Enroll Farmer via POST /api/v1/farmers
            URL farmerUrl = new URL(backendBaseUrl + "/api/v1/farmers");
            HttpURLConnection fConn = (HttpURLConnection) farmerUrl.openConnection();
            fConn.setConnectTimeout(6000);
            fConn.setReadTimeout(6000);
            fConn.setDoOutput(true);
            fConn.setRequestMethod("POST");
            fConn.setRequestProperty("Content-Type", "application/json");

            JSONObject fPayload = new JSONObject();
            fPayload.put("id", farmerId);
            fPayload.put("farmer_id", farmerId);
            fPayload.put("full_name", fullName);
            fPayload.put("phone_number", phone);
            fPayload.put("language_pref", lang);

            try (DataOutputStream dos = new DataOutputStream(fConn.getOutputStream())) {
                dos.write(fPayload.toString().getBytes(StandardCharsets.UTF_8));
            }

            int fCode = fConn.getResponseCode();
            String actualFarmerId = farmerId;

            if (fCode == HttpURLConnection.HTTP_CONFLICT) {
                // Farmer phone already exists; login to fetch registered farmer ID
                fConn.disconnect();
                URL loginUrl = new URL(backendBaseUrl + "/api/v1/farmers/login");
                HttpURLConnection lConn = (HttpURLConnection) loginUrl.openConnection();
                lConn.setConnectTimeout(6000);
                lConn.setReadTimeout(6000);
                lConn.setDoOutput(true);
                lConn.setRequestMethod("POST");
                lConn.setRequestProperty("Content-Type", "application/json");

                JSONObject lPayload = new JSONObject();
                lPayload.put("phone_number", phone);
                try (DataOutputStream dos = new DataOutputStream(lConn.getOutputStream())) {
                    dos.write(lPayload.toString().getBytes(StandardCharsets.UTF_8));
                }

                int lCode = lConn.getResponseCode();
                if (lCode == HttpURLConnection.HTTP_OK) {
                    String lBody = readStream(lConn.getInputStream());
                    JSONObject lObj = new JSONObject(lBody);
                    if (lObj.has("id")) {
                        actualFarmerId = lObj.getString("id");
                    } else if (lObj.has("farmer") && lObj.getJSONObject("farmer").has("id")) {
                        actualFarmerId = lObj.getJSONObject("farmer").getString("id");
                    }
                    Log.i(TAG, "Farmer profile retrieved via login: " + actualFarmerId);
                }
                lConn.disconnect();
            } else if (fCode == HttpURLConnection.HTTP_CREATED || fCode == HttpURLConnection.HTTP_OK) {
                String fBody = readStream(fConn.getInputStream());
                JSONObject fRes = new JSONObject(fBody);
                if (fRes.has("id")) {
                    actualFarmerId = fRes.getString("id");
                }
                Log.i(TAG, "Farmer successfully registered: " + actualFarmerId);
                fConn.disconnect();
            } else {
                String err = readStream(fConn.getErrorStream());
                Log.w(TAG, "Farmer registration response HTTP " + fCode + ": " + err);
                fConn.disconnect();
            }

            prefs.edit().putString(KEY_FARMER_ID, actualFarmerId).apply();

            // 5. Enroll Device via POST /api/v1/devices/register
            URL devUrl = new URL(backendBaseUrl + "/api/v1/devices/register");
            HttpURLConnection dConn = (HttpURLConnection) devUrl.openConnection();
            dConn.setConnectTimeout(6000);
            dConn.setReadTimeout(6000);
            dConn.setDoOutput(true);
            dConn.setRequestMethod("POST");
            dConn.setRequestProperty("Content-Type", "application/json");

            JSONObject dPayload = new JSONObject();
            dPayload.put("device_id", deviceId);
            dPayload.put("id", deviceId);
            dPayload.put("farmer_id", actualFarmerId);
            dPayload.put("public_key_pem", publicKeyPem.trim());

            try (DataOutputStream dos = new DataOutputStream(dConn.getOutputStream())) {
                dos.write(dPayload.toString().getBytes(StandardCharsets.UTF_8));
            }

            int dCode = dConn.getResponseCode();
            if (dCode == HttpURLConnection.HTTP_CREATED || dCode == HttpURLConnection.HTTP_OK) {
                String dBody = readStream(dConn.getInputStream());
                Log.i(TAG, "Device successfully enrolled on backend: " + dBody);
                dConn.disconnect();
                return true;
            } else {
                String err = readStream(dConn.getErrorStream());
                Log.e(TAG, "Device registration failed with HTTP " + dCode + ": " + err);
                dConn.disconnect();
                return false;
            }

        } catch (Exception e) {
            Log.e(TAG, "Exception during auto-enrollment for " + deviceId, e);
            return false;
        }
    }

    private static String readStream(InputStream is) {
        if (is == null) return "";
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    public boolean syncSingleItem(EvidenceRecord record) {
        String evidenceId = record.getEvidenceId();
        String deviceId = record.getDeviceId();
        dbHelper.updateStatus(evidenceId, "SYNCING", null, null, record.getRetryCount());

        // Proactively ensure device is enrolled on backend
        ensureDeviceEnrolled(deviceId);

        return executeUploadAttempt(record, true);
    }

    private boolean executeUploadAttempt(EvidenceRecord record, boolean allowReEnrollRetry) {
        String evidenceId = record.getEvidenceId();
        HttpURLConnection conn = null;
        try {
            String boundary = "===PramanBoundary" + UUID.randomUUID().toString() + "===";
            String lineEnd = "\r\n";
            String twoHyphens = "--";

            URL url = new URL(backendBaseUrl + "/api/v1/evidence/ingest");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(30000);
            conn.setDoInput(true);
            conn.setDoOutput(true);
            conn.setUseCaches(false);
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Connection", "Keep-Alive");
            conn.setRequestProperty("User-Agent", "PRAMAN-Farmer-Android/1.0");
            conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);

            DataOutputStream dos = new DataOutputStream(conn.getOutputStream());

            // 1. Envelope part
            dos.writeBytes(twoHyphens + boundary + lineEnd);
            dos.writeBytes("Content-Disposition: form-data; name=\"envelope\"" + lineEnd);
            dos.writeBytes("Content-Type: application/json; charset=UTF-8" + lineEnd);
            dos.writeBytes(lineEnd);
            byte[] envelopeBytes = record.getEnvelopeJson().getBytes(StandardCharsets.UTF_8);
            dos.write(envelopeBytes);
            dos.writeBytes(lineEnd);

            // 2. Signature part
            dos.writeBytes(twoHyphens + boundary + lineEnd);
            dos.writeBytes("Content-Disposition: form-data; name=\"signature\"" + lineEnd);
            dos.writeBytes("Content-Type: text/plain; charset=UTF-8" + lineEnd);
            dos.writeBytes(lineEnd);
            dos.writeBytes(record.getSignatureB64());
            dos.writeBytes(lineEnd);

            // 3. File part (raw image binary)
            File imageFile = new File(record.getRawFilePath());
            if (!imageFile.exists() || imageFile.length() == 0) {
                throw new IllegalStateException("Raw evidence image file missing at: " + record.getRawFilePath());
            }

            dos.writeBytes(twoHyphens + boundary + lineEnd);
            dos.writeBytes("Content-Disposition: form-data; name=\"file\"; filename=\"" + imageFile.getName() + "\"" + lineEnd);
            dos.writeBytes("Content-Type: image/jpeg" + lineEnd);
            dos.writeBytes("Content-Transfer-Encoding: binary" + lineEnd);
            dos.writeBytes(lineEnd);

            try (FileInputStream fis = new FileInputStream(imageFile)) {
                byte[] buffer = new byte[16384];
                int bytesRead;
                while ((bytesRead = fis.read(buffer)) != -1) {
                    dos.write(buffer, 0, bytesRead);
                }
            }
            dos.writeBytes(lineEnd);

            // End of multipart
            dos.writeBytes(twoHyphens + boundary + twoHyphens + lineEnd);
            dos.flush();
            dos.close();

            int statusCode = conn.getResponseCode();
            InputStream responseStream = (statusCode >= 200 && statusCode < 400)
                    ? conn.getInputStream()
                    : conn.getErrorStream();

            String responseBody = readStream(responseStream);

            if (statusCode == HttpURLConnection.HTTP_CREATED || statusCode == HttpURLConnection.HTTP_OK) {
                // Success: Durably acknowledged by backend
                dbHelper.updateStatus(evidenceId, "SYNCED", responseBody, null, record.getRetryCount());
                Log.i(TAG, "Evidence " + evidenceId + " successfully synced to backend: " + responseBody);

                if (listener != null) {
                    mainHandler.post(() -> listener.onItemSynced(evidenceId, true, responseBody));
                }
                return true;
            } else if (statusCode == HttpURLConnection.HTTP_FORBIDDEN && allowReEnrollRetry) {
                // If backend returned HTTP 403 Forbidden (Unregistered device), force re-enrollment and retry once
                Log.w(TAG, "Received HTTP 403 Forbidden on upload. Attempting auto-enrollment retry...");
                conn.disconnect();
                conn = null;

                boolean enrolled = ensureDeviceEnrolled(record.getDeviceId());
                if (enrolled) {
                    return executeUploadAttempt(record, false);
                }
            }

            int newRetry = record.getRetryCount() + 1;
            String errorMsg = "HTTP " + statusCode + ": " + responseBody;
            dbHelper.updateStatus(evidenceId, "FAILED", null, errorMsg, newRetry);
            Log.w(TAG, "Evidence " + evidenceId + " sync failed: " + errorMsg);

            if (listener != null) {
                mainHandler.post(() -> listener.onItemSynced(evidenceId, false, errorMsg));
            }
            return false;

        } catch (Exception e) {
            int newRetry = record.getRetryCount() + 1;
            String errorMsg = "Network error: " + e.getMessage();
            dbHelper.updateStatus(evidenceId, "FAILED", null, errorMsg, newRetry);
            Log.e(TAG, "Exception during evidence sync " + evidenceId, e);

            if (listener != null) {
                mainHandler.post(() -> listener.onItemSynced(evidenceId, false, errorMsg));
            }
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }
}
