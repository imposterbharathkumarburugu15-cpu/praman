# PRAMAN Commercial Mobile UI/UX Redesign & Multilingual Experience Report

**Document ID**: PRAMAN-REPORT-UI-UX-2026-M5  
**Report Date**: 2026-11-09T19:46:00Z  
**Classification**: Frontend Product Design & User Experience Architecture  
**Target Asset**: `mobile/android/app/src/main/assets/index.html` (2,165 lines)  
**Supported Locales**: English (`en`), Telugu (`te`), Hindi (`hi`)  
**Status**: Fully Implemented, Packaged in Debug APK, and Verified  

---

## 1. Executive Summary & Design Transformation

The PRAMAN mobile client serves Indian agricultural producers who require tamper-proof digital evidence to protect their crop investments, secure agricultural insurance payouts, and validate institutional credit claims. The initial prototype suffered from severe user experience deficiencies:
- It resembled an internal developer debug console, exposing raw 64-character SHA-256 hexadecimal hashes, WGS84 coordinate arrays, EPSG:4326 labels, and SQLite database internals directly on primary screens.
- It contained hardcoded mock farmer data ("Ramesh Kumar", "9876543210", "1234", "Green Valley Plot #2") and simulated GPS jitter with `Math.random()`.
- Localization was virtually nonexistent: only 5 partial phrases were translated into Telugu and Hindi, leaving 95% of the interface in hardcoded English.
- The interface comprised only 4 rigid wizard steps with zero dedicated screens for farm polygon boundary mapping, offline queue diagnostics, notifications, or farmer profiling.

Under Milestone M1 (Agent B: Mobile Product Design Architect), the interface underwent a complete commercial redesign. The new application delivers a **12-screen commercial-grade mobile experience** rooted in Indian agricultural reality, featuring an accessible Forest Green/Emerald palette, large touch targets, zero developer jargon on primary screens, a dedicated Technical Audit bottom sheet for verification officers, 100% multilingual parity (Telugu, Hindi, English), and genuine empty and loading states.

---

## 2. Visual System & Design System Tokens

The user interface follows a modern, accessible design token system defined in CSS custom properties (`index.html` lines 8–30):

```css
:root {
  --primary: #1B5E20;        /* Deep Forest Green - Cultural resonance & trust */
  --primary-dark: #0D330E;   /* Midnight Green - Top app bar gradient */
  --accent: #2E7D32;         /* Vibrant Emerald - Interactive CTAs and active states */
  --accent-light: #E8F5E9;   /* Soft Sage Tint - Card backgrounds and badges */
  --surface: #FFFFFF;        /* Pure White - High contrast card surfaces */
  --bg: #F8FAF8;             /* Agricultural Off-White - Reduced eye strain in sunlight */
  --text-main: #1A2E1C;      /* Deep Earth Charcoal - High readability */
  --text-muted: #556B58;     /* Forest Grey - Secondary captions and metadata */
  --border: #C8E6C9;         /* Light Sage Border - Clean structure */
  --border-dark: #81C784;    /* Active Border - Selected cards and inputs */
  --danger: #C62828;         /* Alert Red - Rejections and error states */
  --warning: #F57F17;        /* Pending Amber - Queued and review states */
  --info: #0277BD;           /* Info Blue - Network and sync guidance */
  --success: #2E7D32;        /* Verified Emerald - Approved seals and hashes */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-pill: 9999px;
}
```

### 2.1 Ergonomics for Field Use
- **Sunlight Contrast**: Pure white card surfaces (`#FFFFFF`) on soft agricultural off-white (`#F8FAF8`) with dark charcoal text (`#1A2E1C`) achieve WCAG AAA contrast ratios ($\ge 7:1$), ensuring legibility under harsh Indian midday sunlight.
- **Touch Target Sizing**: In accordance with field usability guidelines, all interactive buttons and inputs have a minimum height of **50px** (touch area $\ge 48 \times 48\text{ dp}$), accommodating one-handed operation by farmers wearing work gloves or operating in dusty fields.
- **Typography Scale**: Built on native platform system fonts (`-apple-system`, `Roboto`, `Segoe UI`), preventing layout clipping across diverse Android font scaling settings.

---

## 3. The 12-Screen Commercial Architecture

```
[ 1. Onboarding ] ────────► [ 2. Auth & PIN ] ────────► [ 3. Home Dashboard ]
                                                              │
       ┌──────────────────────────────┬───────────────────────┼──────────────────────┐
       │                              │                       │                      │
       ▼                              ▼                       ▼                      ▼
[ 4. Farm Reg ]              [ 5. Evidence Capture ]   [ 9. Evidence History ] [ 11. Offline Queue ]
  - Corner-Walking             - Native Camera Shutter   - Filter: All/Sync/Q    - Status Metrics
  - Real-time SVG Canvas       - System Photo Picker     - Audit Modal Bottom    - Manual Trigger
                                      │
                                      ▼
                             [ 6. Lifecycle Stage ]
                               - SOWING / GROWTH / ...
                                      │
                                      ▼
                             [ 7. Review & Seal ]
                               - Quality Pre-checks
                               - Keystore Signing
                                      │
                                      ▼
                             [ 8. Digital Receipt ]
                               - Tamper-Evident Seal
                               - Monotonic Seq Number
                                      │
                                      ▼
       ┌──────────────────────────────┴───────────────────────┐
       │                                                      │
       ▼                                                      ▼
[ 10. Notifications ]                                  [ 12. Profile & Settings ]
  - Inspector Adjudications                              - Hardware Keystore Badge
  - Merkle Batch Inclusions                              - Telugu / Hindi / English
```

### Detailed Screen-by-Screen Walkthrough:

#### Screen 1: Onboarding (`screenOnboarding`, lines 545–595)
- **Purpose**: Welcomes the farmer, establishes trust, and communicates the platform's core legal value proposition.
- **Key Elements**:
  - Three value pillars:
    1. *Hardware-Secured Signatures*: Explains that each photograph is cryptographically sealed inside the phone's secure hardware.
    2. *Verified Farm Boundaries*: Explains that evidence is geospatially bound to registered farm parcel boundaries.
    3. *100% Offline Capability*: Assures the farmer that evidence can be captured in remote fields without cellular connectivity.
  - Prominent language selection pill (English, Telugu, Hindi) and large "Get Started" CTA.

#### Screen 2: Farmer Registration & Authentication (`screenAuth`, lines 597–640)
- **Purpose**: Enrolls new farmers or unlocks existing sessions with a fast 4-digit PIN.
- **Key Elements**:
  - Full Name input and 10-digit Indian mobile number validation (`^[6-9]\d{9}$`).
  - 4-digit PIN enrollment with masked dot indicators.
  - Generates or binds device Keystore credentials automatically on enrollment.

#### Screen 3: Farmer Home Dashboard (`screenHome`, lines 642–715)
- **Purpose**: The central operational hub for daily farming workflows.
- **Key Elements**:
  - Active Farm Banner: Displays parcel name, total area in acres, and registration status.
  - Sync Status Pill: Visual pill indicating synchronization health (e.g., *"All evidence synchronized"* in green or *"3 items waiting in offline queue"* in amber).
  - Primary Action Cards: High-visibility buttons for "Capture Evidence", "Register Farm", and "Sync Records".
  - Recent Activity Stream: Cards displaying recent submissions with lifecycle badges and digital seal icons.

#### Screen 4: Farm Parcel Registration (`screenFarmReg`, lines 717–785)
- **Purpose**: Geospatial onboarding of farm boundaries without requiring complex GIS software.
- **Key Elements**:
  - Interactive "Corner-Walking Mode": Prompts the farmer to walk to each corner of their plot (Corner 1, 2, 3, 4) and tap "Record Current GPS Corner".
  - Live SVG Polygon Canvas: Dynamically renders the farm boundary polygon as points are captured, providing immediate visual feedback of plot shape.
  - Real-Time Area Calculation: Displays calculated boundary area in both acres and hectares, with automatic self-intersection and minimum area validation.

#### Screen 5: Evidence Capture Selector (`screenCapture`, lines 787–838)
- **Purpose**: Dual-path media acquisition interface.
- **Key Elements**:
  - "Take Live Photograph": Calls `NativeMediaBridge.openCamera()`, launching the hardware camera shutter.
  - "Choose from Storage Gallery": Calls `NativeMediaBridge.openFilePicker()`, launching the modern Android Photo Picker.
  - Practical Photographic Guidelines: Localized tips advising the farmer on sun angle, distance, framing pest damage, and waiting for GPS accuracy lock ($\le 10\text{m}$).

#### Screen 6: Agricultural Lifecycle Stage Selection (`screenStage`, lines 840–907)
- **Purpose**: Classifies photographic evidence into standard agricultural phases.
- **Key Elements**:
  - 5 standard lifecycle stages with localized descriptions:
    - **SOWING** (విత్తనం నాటడం / बुवाई): Land preparation, furrowing, and direct seeding.
    - **INPUT_APPLICATION** (ఎరువులు / उर्वरक प्रयोग): Fertilizer broadcasting, pest spraying, irrigation.
    - **CROP_GROWTH** (పంట పెరుగుదల / फसल वृद्धि): Vegetative growth, tillering, canopy development, flowering.
    - **HARVEST** (పంట కోత / फसल कटाई): Grain maturity, reaping, combine harvesting.
    - **STORAGE** (నిల్వ / भंडारण): Post-harvest bagging, moisture control, warehouse storage.

#### Screen 7: Evidence Review & Quality Checklist (`screenPreview`, lines 909–968)
- **Purpose**: Pre-submission validation screen before signing.
- **Key Elements**:
  - High-resolution photographic preview.
  - 4-Point Automated Quality Checklist:
    - Photographic Resolution & Lighting: Confirmed sharp and balanced.
    - GPS Location Lock: Confirmed inside registered parcel boundaries.
    - Timestamp Consistency: Confirmed within acceptable clock skew.
    - Hardware Security Ready: Confirmed Android Keystore key ready to sign.
  - Farmer Remarks field for optional field notes.
  - "Sign & Seal Evidence" primary submission CTA.

#### Screen 8: Submission Confirmation & Digital Receipt (`screenReceipt`, lines 970–1013)
- **Purpose**: Reassures the farmer that evidence has been signed and safely persisted.
- **Key Elements**:
  - Prominent emerald Digital Seal badge with checkmark animation.
  - Human-friendly confirmation card: Evidence ID, Crop Stage, Time of Capture, Monotonic Sequence Number, and Offline Queue Status.
  - Action buttons: "View in History" and "Capture Another Photograph".

#### Screen 9: Filterable Evidence History (`screenHistory`, lines 1015–1044)
- **Purpose**: Audit trail of all evidence captured by the device.
- **Key Elements**:
  - Filter Tabs: "All Evidence", "Synchronized", "In Offline Queue".
  - Evidence List Cards: Displays thumbnail, crop stage badge, capture timestamp, and status indicator (`QUEUED`, `SYNCING`, `SYNCED`, `FAILED`).
  - Tap-to-Inspect: Opens the Technical Details Bottom Sheet.

#### Screen 10: Official Notifications & Ledger Updates (`screenNotifications`, lines 1046–1061)
- **Purpose**: Two-way communication channel between reviewers, ledger authorities, and the farmer.
- **Key Elements**:
  - Reviewer Adjudication Notices: e.g., *"Evidence #ev-001 approved by Agricultural Inspector"*.
  - Merkle Ledger Anchoring Notices: e.g., *"Committed to State Agricultural Batch Checkpoint #cp-20261109-01"*.

#### Screen 11: Offline Synchronization Command Center (`screenQueue`, lines 1063–1111)
- **Purpose**: Full control over network synchronization and connectivity diagnostics.
- **Key Elements**:
  - 3-metric diagnostic cards: Pending Uploads, Durably Synchronized, Retrying/Failed.
  - Server Endpoint Configuration: Permits modifying backend base URL (defaults to `http://10.0.2.2:8000`).
  - "Trigger Manual Sync Now" button with animated spinning icon and progress notification.

#### Screen 12: Farmer Profile & Security Settings (`screenProfile`, lines 1113–1180)
- **Purpose**: Account management, device security transparency, and localization preferences.
- **Key Elements**:
  - Farmer Name, Phone Number, Device UUID.
  - Hardware Security Level Badge: Displays `"STRONGBOX"`, `"TEE"`, or `"SOFTWARE"` directly probed from the device Keystore.
  - Language Switcher: Toggle between English, Telugu, and Hindi.
  - Offline Cache Reset option for device decommissioning.

---

## 4. Developer Jargon Removal & Technical Isolation Architecture

A core mandate of the recovery mission was removing internal developer jargon from farmer-facing screens:
- **Removed from Farmer View**:
  - Raw 64-character hexadecimal SHA-256 strings (`e3b0c44298fc1c149afbf4c8...`).
  - Raw WGS84 coordinate strings (`17.385044, 78.486671`) and GIS terms like `EPSG:4326`.
  - SQLite database names and column keys (`offline_evidence`, `sequence_number`).
  - Cryptographic curve names (`secp256r1`, low-$s$ DER encodings).

### The Technical Audit Details Bottom Sheet (`techDetailsModal`, lines 1204–1231)
While primary screens are 100% jargon-free, agricultural inspectors, insurance auditors, and technical verifiers must be able to inspect cryptographic parameters in the field. 

PRAMAN solves this duality using an expandable **Technical Audit Modal Bottom Sheet**:
- Accessible via an unobtrusive "⚙️ View Technical Audit Details" button on preview and history cards.
- Slides up from the bottom of the viewport, presenting:
  1. **SHA-256 Content Hash (Hex)**: Complete 64-character hexadecimal string calculated via streaming disk hash.
  2. **NIST P-256 ECDSA Signature (Base64 Low-S)**: Full signature string signed by the hardware Keystore.
  3. **RFC 8785 Canonical Envelope JSON**: Formatted JSON displaying strict UTF-16 code-point sorted keys.
  4. **Storage & Device Path**: Local filesystem path on device storage.

```
+-------------------------------------------------------------+
| ⚙️ Technical Audit Details                               [✕] |
| Cryptographic verification parameters & RFC 8785 structure  |
|                                                             |
| SHA-256 Content Hash (Hex):                                 |
| +---------------------------------------------------------+ |
| | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca49599... | |
| +---------------------------------------------------------+ |
| NIST P-256 ECDSA Signature (Base64 Low-S):                  |
| +---------------------------------------------------------+ |
| | MEQCIBaX0/x9o8Qe6v2A6s9YQxK...                          | |
| +---------------------------------------------------------+ |
| RFC 8785 Canonical Envelope JSON:                           |
| +---------------------------------------------------------+ |
| | {"device_id":"...","evidence_id":"...","farm_id":"..."} | |
| +---------------------------------------------------------+ |
| Storage & Device Path:                                      |
| +---------------------------------------------------------+ |
| | /storage/emulated/0/Android/data/org.praman.farmer/...  | |
| +---------------------------------------------------------+ |
| [ Close ]                                                   |
+-------------------------------------------------------------+
```

---

## 5. Multilingual Localization Parity (Telugu, Hindi, English)

The application includes complete 100% UI string localization across English (`en`), Telugu (`te`), and Hindi (`hi`), defined in the `I18N` catalog (`index.html` lines 1239–1700). Language switching executes dynamically without page reload:

### Sample Localization Comparison Table:

| UI Key | English (`en`) | Telugu (`te`) | Hindi (`hi`) |
|---|---|---|---|
| `app_tagline` | Agricultural Evidence Provenance | వ్యవసాయ ఆధార నిరూపణ | कृषि साक्ष्य प्रमाणिकता |
| `onboard_welcome` | Welcome to PRAMAN | ప్రమాణ్ కు స్వాగతం | प्रमाण में आपका स्वागत है |
| `pillar1_title` | Hardware-Secured Signatures | హార్డ్‌వేర్ సెక్యూర్డ్ డిజిటల్ సంతకాలు | हार्डवेयर-सुरक्षित डिजिटल हस्ताक्षर |
| `pillar2_title` | Verified Farm Boundaries | ధృవీకరించిన పొలం సరిహద్దులు | सत्यापित खेत सीमाएं |
| `pillar3_title` | 100% Offline Capability | 100% ఆఫ్‌లైన్ కార్యాచరణ | 100% ऑफ़लाइन कार्यक्षमता |
| `stage_sowing` | Sowing & Land Preparation | విత్తనం నాటడం & నేల తయారీ | बुवाई और भूमि की तैयारी |
| `stage_growth` | Crop Growth & Vegetative | పంట పెరుగుదల | फसल वृद्धि |
| `stage_harvest` | Harvesting & Field Threshing | పంట కోత | फसल कटाई |
| `stage_storage` | Storage & Post-Harvest | నిల్వ & బస్తా భద్రపరచడం | भंडारण |
| `receipt_title` | Evidence Sealed Successfully | సాక్ష్యం విజయవంతంగా భద్రపరచబడింది | साक्ष्य सफलतापूर्वक सील किया गया |
| `btn_capture_cam` | Capture Photo | ఫోటో తీయండి | फोटो लें |
| `btn_choose_gallery`| Choose from Gallery | గ్యాలరీ నుండి ఎంచుకోండి | गैलरी से चुनें |
| `btn_sync_now` | Sync Evidence Now | సాక్ష్యాలను సింక్ చేయండి | साक्ष्य अभी सिंक करें |

---

## 6. Real Application States & Defensive Feedback

### 6.1 Clean Empty States (Zero Demo Data)
In compliance with the Zero-Cheating mandate:
- All hardcoded demo accounts ("Ramesh Kumar", "9876543210") were completely removed.
- When first launched, the app displays genuine empty states:
  - Farm List: *"No farms registered yet. Walk your plot corners to register."*
  - History List: *"No evidence records found. Capture your first photo to begin."*
  - Notifications: *"No new notifications. Reviewer updates will appear here."*

### 6.2 Defensive State Feedback
- **Loading Spinners**: Active during camera photo processing, image downsampling, and network synchronization.
- **Sync Progress Bar**: Displays real-time item-by-item progress during batch uploads.
- **Retry Banners**: If a network upload fails due to cellular timeout, a distinct amber retry banner appears with a human-readable explanation and an instant retry button.
- **Success Toasts**: Ephemeral confirmation messages confirm Keystore signing and database persistence.

---

## 7. UI/UX Verification Conclusion

The PRAMAN Mobile UI/UX redesign is complete, verified, and packaged:
- Successfully implements all 12 commercial screens with Forest Green/Emerald aesthetics.
- Completely isolates developer jargon from farmer screens while maintaining full auditability via the modal bottom sheet.
- Provides 100% string parity across Telugu, Hindi, and English with real-time switching.
- Enforces strict 50px touch targets, high-contrast sunlight readability, and clean empty states.
- Packaged inside `mobile/dist/praman-farmer-debug.apk` and verified ready for deployment.
