# PRAMAN Database Design & Schema Specification

## 1. Overview & Storage Engine

PRAMAN uses **PostgreSQL 17** running on localhost port 1234 (`postgresql://postgres:postgres@localhost:1234/praman`), managed through **SQLAlchemy 2.0** and **Alembic** migrations. The schema is engineered with strict foreign key constraints, UUID primary keys, check constraints, composite unique constraints for replay prevention, and database-level triggers enforcing an immutable append-only audit trail.

---

## 2. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    FARMER ||--o{ DEVICE : "registers (1:N)"
    FARMER ||--o{ FARM : "owns (1:N)"
    FARM ||--o{ EVIDENCE : "records (1:N)"
    DEVICE ||--o{ EVIDENCE : "signs (1:N)"

    FARMER {
        string id PK "UUIDv4"
        string full_name "Full name of farmer"
        string phone_number UK "E.164 phone number"
        string language_pref "te | hi | en"
        timestamp created_at "Server timestamp"
    }

    DEVICE {
        string id PK "UUIDv4"
        string farmer_id FK "References farmers.id (CASCADE)"
        text public_key_pem "NIST P-256 ECDSA public key"
        string status "ACTIVE | REVOKED | SUSPENDED"
        integer last_sequence_number "Monotonic sequence counter"
        timestamp created_at "Server timestamp"
    }

    FARM {
        string id PK "UUIDv4"
        string farmer_id FK "References farmers.id (CASCADE)"
        string farm_name "Parcel identifier / name"
        string crop_type "Cotton, Rice, Maize, etc."
        text boundary_geojson "Validated WGS84 GeoJSON polygon"
        float area_hectares "Calculated parcel area"
        timestamp created_at "Server timestamp"
    }

    EVIDENCE {
        string id PK "UUIDv4"
        string farm_id FK "References farms.id"
        string device_id FK "References devices.id"
        integer sequence_number "Monotonic sequence per device"
        string lifecycle_stage "SOWING | INPUT_APPLICATION | CROP_GROWTH | HARVEST | STORAGE"
        string image_hash "SHA-256 of original image file"
        text canonical_envelope_json "RFC 8785 canonical JSON payload"
        text signature_b64 "Base64 ASN.1 DER P-256 signature"
        string status "DURABLY_ACKED | PENDING_AI | PENDING_REVIEW | APPROVED | REJECTED"
        timestamp created_at "Server timestamp"
    }

    AUDIT_LOG {
        string log_id PK "UUIDv4"
        string event_type "INGESTION | SEQUENCE_LOCK | REVIEW_DECISION | DEVICE_REVOCATION"
        string entity_type "evidence | device | farm | farmer"
        string entity_id "Target entity UUID"
        string actor_id "User / Device / System actor"
        string previous_state "Serialized previous state or NULL"
        string new_state "Serialized current state"
        string payload_hash "SHA-256 hash of event payload"
        string prev_log_hash "Hash chain linking prior audit entry"
        timestamp created_at "Server timestamp"
    }
```

---

## 3. Detailed Table Definitions

### 3.1 `farmers` Table
Stores farmer identity, multilingual preferences, and contact details.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | UUIDv4 identifier. |
| `full_name` | `VARCHAR(255)` | `NOT NULL` | Full legal or display name of the farmer. |
| `phone_number` | `VARCHAR(32)` | `NOT NULL, UNIQUE` | Unique phone number used for login and notifications. |
| `language_pref` | `VARCHAR(10)` | `NOT NULL, CHECK (language_pref IN ('te', 'hi', 'en'))` | UI language preference (Telugu, Hindi, or English). Defaults to `'te'`. |
| `created_at` | `TIMESTAMP` | `NOT NULL, DEFAULT CURRENT_TIMESTAMP` | Record creation timestamp. |

- **Indexes**:
  - `ix_farmers_phone_number` (`phone_number`, UNIQUE).

### 3.2 `devices` Table
Maintains device hardware enrollment, NIST P-256 public keys, lifecycle status, and the latest monotonic sequence number.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | UUIDv4 device identifier (generated on mobile or server). |
| `farmer_id` | `VARCHAR(36)` | `NOT NULL, FOREIGN KEY -> farmers.id ON DELETE CASCADE` | Enrolled farmer owner. |
| `public_key_pem` | `TEXT` | `NOT NULL` | PEM-encoded P-256 public key generated in hardware Keystore. |
| `status` | `VARCHAR(20)` | `NOT NULL, CHECK (status IN ('ACTIVE', 'REVOKED', 'SUSPENDED'))` | Device trust status. Default `'ACTIVE'`. |
| `last_sequence_number` | `INTEGER` | `NOT NULL, DEFAULT 0` | Current sequence counter; guarantees strictly monotonic upload increments. |
| `created_at` | `TIMESTAMP` | `NOT NULL, DEFAULT CURRENT_TIMESTAMP` | Enrollment timestamp. |

- **Indexes**:
  - `ix_devices_farmer_id` (`farmer_id`).

### 3.3 `farms` Table
Represents registered land parcels with boundary polygons validated under WGS84 standards.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | UUIDv4 farm parcel identifier. |
| `farmer_id` | `VARCHAR(36)` | `NOT NULL, FOREIGN KEY -> farmers.id ON DELETE CASCADE` | Owning farmer. |
| `farm_name` | `VARCHAR(255)` | `NOT NULL` | Name or identifier of the agricultural plot. |
| `crop_type` | `VARCHAR(100)` | `NOT NULL` | Primary crop cultivated (e.g., Cotton, Rice, Maize, Turmeric). |
| `boundary_geojson` | `TEXT` | `NOT NULL` | Strict GeoJSON Polygon string verifying closure and non-self-intersection. |
| `area_hectares` | `FLOAT` | `NOT NULL` | Calculated surface area in hectares. |
| `created_at` | `TIMESTAMP` | `NOT NULL, DEFAULT CURRENT_TIMESTAMP` | Registration timestamp. |

- **Indexes**:
  - `ix_farms_farmer_id` (`farmer_id`).

### 3.4 `evidence` Table
The primary ledger for field capture envelopes, cryptographic signatures, and provenance statuses.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | UUIDv4 matching `envelope.evidence_id`. |
| `farm_id` | `VARCHAR(36)` | `NOT NULL, FOREIGN KEY -> farms.id` | Target farm where photo was captured. |
| `device_id` | `VARCHAR(36)` | `NOT NULL, FOREIGN KEY -> devices.id` | Device that signed the evidence envelope. |
| `sequence_number` | `INTEGER` | `NOT NULL` | Device monotonic sequence number. |
| `lifecycle_stage` | `VARCHAR(50)` | `NOT NULL` | `SOWING`, `INPUT_APPLICATION`, `CROP_GROWTH`, `HARVEST`, `STORAGE`. |
| `image_hash` | `VARCHAR(64)` | `NOT NULL` | SHA-256 hexadecimal digest of the stored image. |
| `canonical_envelope_json`| `TEXT` | `NOT NULL` | RFC 8785 canonical JSON string. |
| `signature_b64` | `TEXT` | `NOT NULL` | Base64-encoded ASN.1 DER ECDSA P-256 signature. |
| `status` | `VARCHAR(30)` | `NOT NULL, DEFAULT 'DURABLY_ACKED'` | Lifecycle status (`DURABLY_ACKED`, `PENDING_REVIEW`, `APPROVED`, etc.). |
| `created_at` | `TIMESTAMP` | `NOT NULL, DEFAULT CURRENT_TIMESTAMP` | Server ingestion timestamp. |

- **Indexes & Unique Constraints**:
  - `uq_device_sequence` (`device_id`, `sequence_number`, UNIQUE): Prevents sequence replay at the database level.
  - `ix_evidence_farm_id` (`farm_id`).
  - `ix_evidence_device_id` (`device_id`).
  - `ix_evidence_image_hash` (`image_hash`): Enables instant $O(1)$ duplicate lookup.

### 3.5 `audit_log` Table
Tamper-evident, hash-chained, append-only record of all security-critical system events.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `log_id` | `VARCHAR(36)` | `PRIMARY KEY` | UUIDv4 log event ID. |
| `event_type` | `VARCHAR(100)` | `NOT NULL` | Category: `INGESTION`, `SEQUENCE_LOCK`, `REVIEW`, `REVOCATION`. |
| `entity_type` | `VARCHAR(50)` | `NOT NULL` | `evidence`, `device`, `farm`, `farmer`. |
| `entity_id` | `VARCHAR(36)` | `NOT NULL` | Primary key of the affected entity. |
| `actor_id` | `VARCHAR(100)` | `NOT NULL` | Identity of actor (device UUID, reviewer username, system worker). |
| `previous_state` | `TEXT` | `NULLABLE` | JSON snapshot of prior state. |
| `new_state` | `TEXT` | `NOT NULL` | JSON snapshot of new state. |
| `payload_hash` | `VARCHAR(64)` | `NOT NULL` | SHA-256 hash of event details. |
| `prev_log_hash` | `VARCHAR(64)` | `NULLABLE` | Hash of prior log entry creating an immutable audit chain. |
| `created_at` | `TIMESTAMP` | `NOT NULL, DEFAULT CURRENT_TIMESTAMP` | Server timestamp. |

---

## 4. Immutability Enforcers & Database Triggers

To guarantee that the audit trail cannot be manipulated even by privileged application users, PostgreSQL triggers prohibit all `UPDATE` and `DELETE` operations on `audit_log`:

```sql
CREATE OR REPLACE FUNCTION audit_log_prohibit_update()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Audit log records are immutable and cannot be updated';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION audit_log_prohibit_delete()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Audit log records are append-only and cannot be deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prohibit_audit_update
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_prohibit_update();

CREATE TRIGGER prohibit_audit_delete
BEFORE DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_prohibit_delete();
```

---

## 5. Migration Strategy

Alembic maintains version-controlled migration scripts located in `backend/alembic/versions/`. Migrations can be applied or verified using:
```bash
# Upgrade database to latest revision
alembic upgrade head

# Downgrade revision if rolled back
alembic downgrade base
```
Automatic database initialization script `backend/init_db.py` creates the database instance on PostgreSQL port 1234 if it does not already exist.

