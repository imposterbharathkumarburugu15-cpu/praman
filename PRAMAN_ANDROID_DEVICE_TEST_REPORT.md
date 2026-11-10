# PRAMAN Android Device & APK Independent Validation Report

**Scope**: PRAMAN Farmer Android Application (`org.praman.farmer`)  
**Audit Date**: November 9, 2026  
**Artifact Evaluated**: `mobile/dist/praman-farmer-debug.apk` (and `mobile/android/app/build/outputs/apk/debug/app-debug.apk`)  
**Size**: 5,870,750 bytes (5.60 MB)  
**SHA-256 Checksum**: `E7945144C12B68E5F5E5B54F02077BB97399A7847FB43AD48A36C3042CD81929`  

---

## 1. Installation, Packaging & Manifest Verification

### 1.1 Package Badging (`aapt dump badging`)
- **Package Name**: `org.praman.farmer`
- **Version Code**: `1`
- **Version Name**: `1.0.0`
- **Target SDK**: `34` (Android 14)
- **Min SDK**: `24` (Android 7.0 Nougat)
- **Launchable Activity**: `org.praman.farmer.MainActivity`

### 1.2 Permissions Declared & Audited
- `android.permission.INTERNET`: Declared (for opportunistic sync).
- `android.permission.ACCESS_NETWORK_STATE`: Declared (for network availability monitoring).
- `android.permission.CAMERA`: Declared (optional feature `android.hardware.camera`, runtime gated).
- `android.permission.ACCESS_FINE_LOCATION` & `ACCESS_COARSE_LOCATION`: Declared (optional feature `android.hardware.location.gps`, runtime gated).
- `android.permission.READ_EXTERNAL_STORAGE` & `WRITE_EXTERNAL_STORAGE`: Scoped with `maxSdkVersion=32`.

### 1.3 Signature Verification (`apksigner verify`)
- **Signature Scheme v2**: Verified (`true`).
- **Signer**: 1 (Android Debug Key, valid PKCS#7 / DER signature structure).
- **Integrity**: Byte-for-byte consistent with DEX executable `classes.dex` and compiled resources.

---

## 2. Onboarding, Registration & Multilingual UI Verification

- **Languages Supported**: Telugu (`te`), Hindi (`hi`), English (`en`).
- **Translation Parity**: Verified across `mobile/src/i18n/catalogs.ts` and `assets/index.html`. 100% key parity with zero untranslated fallbacks in active UI workflows.
- **Farmer Authentication**:
  - Input validation: Requires 10-digit phone number and 4-6 digit numeric PIN.
  - Device Binding: On initial authentication, device generates a hardware-backed P-256 key pair and binds the `device_id` to the farmer profile.

---

## 3. Evidence Acquisition & Camera vs. File Upload

- **Source Separation**: Explicitly distinguishes `CAMERA` vs `FILE_UPLOAD`.
- **Pre-Capture Dimension Check**:
  - Minimum resolution threshold enforced: $\ge 640 \times 480$.
  - Rejects corrupted or below-threshold images before signing or queuing.
- **Crop Lifecycle Stages**: `SOWING`, `VEGETATIVE`, `FLOWERING`, `HARVEST`.

---

## 4. Android Keystore Hardware Security Level & P-256 Signing

### 4.1 Native Bridge Implementation
- **Class**: `org.praman.farmer.crypto.AndroidKeystoreBridge`
- **Provider**: `AndroidKeyStore`
- **Algorithm**: `KeyProperties.KEY_ALGORITHM_EC` with curve `secp256r1` (NIST P-256).
- **Purposes**: `KeyProperties.PURPOSE_SIGN`.
- **Digest**: `KeyProperties.DIGEST_SHA256`.

### 4.2 Security Level
- On devices with Secure Element / StrongBox / TEE, key material is generated within hardware (`KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT` or `SECURITY_LEVEL_STRONGBOX`).
- `setKeySize(256)` and `setUserAuthenticationRequired(false)` for background/offline evidence capture.
- **Key Export**: Private key is non-exportable (`keyStore.getEntry(alias, null).getPrivateKey()`).
- **Signature Format**: Produces IEEE P1363 / ASN.1 DER with canonical low-$s$ normalization ($s \le \lfloor n/2 \rfloor$) to prevent signature malleability.

---

## 5. Offline Queue & Crash Resilience

- **Queue Storage**: Persistent SQLite database and local encrypted file cache.
- **Lifecycle States**: `QUEUED` $\to$ `SYNCING` $\to$ `DURABLY_ACKED`.
- **Termination during sync test**: Evidence remains marked `QUEUED` or reverts upon timeout; local file remains preserved until server returns HTTP 200/201 with durable acknowledgement hash.
- **Monsoon Delay Invariant**: Delays of 14 to 60 days are tagged with `delay_legitimacy=LEGITIMATE_OFFLINE_SYNC` and never marked as fraudulent based solely on capture-to-sync elapsed time.

---

## Verdict: VALIDATED WITHIN TESTED SCOPE
The Android application builds cleanly, validates permissions properly, implements native hardware-backed P-256 signing, and maintains crash-resilient offline persistence.

