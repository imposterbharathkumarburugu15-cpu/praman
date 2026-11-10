package org.praman.farmer.connectivity;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import org.json.JSONException;
import org.json.JSONObject;
import org.praman.farmer.sync.EvidenceSyncEngine;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Genuine Three-Tier Connectivity Detection Bridge.
 * Replaces simulated/hardcoded offline badges with real-time network capability inspection,
 * internet reachability probing, and PRAMAN backend health checks.
 *
 * Tier A: Device network state (No network, Wi-Fi connected, Mobile data connected, Network unvalidated)
 * Tier B: Internet reachability (probe actual internet gateway)
 * Tier C: PRAMAN backend reachability (probe /api/v1/health on configured backend URL)
 *
 * Combinations:
 * - ONLINE: backend reachable
 * - INTERNET_AVAILABLE: backend unavailable, internet reachable
 * - CONNECTED: internet not validated, network interface up
 * - OFFLINE: no usable network
 *
 * Fully supports Mobile Cellular Data without requiring Wi-Fi.
 */
public class NativeConnectivityBridge {

    private static final String TAG = "NativeConnectivityBridge";
    private static final String PREF_NAME = "praman_connectivity_prefs";
    private static final String PREF_BACKEND_URL = "backend_base_url";

    // Primary Status Categories
    public static final String STATUS_ONLINE = "ONLINE";
    public static final String STATUS_INTERNET_AVAILABLE = "INTERNET_AVAILABLE";
    public static final String STATUS_CONNECTED = "CONNECTED";
    public static final String STATUS_OFFLINE = "OFFLINE";

    // Network Interface Types
    public static final String NET_NONE = "NONE";
    public static final String NET_WIFI = "WIFI";
    public static final String NET_CELLULAR = "CELLULAR";
    public static final String NET_ETHERNET = "ETHERNET";
    public static final String NET_OTHER = "OTHER";

    private final Context context;
    private final ConnectivityManager connectivityManager;
    private final ExecutorService executor;
    private final Handler mainHandler;
    private final SharedPreferences prefs;

    private WebView webView;
    private EvidenceSyncEngine syncEngine;

    private String backendUrl;
    private String networkType = NET_NONE;
    private boolean isNetworkConnected = false;
    private boolean isInternetValidatedByOs = false;
    private boolean isInternetReachable = false;
    private boolean isBackendReachable = false;
    private String currentOverallStatus = STATUS_OFFLINE;
    private String lastBackendHealthResponse = null;
    private long lastProbeTimestamp = 0;

    private final AtomicBoolean isProbing = new AtomicBoolean(false);
    private ConnectivityManager.NetworkCallback networkCallback;

    public NativeConnectivityBridge(Context context) {
        this(context, null, null);
    }

    public NativeConnectivityBridge(Context context, @Nullable WebView webView, @Nullable EvidenceSyncEngine syncEngine) {
        this.context = context.getApplicationContext();
        this.webView = webView;
        this.syncEngine = syncEngine;
        this.connectivityManager = (ConnectivityManager) this.context.getSystemService(Context.CONNECTIVITY_SERVICE);
        this.executor = Executors.newSingleThreadExecutor();
        this.mainHandler = new Handler(Looper.getMainLooper());
        this.prefs = this.context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);

        // Load persisted backend URL or fallback to default
        String savedUrl = prefs.getString(PREF_BACKEND_URL, null);
        if (savedUrl != null && !savedUrl.trim().isEmpty()) {
            this.backendUrl = savedUrl.trim().replaceAll("/+$", "");
        } else if (syncEngine != null && syncEngine.getBackendBaseUrl() != null) {
            this.backendUrl = syncEngine.getBackendBaseUrl();
        } else {
            this.backendUrl = EvidenceSyncEngine.DEFAULT_BACKEND_URL;
        }

        if (syncEngine != null) {
            syncEngine.setBackendBaseUrl(this.backendUrl);
        }

        registerNetworkCallbacks();
        checkReachabilityAsync();
    }

    public void setWebView(WebView webView) {
        this.webView = webView;
    }

    public void setSyncEngine(EvidenceSyncEngine syncEngine) {
        this.syncEngine = syncEngine;
        if (this.syncEngine != null && this.backendUrl != null) {
            this.syncEngine.setBackendBaseUrl(this.backendUrl);
        }
    }

    private void registerNetworkCallbacks() {
        if (connectivityManager == null) return;

        NetworkRequest request = new NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .build();

        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(@NonNull Network network) {
                Log.d(TAG, "Network became available: " + network);
                triggerDelayedReachabilityCheck(500);
            }

            @Override
            public void onLost(@NonNull Network network) {
                Log.d(TAG, "Network lost: " + network);
                triggerDelayedReachabilityCheck(300);
            }

            @Override
            public void onCapabilitiesChanged(@NonNull Network network, @NonNull NetworkCapabilities capabilities) {
                Log.d(TAG, "Network capabilities changed: " + capabilities);
                triggerDelayedReachabilityCheck(500);
            }
        };

        try {
            connectivityManager.registerDefaultNetworkCallback(networkCallback);
            Log.i(TAG, "Default network callback registered");
        } catch (Exception e) {
            try {
                connectivityManager.registerNetworkCallback(request, networkCallback);
                Log.i(TAG, "Network callback registered with request");
            } catch (Exception ex) {
                Log.e(TAG, "Failed to register network callback", ex);
            }
        }
    }

    private void triggerDelayedReachabilityCheck(long delayMs) {
        mainHandler.postDelayed(this::checkReachabilityAsync, delayMs);
    }

    /**
     * Inspects active network capabilities on device (Tier A).
     */
    public synchronized void inspectDeviceNetworkState() {
        if (connectivityManager == null) {
            networkType = NET_NONE;
            isNetworkConnected = false;
            isInternetValidatedByOs = false;
            return;
        }

        Network activeNetwork = connectivityManager.getActiveNetwork();
        if (activeNetwork == null) {
            networkType = NET_NONE;
            isNetworkConnected = false;
            isInternetValidatedByOs = false;
            return;
        }

        NetworkCapabilities capabilities = connectivityManager.getNetworkCapabilities(activeNetwork);
        if (capabilities == null) {
            networkType = NET_NONE;
            isNetworkConnected = false;
            isInternetValidatedByOs = false;
            return;
        }

        isNetworkConnected = capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        isInternetValidatedByOs = capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);

        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
            networkType = NET_WIFI;
        } else if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
            networkType = NET_CELLULAR;
        } else if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
            networkType = NET_ETHERNET;
        } else {
            networkType = NET_OTHER;
        }
    }

    /**
     * Probes actual internet reachability (Tier B).
     * Connects to public DNS port 53 or HTTP 204 endpoint.
     */
    public boolean probeInternetReachability() {
        // Method 1: Lightweight socket connection to Cloudflare/Google public DNS (port 53)
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("8.8.8.8", 53), 2500);
            return true;
        } catch (Exception ignored) {}

        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("1.1.1.1", 53), 2500);
            return true;
        } catch (Exception ignored) {}

        // Method 2: HTTP 204 captive portal probe
        try {
            URL url = new URL("http://connectivitycheck.gstatic.com/generate_204");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(3000);
            conn.setUseCaches(false);
            conn.setRequestMethod("GET");
            int code = conn.getResponseCode();
            conn.disconnect();
            return (code == 204 || (code >= 200 && code < 300));
        } catch (Exception ignored) {}

        return false;
    }

    /**
     * Probes PRAMAN backend /api/v1/health (Tier C).
     */
    public boolean probeBackendReachability() {
        if (backendUrl == null || backendUrl.trim().isEmpty()) {
            return false;
        }

        HttpURLConnection conn = null;
        try {
            String target = backendUrl.replaceAll("/+$", "") + "/api/v1/health";
            URL url = new URL(target);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(3500);
            conn.setReadTimeout(3500);
            conn.setUseCaches(false);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "PRAMAN-Android-Connectivity/1.0");

            int code = conn.getResponseCode();
            InputStream is = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
            StringBuilder sb = new StringBuilder();
            if (is != null) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line);
                    }
                }
            }
            String body = sb.toString();
            lastBackendHealthResponse = body;

            if (code == HttpURLConnection.HTTP_OK && body.contains("\"status\"")) {
                Log.i(TAG, "PRAMAN backend healthy at " + target + ": " + body);
                return true;
            } else {
                Log.w(TAG, "Backend responded with code " + code + ": " + body);
                return false;
            }
        } catch (Exception e) {
            Log.d(TAG, "Backend probe failed for " + backendUrl + ": " + e.getMessage());
            lastBackendHealthResponse = "Unreachable: " + e.getMessage();
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /**
     * Executes the full three-tier diagnostic in background.
     */
    public void checkReachabilityAsync() {
        if (isProbing.compareAndSet(false, true)) {
            executor.execute(() -> {
                try {
                    // Tier A: Device interface
                    inspectDeviceNetworkState();

                    if (!isNetworkConnected && NET_NONE.equals(networkType)) {
                        isInternetReachable = false;
                        isBackendReachable = false;
                        currentOverallStatus = STATUS_OFFLINE;
                    } else {
                        // Tier B: Internet reachability
                        isInternetReachable = probeInternetReachability();

                        // Tier C: PRAMAN backend reachability
                        isBackendReachable = probeBackendReachability();

                        // Compute combinations per ORIGINAL_REQUEST §6
                        if (isBackendReachable) {
                            currentOverallStatus = STATUS_ONLINE;
                        } else if (isInternetReachable) {
                            currentOverallStatus = STATUS_INTERNET_AVAILABLE;
                        } else if (isNetworkConnected) {
                            currentOverallStatus = STATUS_CONNECTED;
                        } else {
                            currentOverallStatus = STATUS_OFFLINE;
                        }
                    }

                    lastProbeTimestamp = System.currentTimeMillis();
                    notifyConnectivityChanged();

                } finally {
                    isProbing.set(false);
                }
            });
        }
    }

    private void notifyConnectivityChanged() {
        if (webView == null) return;
        mainHandler.post(() -> {
            try {
                JSONObject payload = buildStatusJson();
                String js = String.format(Locale.US,
                        "if(window.app && window.app.onConnectivityChanged){window.app.onConnectivityChanged(%s);}",
                        payload.toString());
                webView.evaluateJavascript(js, null);
            } catch (Exception e) {
                Log.w(TAG, "Failed to dispatch connectivity event to WebView", e);
            }
        });
    }

    public JSONObject buildStatusJson() {
        JSONObject obj = new JSONObject();
        try {
            obj.put("status", currentOverallStatus);
            obj.put("displayStatus", getDisplayStatusString(currentOverallStatus));
            obj.put("networkType", networkType);
            obj.put("isConnected", isNetworkConnected);
            obj.put("isInternetValidatedByOs", isInternetValidatedByOs);
            obj.put("hasInternet", isInternetReachable);
            obj.put("backendReachable", isBackendReachable);
            obj.put("backendUrl", backendUrl);
            obj.put("timestamp", lastProbeTimestamp);
            obj.put("backendHealth", lastBackendHealthResponse != null ? lastBackendHealthResponse : "");

            String description;
            switch (currentOverallStatus) {
                case STATUS_ONLINE:
                    description = String.format(Locale.US, "Online: Backend reachable via %s", networkType);
                    break;
                case STATUS_INTERNET_AVAILABLE:
                    description = String.format(Locale.US, "Internet available: Backend unreachable at %s", backendUrl);
                    break;
                case STATUS_CONNECTED:
                    description = String.format(Locale.US, "Connected: %s interface up, internet not validated", networkType);
                    break;
                case STATUS_OFFLINE:
                default:
                    description = "Offline: No usable network interface";
                    break;
            }
            obj.put("description", description);

        } catch (JSONException ignored) {}
        return obj;
    }

    public static String getDisplayStatusString(String status) {
        if (STATUS_ONLINE.equals(status)) return "Online";
        if (STATUS_INTERNET_AVAILABLE.equals(status)) return "Internet available";
        if (STATUS_CONNECTED.equals(status)) return "Connected";
        return "Offline";
    }

    // --- JavaScript Interface APIs ---

    @JavascriptInterface
    public String getNetworkState() {
        return buildStatusJson().toString();
    }

    @JavascriptInterface
    public String checkReachability() {
        checkReachabilityAsync();
        return buildStatusJson().toString();
    }

    @JavascriptInterface
    public void setBackendUrl(String url) {
        if (url != null && !url.trim().isEmpty()) {
            this.backendUrl = url.trim().replaceAll("/+$", "");
            prefs.edit().putString(PREF_BACKEND_URL, this.backendUrl).apply();
            if (syncEngine != null) {
                syncEngine.setBackendBaseUrl(this.backendUrl);
            }
            Log.i(TAG, "Configured backend URL updated to: " + this.backendUrl);
            checkReachabilityAsync();
        }
    }

    @JavascriptInterface
    public String getBackendUrl() {
        return this.backendUrl;
    }

    @JavascriptInterface
    public String getDetailedDiagnostic() {
        inspectDeviceNetworkState();
        JSONObject obj = buildStatusJson();
        try {
            obj.put("tierA_deviceNetwork", networkType);
            obj.put("tierA_connected", isNetworkConnected);
            obj.put("tierB_internetReachable", isInternetReachable);
            obj.put("tierC_backendReachable", isBackendReachable);
            obj.put("tierC_backendUrl", backendUrl);
        } catch (JSONException ignored) {}
        return obj.toString();
    }

    public void onDestroy() {
        if (connectivityManager != null && networkCallback != null) {
            try {
                connectivityManager.unregisterNetworkCallback(networkCallback);
            } catch (Exception ignored) {}
        }
        executor.shutdown();
    }
}
