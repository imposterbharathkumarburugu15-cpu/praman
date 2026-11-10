# PRAMAN GPS Implementation & Real Location Acquisition Report

**Component**: Android Location Services & GPS Acquisition Bridge  
**Module**: `org.praman.farmer.location.NativeLocationBridge`  
**Integration**: `MainActivity.java` & `mobile/android/app/src/main/assets/index.html`  
**Date**: 2026-11-10  
**Specification Reference**: ORIGINAL_REQUEST.md §2 (REAL GPS AND LOCATION ACQUISITION)  
**Status**: Implemented, Tested, Passed  

---

## 1. Executive Summary

Prior to this implementation, the PRAMAN Android application contained critical simulation defects in its location subsystem (cataloged as DEF-MOB-01 and DEF-MOB-12):
1. The web interface hardcoded coordinates to Hyderabad (`17.385044, 78.486671`) with a static accuracy of `5.0m`.
2. Geolocation errors were inverted: when the sensor or permissions failed, the callback displayed `"GPS signal acquired from device sensor (High Accuracy)"` while retaining the hardcoded coordinates.
3. No native Android location services existed in the Java source; `LocationManager` and `LocationListener` were completely absent.
4. `WebChromeClient` omitted `onGeolocationPermissionsShowPrompt`, causing WebViews to reject HTML5 location prompts by default.

Worker M4 has completely replaced this simulation with a genuine hardware location pipeline:
- Created `NativeLocationBridge.java` utilizing Android `LocationManager` (`GPS_PROVIDER` with fallback to `NETWORK_PROVIDER`).
- Enforced strict runtime location permissions (`ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`).
- Captured genuine coordinate attributes: latitude, longitude, horizontal accuracy in metres, observation timestamp (UTC epoch ms), provider name, and mock location status.
- Implemented state transitions: `ACQUIRING`, `LOCATION_ACQUIRED`, `ACCURACY_INSUFFICIENT`, `PERMISSION_REQUIRED`, `GPS_UNAVAILABLE`, `LOCATION_UNAVAILABLE`.
- Overrode `WebChromeClient.onGeolocationPermissionsShowPrompt` in `MainActivity.java` and registered `NativeLocationBridge` via `@JavascriptInterface`.
- Removed all hardcoded coordinates and fake success messages from `assets/index.html`.

---

## 2. Implementation Inventory

| Item # | Capability | Source Location | Implementation Status | Test Status |
|---|---|---|---|---|
| 1 | Native Location Bridge | `mobile/android/app/src/main/java/org/praman/farmer/location/NativeLocationBridge.java` | **Implemented** | **Passed** |
| 2 | Runtime Permission Checks | `NativeLocationBridge.java:hasLocationPermission()` | **Implemented** | **Passed** |
| 3 | GPS & Network Provider Listeners | `NativeLocationBridge.java:requestLocationUpdates()` | **Implemented** | **Passed** |
| 4 | State Machine Enforcement | `NativeLocationBridge.java:evaluateLocationState()` | **Implemented** | **Passed** |
| 5 | Horizontal Accuracy Gating | `NativeLocationBridge.java:evaluateAccuracy()` | **Implemented** | **Passed** |
| 6 | Android Mock Location Detection | `NativeLocationBridge.java:isMockLocation()` | **Implemented** | **Passed** |
| 7 | WebChromeClient Prompt Handling | `mobile/android/app/src/main/java/org/praman/farmer/MainActivity.java:85` | **Implemented** | **Passed** |
| 8 | WebView Interface Binding | `MainActivity.java:135` (`NativeLocationBridge`) | **Implemented** | **Passed** |
| 9 | UI Hardcoded Coordinates Removal | `assets/index.html:1517` (`currentGps = null`) | **Implemented** | **Passed** |
| 10 | Error Inversion Callback Fix | `assets/index.html:1845–1890` (`acquireGpsPosition`) | **Implemented** | **Passed** |
| 11 | Boundary Jitter Removal | `assets/index.html:2005` (`markCurrentCorner`) | **Implemented** | **Passed** |
| 12 | Unit Test Suite | `mobile/android/app/src/test/java/org/praman/farmer/NativeLocationBridgeTest.java` | **Implemented** | **Passed** |

---

## 3. Location State Machine

The bridge strictly enforces the following six operational states per ORIGINAL_REQUEST §2:

1. **`ACQUIRING`**:
   - Actively listening to `LocationManager.GPS_PROVIDER` (1s interval, 0.5m displacement) and `LocationManager.NETWORK_PROVIDER` (1s interval, 1.0m displacement).
   - UI status: *"Acquiring GPS fix from satellite sensor..."* (amber indicator).
2. **`LOCATION_ACQUIRED`**:
   - A genuine observation arrived with horizontal accuracy <= `accuracyThresholdMeters` (default: 25.0 metres).
   - UI status: *"${latitude.toFixed(6)}, ${longitude.toFixed(6)} (±${accuracy.toFixed(1)}m, GPS)"*.
3. **`ACCURACY_INSUFFICIENT`**:
   - Fix was received, but accuracy exceeds threshold (e.g. ±45.0m indoors). Coordinates are preserved but flagged.
   - UI status: *"Accuracy Insufficient: ±45.0m (Threshold: 25m). Move to open sky."*
4. **`PERMISSION_REQUIRED`**:
   - `ACCESS_FINE_LOCATION` or `ACCESS_COARSE_LOCATION` was denied by the user.
   - UI status: *"Location permission required. Tap to grant access."*
5. **`GPS_UNAVAILABLE`**:
   - Both GPS and Network providers are disabled in Android Settings.
   - UI status: *"GPS disabled on device. Please enable in Settings."*
6. **`LOCATION_UNAVAILABLE`**:
   - Acquisition timed out (default: 15,000ms) without any satellite or network fix.
   - UI status: *"Location fix unavailable. Move to open sky."*

---

## 4. Verification & Unit Test Results

The implementation was independently tested using Gradle debug unit tests on Android:

```powershell
cd mobile/android
.\gradlew.bat testDebugUnitTest --tests "org.praman.farmer.NativeLocationBridgeTest"
```

**Results**:
- `testLocationStateConstants`: **PASSED** (Validated state constant mappings).
- `testEvaluateLocationAccuracyThresholds`: **PASSED** (Validated 8.5m pass, 25.0m boundary, 25.1m rejection, 45.0m rejection, 0.0m invalid rejection, and custom threshold adjustments).
- `testLocationJsonFormatting`: **PASSED** (Validated JSON serialization of lat, lon, acc, UTC timestamp, provider, isMock).
- `testLocationJsonWithError`: **PASSED** (Validated JSON serialization of insufficient accuracy error payloads).
- `testMockLocationDetectionLogic`: **PASSED** (Validated null-safe mock detection).

---

## 5. Security & Anti-Spoofing Considerations

1. **Mock Location Transparency**: The bridge queries `location.isMock()` (API 31+) and `location.isFromMockProvider()` (API 18–30), tagging the observation in the envelope metadata with `"isMock": true|false`.
2. **Hardware Geodesic Area Integrity**: Coordinate observations are signed directly by the Android Hardware Keystore NIST P-256 private key inside the evidence envelope, binding the sensor timestamp and GPS coordinates cryptographically.
3. **No Ownership Claim**: Location observations represent the device position at the capture instant; they do not establish legal land ownership without cadastral backend validation.
