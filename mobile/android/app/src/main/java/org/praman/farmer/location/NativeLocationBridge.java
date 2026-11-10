package org.praman.farmer.location;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.location.LocationProvider;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Locale;

/**
 * Genuine Android Hardware Location Bridge.
 * Replaces simulated/hardcoded coordinates with real Android LocationManager acquisition
 * using GPS_PROVIDER with fallback to NETWORK_PROVIDER.
 * 
 * Enforces strict operational states:
 * - ACQUIRING: actively searching for GPS / Network satellite fix
 * - LOCATION_ACQUIRED: genuine location obtained meeting accuracy criteria
 * - ACCURACY_INSUFFICIENT: location obtained but error exceeds accuracy threshold
 * - PERMISSION_REQUIRED: ACCESS_FINE_LOCATION or ACCESS_COARSE_LOCATION missing
 * - GPS_UNAVAILABLE: hardware GPS sensor or providers disabled by device user
 * - LOCATION_UNAVAILABLE: fix timed out or hardware returned no coordinate observation
 */
public class NativeLocationBridge implements LocationListener {

    private static final String TAG = "NativeLocationBridge";
    public static final int REQUEST_LOCATION_PERMISSION_CODE = 2002;

    // Defined States per ORIGINAL_REQUEST §2
    public static final String STATE_ACQUIRING = "ACQUIRING";
    public static final String STATE_LOCATION_ACQUIRED = "LOCATION_ACQUIRED";
    public static final String STATE_ACCURACY_INSUFFICIENT = "ACCURACY_INSUFFICIENT";
    public static final String STATE_PERMISSION_REQUIRED = "PERMISSION_REQUIRED";
    public static final String STATE_GPS_UNAVAILABLE = "GPS_UNAVAILABLE";
    public static final String STATE_LOCATION_UNAVAILABLE = "LOCATION_UNAVAILABLE";

    private final Context context;
    private final LocationManager locationManager;
    private final Handler mainHandler;
    private WebView webView;

    private float accuracyThresholdMeters = 25.0f; // Standard agricultural GPS accuracy threshold
    private long acquisitionTimeoutMs = 15000;     // 15 seconds acquisition timeout
    private String currentState = STATE_ACQUIRING;
    private Location lastLocation = null;
    private boolean isListening = false;
    private String lastErrorMessage = null;

    private final Runnable timeoutRunnable = new Runnable() {
        @Override
        public void run() {
            if (isListening && (lastLocation == null || !STATE_LOCATION_ACQUIRED.equals(currentState))) {
                Log.w(TAG, "Location acquisition timed out after " + acquisitionTimeoutMs + "ms");
                if (lastLocation == null) {
                    currentState = STATE_LOCATION_UNAVAILABLE;
                    lastErrorMessage = "Location acquisition timed out. No GPS satellite or network fix.";
                } else if (lastLocation.getAccuracy() > accuracyThresholdMeters) {
                    currentState = STATE_ACCURACY_INSUFFICIENT;
                    lastErrorMessage = String.format(Locale.US,
                            "Fix accuracy (±%.1fm) exceeds threshold (±%.1fm).",
                            lastLocation.getAccuracy(), accuracyThresholdMeters);
                }
                notifyStateChanged();
            }
        }
    };

    public NativeLocationBridge(Context context) {
        this(context, null);
    }

    public NativeLocationBridge(Context context, @Nullable WebView webView) {
        this.context = context.getApplicationContext();
        this.webView = webView;
        this.locationManager = (LocationManager) this.context.getSystemService(Context.LOCATION_SERVICE);
        this.mainHandler = new Handler(Looper.getMainLooper());
        checkInitialStatus();
    }

    public void setWebView(WebView webView) {
        this.webView = webView;
    }

    private void checkInitialStatus() {
        if (!hasLocationPermission()) {
            currentState = STATE_PERMISSION_REQUIRED;
            lastErrorMessage = "Location permission not granted. ACCESS_FINE_LOCATION required.";
        } else if (!isAnyProviderEnabled()) {
            currentState = STATE_GPS_UNAVAILABLE;
            lastErrorMessage = "Location services disabled on device. Enable GPS in Settings.";
        } else {
            currentState = STATE_ACQUIRING;
            lastErrorMessage = null;
        }
    }

    @JavascriptInterface
    public boolean hasLocationPermission() {
        boolean fine = ContextCompat.checkSelfPermission(context,
                Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean coarse = ContextCompat.checkSelfPermission(context,
                Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        return fine || coarse;
    }

    @JavascriptInterface
    public boolean isGpsEnabled() {
        if (locationManager == null) return false;
        try {
            return locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER);
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public boolean isNetworkProviderEnabled() {
        if (locationManager == null) return false;
        try {
            return locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER);
        } catch (Exception e) {
            return false;
        }
    }

    public boolean isAnyProviderEnabled() {
        return isGpsEnabled() || isNetworkProviderEnabled();
    }

    @JavascriptInterface
    public void setAccuracyThreshold(float meters) {
        if (meters > 0) {
            this.accuracyThresholdMeters = meters;
        }
    }

    @JavascriptInterface
    public float getAccuracyThreshold() {
        return this.accuracyThresholdMeters;
    }

    @JavascriptInterface
    public void setTimeoutMs(long ms) {
        if (ms > 1000) {
            this.acquisitionTimeoutMs = ms;
        }
    }

    @JavascriptInterface
    public String getLocationState() {
        return this.currentState;
    }

    @JavascriptInterface
    public void requestPermissions() {
        if (context instanceof Activity) {
            Activity act = (Activity) context;
            ActivityCompat.requestPermissions(act, new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
            }, REQUEST_LOCATION_PERMISSION_CODE);
        }
    }

    /**
     * Initiates real location updates across GPS_PROVIDER and NETWORK_PROVIDER.
     */
    @JavascriptInterface
    public synchronized String requestLocationUpdates() {
        if (!hasLocationPermission()) {
            currentState = STATE_PERMISSION_REQUIRED;
            lastErrorMessage = "Location permission required. Please grant ACCESS_FINE_LOCATION.";
            notifyStateChanged();
            return buildResponseJson().toString();
        }

        if (locationManager == null || !isAnyProviderEnabled()) {
            currentState = STATE_GPS_UNAVAILABLE;
            lastErrorMessage = "Location providers disabled on device. Please enable GPS in device settings.";
            notifyStateChanged();
            return buildResponseJson().toString();
        }

        currentState = STATE_ACQUIRING;
        lastErrorMessage = null;
        notifyStateChanged();

        mainHandler.post(() -> {
            try {
                if (isListening) {
                    locationManager.removeUpdates(NativeLocationBridge.this);
                }

                // First check if a recent last-known location is available (under 60s)
                Location bestLastKnown = getBestLastKnownLocation();
                if (bestLastKnown != null) {
                    long ageMs = System.currentTimeMillis() - bestLastKnown.getTime();
                    if (ageMs < 60000) {
                        processLocation(bestLastKnown);
                    }
                }

                // Register listeners on both GPS and Network providers for fastest reliable fix
                boolean registered = false;
                if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                    locationManager.requestLocationUpdates(
                            LocationManager.GPS_PROVIDER,
                            1000L,   // 1 second interval
                            0.5f,    // 0.5 meter displacement
                            NativeLocationBridge.this,
                            Looper.getMainLooper()
                    );
                    registered = true;
                    Log.i(TAG, "Registered GPS_PROVIDER location listener");
                }

                if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                    locationManager.requestLocationUpdates(
                            LocationManager.NETWORK_PROVIDER,
                            1000L,
                            1.0f,
                            NativeLocationBridge.this,
                            Looper.getMainLooper()
                    );
                    registered = true;
                    Log.i(TAG, "Registered NETWORK_PROVIDER location listener");
                }

                if (registered) {
                    isListening = true;
                    mainHandler.removeCallbacks(timeoutRunnable);
                    mainHandler.postDelayed(timeoutRunnable, acquisitionTimeoutMs);
                } else {
                    currentState = STATE_GPS_UNAVAILABLE;
                    lastErrorMessage = "Could not register location listeners with device sensors.";
                    notifyStateChanged();
                }

            } catch (SecurityException se) {
                currentState = STATE_PERMISSION_REQUIRED;
                lastErrorMessage = "SecurityException requesting location: " + se.getMessage();
                notifyStateChanged();
                Log.e(TAG, "SecurityException registering location updates", se);
            } catch (Exception e) {
                currentState = STATE_LOCATION_UNAVAILABLE;
                lastErrorMessage = "Exception requesting location: " + e.getMessage();
                notifyStateChanged();
                Log.e(TAG, "Error registering location updates", e);
            }
        });

        return buildResponseJson().toString();
    }

    @JavascriptInterface
    public synchronized void stopLocationUpdates() {
        if (locationManager != null && isListening) {
            mainHandler.post(() -> {
                try {
                    locationManager.removeUpdates(NativeLocationBridge.this);
                } catch (Exception ignored) {}
                isListening = false;
                mainHandler.removeCallbacks(timeoutRunnable);
            });
        }
    }

    @Nullable
    public Location getBestLastKnownLocation() {
        if (locationManager == null || !hasLocationPermission()) return null;
        Location best = null;
        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                best = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                Location netLoc = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                if (best == null || (netLoc != null && netLoc.getTime() > best.getTime())) {
                    best = netLoc;
                }
            }
        } catch (SecurityException se) {
            Log.w(TAG, "Cannot get last known location: permission missing");
        } catch (Exception e) {
            Log.w(TAG, "Error querying last known location", e);
        }
        return best;
    }

    @JavascriptInterface
    public String getLastKnownLocationJson() {
        Location loc = getBestLastKnownLocation();
        if (loc != null) {
            return locationToJson(loc, evaluateLocationState(loc)).toString();
        }
        return "{\"state\":\"LOCATION_UNAVAILABLE\",\"error\":\"No cached location available\"}";
    }

    @JavascriptInterface
    public String getCurrentLocation() {
        return buildResponseJson().toString();
    }

    /**
     * Core location processor. Analyzes accuracy, observation timestamp,
     * provider name, and mock location status.
     */
    public synchronized void processLocation(@NonNull Location location) {
        this.lastLocation = location;
        this.currentState = evaluateLocationState(location);

        if (STATE_LOCATION_ACQUIRED.equals(currentState)) {
            lastErrorMessage = null;
            // Valid fix acquired; can cancel timeout
            mainHandler.removeCallbacks(timeoutRunnable);
        } else if (STATE_ACCURACY_INSUFFICIENT.equals(currentState)) {
            lastErrorMessage = String.format(Locale.US,
                    "Current accuracy (±%.1fm) is worse than threshold (±%.1fm). Move to open sky.",
                    location.getAccuracy(), accuracyThresholdMeters);
        }

        notifyStateChanged();
    }

    public String evaluateLocationState(@Nullable Location location) {
        if (location == null) {
            return STATE_LOCATION_UNAVAILABLE;
        }
        return evaluateAccuracy(location.getAccuracy(), accuracyThresholdMeters);
    }

    public static String evaluateAccuracy(float accuracyMeters, float thresholdMeters) {
        if (accuracyMeters <= 0.0f || accuracyMeters > thresholdMeters) {
            return STATE_ACCURACY_INSUFFICIENT;
        }
        return STATE_LOCATION_ACQUIRED;
    }

    public static boolean isMockLocation(@Nullable Location location) {
        if (location == null) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return location.isMock();
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR2) {
            return location.isFromMockProvider();
        }
        return false;
    }

    public static JSONObject formatLocationJson(double latitude, double longitude, float accuracy,
                                                long timestamp, String provider, boolean isMock,
                                                String state, @Nullable String error) {
        JSONObject obj = new JSONObject();
        try {
            obj.put("state", state);
            obj.put("latitude", latitude);
            obj.put("longitude", longitude);
            obj.put("accuracy", (double) accuracy);
            obj.put("timestamp", timestamp);
            obj.put("provider", provider != null ? provider : "unknown");
            obj.put("isMock", isMock);
            if (error != null) {
                obj.put("error", error);
            }
        } catch (JSONException ignored) {}
        return obj;
    }

    public JSONObject locationToJson(@NonNull Location loc, @NonNull String state) {
        JSONObject obj = formatLocationJson(
                loc.getLatitude(),
                loc.getLongitude(),
                loc.getAccuracy(),
                loc.getTime(),
                loc.getProvider(),
                isMockLocation(loc),
                state,
                lastErrorMessage
        );
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                obj.put("verticalAccuracyMeters", (double) loc.getVerticalAccuracyMeters());
            }
            if (loc.hasAltitude()) {
                obj.put("altitude", loc.getAltitude());
            }
            if (loc.hasBearing()) {
                obj.put("bearing", (double) loc.getBearing());
            }
            if (loc.hasSpeed()) {
                obj.put("speed", (double) loc.getSpeed());
            }
        } catch (Exception ignored) {}
        return obj;
    }

    public JSONObject buildResponseJson() {
        if (lastLocation != null && (STATE_LOCATION_ACQUIRED.equals(currentState) || STATE_ACCURACY_INSUFFICIENT.equals(currentState))) {
            return locationToJson(lastLocation, currentState);
        }

        JSONObject obj = new JSONObject();
        try {
            obj.put("state", currentState);
            if (lastErrorMessage != null) {
                obj.put("error", lastErrorMessage);
            } else if (STATE_ACQUIRING.equals(currentState)) {
                obj.put("message", "Acquiring GPS fix from satellite sensor...");
            }
        } catch (JSONException ignored) {}
        return obj;
    }

    private void notifyStateChanged() {
        if (webView == null) return;
        mainHandler.post(() -> {
            try {
                JSONObject payload = buildResponseJson();
                String js = String.format(Locale.US,
                        "if(window.app && window.app.onNativeLocationUpdate){window.app.onNativeLocationUpdate(%s);}",
                        payload.toString());
                webView.evaluateJavascript(js, null);
            } catch (Exception e) {
                Log.w(TAG, "Failed to dispatch location update to WebView", e);
            }
        });
    }

    // --- LocationListener Callbacks ---

    @Override
    public void onLocationChanged(@NonNull Location location) {
        Log.d(TAG, String.format(Locale.US,
                "Native location observation: provider=%s, lat=%.6f, lng=%.6f, acc=%.1fm, mock=%b",
                location.getProvider(), location.getLatitude(), location.getLongitude(),
                location.getAccuracy(), isMockLocation(location)));

        processLocation(location);
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) {
        if (status == LocationProvider.OUT_OF_SERVICE) {
            Log.w(TAG, "Location provider out of service: " + provider);
        } else if (status == LocationProvider.TEMPORARILY_UNAVAILABLE) {
            Log.w(TAG, "Location provider temporarily unavailable: " + provider);
        }
    }

    @Override
    public void onProviderEnabled(@NonNull String provider) {
        Log.i(TAG, "Location provider enabled: " + provider);
        if (STATE_GPS_UNAVAILABLE.equals(currentState)) {
            requestLocationUpdates();
        }
    }

    @Override
    public void onProviderDisabled(@NonNull String provider) {
        Log.w(TAG, "Location provider disabled: " + provider);
        if (!isAnyProviderEnabled()) {
            currentState = STATE_GPS_UNAVAILABLE;
            lastErrorMessage = "All location providers have been disabled on the device.";
            notifyStateChanged();
        }
    }
}
