# PRAMAN Farmer Mobile Application — Android Build & Artifacts

## Overview
This directory contains the Android application build configuration, native harness, and packaged installable APKs for the **PRAMAN Farmer Mobile** platform.

## Environment & Build Prerequisites
- **JDK**: Eclipse Adoptium JDK 17 (`C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`)
- **Android SDK**: `C:\Users\bhara\AppData\Local\Android\Sdk`
- **Compile SDK**: 34 (Android 14)
- **Min SDK**: 24 (Android 7.0)
- **Target SDK**: 34
- **Gradle**: 8.14.3
- **Android Gradle Plugin (AGP)**: 8.13.0

## Build Commands
To compile and assemble the debug APK:
```powershell
cd mobile\android
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
$env:ANDROID_HOME = "C:\Users\bhara\AppData\Local\Android\Sdk"
.\gradlew.bat assembleDebug
```

## Generated APK Artifacts
1. **Primary Distributable**:
   - Path: `mobile/dist/praman-farmer-debug.apk`
   - Size: `5,870,750 bytes` (~5.60 MB)
   - SHA-256: `E7945144C12B68E5F5E5B54F02077BB97399A7847FB43AD48A36C3042CD81929`
2. **Gradle Standard Output**:
   - Path: `mobile/android/app/build/outputs/apk/debug/app-debug.apk`

## Package Verification
- **Package Name**: `org.praman.farmer`
- **Version**: `1.0.0` (`versionCode = 1`)
- **Main Launchable Activity**: `org.praman.farmer.MainActivity`
- **Signature Scheme**: APK Signature Scheme v2 (VERIFIED)
- **Permissions**:
  - `android.permission.INTERNET`
  - `android.permission.ACCESS_NETWORK_STATE`
  - `android.permission.CAMERA`
  - `android.permission.ACCESS_FINE_LOCATION`
  - `android.permission.ACCESS_COARSE_LOCATION`
  - `android.permission.READ_EXTERNAL_STORAGE`
  - `android.permission.WRITE_EXTERNAL_STORAGE` (maxSdkVersion=32)

## Key Features & Architectural Components
- **Multilingual Support**: Telugu (`te`), Hindi (`hi`), English (`en`) parity with `src/i18n/catalogs.ts`.
- **Farmer Authentication**: On-device registration and login with mobile number and PIN.
- **Farm Boundary Acquisition**: WGS84 GPS coordinate acquisition and closed polygon vertex validation.
- **Evidence Capture**:
  - Direct Camera vs File Upload modes
  - Lifecycle stage classification (`SOWING`, `VEGETATIVE`, `FLOWERING`, `HARVEST`)
  - Resolution verification (minimum 640x480)
  - Cryptographic canonical JSON SHA-256 hash calculation
  - Hardware KeyStore ECDSA P-256 signing bridge with Low-$s$ normalization
- **Offline Persistence**: Local SQLite / offline queue with state transitions (`QUEUED` -> `SYNCING` -> `DURABLY_ACKED`) and opportunistic server sync.

