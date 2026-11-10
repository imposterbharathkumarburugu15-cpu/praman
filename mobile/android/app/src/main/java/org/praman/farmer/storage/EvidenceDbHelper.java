package org.praman.farmer.storage;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

/**
 * SQLite Database Helper for persistent, crash-resilient offline evidence storage.
 * Survives application kill, task manager termination, and device reboot.
 */
public class EvidenceDbHelper extends SQLiteOpenHelper {

    private static final String DATABASE_NAME = "praman_evidence.db";
    private static final int DATABASE_VERSION = 1;

    public static final String TABLE_EVIDENCE = "offline_evidence";
    public static final String COL_EVIDENCE_ID = "evidence_id";
    public static final String COL_DEVICE_ID = "device_id";
    public static final String COL_FARM_ID = "farm_id";
    public static final String COL_SEQUENCE_NUMBER = "sequence_number";
    public static final String COL_LIFECYCLE_STAGE = "lifecycle_stage";
    public static final String COL_CAPTURE_SOURCE = "capture_source";
    public static final String COL_RAW_FILE_PATH = "raw_file_path";
    public static final String COL_IMAGE_HASH = "image_hash";
    public static final String COL_ENVELOPE_JSON = "envelope_json";
    public static final String COL_SIGNATURE_B64 = "signature_b64";
    public static final String COL_STATUS = "status";
    public static final String COL_RETRY_COUNT = "retry_count";
    public static final String COL_SERVER_RECEIPT = "server_receipt";
    public static final String COL_ERROR_MESSAGE = "error_message";
    public static final String COL_CREATED_AT = "created_at";
    public static final String COL_UPDATED_AT = "updated_at";

    private static EvidenceDbHelper instance;

    public static synchronized EvidenceDbHelper getInstance(Context context) {
        if (instance == null) {
            instance = new EvidenceDbHelper(context.getApplicationContext());
        }
        return instance;
    }

    public EvidenceDbHelper(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        String createTable = "CREATE TABLE " + TABLE_EVIDENCE + " ("
                + COL_EVIDENCE_ID + " TEXT PRIMARY KEY, "
                + COL_DEVICE_ID + " TEXT, "
                + COL_FARM_ID + " TEXT, "
                + COL_SEQUENCE_NUMBER + " INTEGER, "
                + COL_LIFECYCLE_STAGE + " TEXT, "
                + COL_CAPTURE_SOURCE + " TEXT, "
                + COL_RAW_FILE_PATH + " TEXT, "
                + COL_IMAGE_HASH + " TEXT, "
                + COL_ENVELOPE_JSON + " TEXT, "
                + COL_SIGNATURE_B64 + " TEXT, "
                + COL_STATUS + " TEXT, "
                + COL_RETRY_COUNT + " INTEGER DEFAULT 0, "
                + COL_SERVER_RECEIPT + " TEXT, "
                + COL_ERROR_MESSAGE + " TEXT, "
                + COL_CREATED_AT + " TEXT, "
                + COL_UPDATED_AT + " TEXT"
                + ");";
        db.execSQL(createTable);
        db.execSQL("CREATE INDEX idx_sequence ON " + TABLE_EVIDENCE + " (" + COL_SEQUENCE_NUMBER + ");");
        db.execSQL("CREATE INDEX idx_status ON " + TABLE_EVIDENCE + " (" + COL_STATUS + ");");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        db.execSQL("DROP TABLE IF EXISTS " + TABLE_EVIDENCE);
        onCreate(db);
    }

    public synchronized long insertOrUpdate(EvidenceRecord record) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_EVIDENCE_ID, record.getEvidenceId());
        values.put(COL_DEVICE_ID, record.getDeviceId());
        values.put(COL_FARM_ID, record.getFarmId());
        values.put(COL_SEQUENCE_NUMBER, record.getSequenceNumber());
        values.put(COL_LIFECYCLE_STAGE, record.getLifecycleStage());
        values.put(COL_CAPTURE_SOURCE, record.getCaptureSource());
        values.put(COL_RAW_FILE_PATH, record.getRawFilePath());
        values.put(COL_IMAGE_HASH, record.getImageHash());
        values.put(COL_ENVELOPE_JSON, record.getEnvelopeJson());
        values.put(COL_SIGNATURE_B64, record.getSignatureB64());
        values.put(COL_STATUS, record.getStatus());
        values.put(COL_RETRY_COUNT, record.getRetryCount());
        values.put(COL_SERVER_RECEIPT, record.getServerReceipt());
        values.put(COL_ERROR_MESSAGE, record.getErrorMessage());
        values.put(COL_CREATED_AT, record.getCreatedAt());
        values.put(COL_UPDATED_AT, record.getUpdatedAt());

        return db.insertWithOnConflict(TABLE_EVIDENCE, null, values, SQLiteDatabase.CONFLICT_REPLACE);
    }

    public synchronized void updateStatus(String evidenceId, String status, String receipt, String errorMsg, int retryCount) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_STATUS, status);
        if (receipt != null) values.put(COL_SERVER_RECEIPT, receipt);
        if (errorMsg != null) values.put(COL_ERROR_MESSAGE, errorMsg);
        values.put(COL_RETRY_COUNT, retryCount);
        values.put(COL_UPDATED_AT, String.valueOf(System.currentTimeMillis()));

        db.update(TABLE_EVIDENCE, values, COL_EVIDENCE_ID + " = ?", new String[]{evidenceId});
    }

    public synchronized List<EvidenceRecord> getAllEvidence() {
        List<EvidenceRecord> list = new ArrayList<>();
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.query(TABLE_EVIDENCE, null, null, null, null, null, COL_SEQUENCE_NUMBER + " DESC");
        try {
            if (cursor.moveToFirst()) {
                do {
                    list.add(cursorToRecord(cursor));
                } while (cursor.moveToNext());
            }
        } finally {
            cursor.close();
        }
        return list;
    }

    public synchronized List<EvidenceRecord> getPendingQueue() {
        List<EvidenceRecord> list = new ArrayList<>();
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.query(TABLE_EVIDENCE, null, COL_STATUS + " != ?", new String[]{"SYNCED"},
                null, null, COL_SEQUENCE_NUMBER + " ASC");
        try {
            if (cursor.moveToFirst()) {
                do {
                    list.add(cursorToRecord(cursor));
                } while (cursor.moveToNext());
            }
        } finally {
            cursor.close();
        }
        return list;
    }

    public synchronized int getNextSequenceNumber(String deviceId) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery("SELECT MAX(" + COL_SEQUENCE_NUMBER + ") FROM " + TABLE_EVIDENCE, null);
        int max = 0;
        try {
            if (cursor.moveToFirst()) {
                max = cursor.getInt(0);
            }
        } finally {
            cursor.close();
        }
        return max + 1;
    }

    public synchronized EvidenceRecord getEvidenceById(String evidenceId) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.query(TABLE_EVIDENCE, null, COL_EVIDENCE_ID + " = ?", new String[]{evidenceId},
                null, null, null);
        try {
            if (cursor.moveToFirst()) {
                return cursorToRecord(cursor);
            }
        } finally {
            cursor.close();
        }
        return null;
    }

    public synchronized void deleteEvidence(String evidenceId) {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_EVIDENCE, COL_EVIDENCE_ID + " = ?", new String[]{evidenceId});
    }

    public synchronized void clearAll() {
        SQLiteDatabase db = getWritableDatabase();
        db.delete(TABLE_EVIDENCE, null, null);
    }

    private EvidenceRecord cursorToRecord(Cursor c) {
        EvidenceRecord r = new EvidenceRecord();
        r.setEvidenceId(c.getString(c.getColumnIndexOrThrow(COL_EVIDENCE_ID)));
        r.setDeviceId(c.getString(c.getColumnIndexOrThrow(COL_DEVICE_ID)));
        r.setFarmId(c.getString(c.getColumnIndexOrThrow(COL_FARM_ID)));
        r.setSequenceNumber(c.getInt(c.getColumnIndexOrThrow(COL_SEQUENCE_NUMBER)));
        r.setLifecycleStage(c.getString(c.getColumnIndexOrThrow(COL_LIFECYCLE_STAGE)));
        r.setCaptureSource(c.getString(c.getColumnIndexOrThrow(COL_CAPTURE_SOURCE)));
        r.setRawFilePath(c.getString(c.getColumnIndexOrThrow(COL_RAW_FILE_PATH)));
        r.setImageHash(c.getString(c.getColumnIndexOrThrow(COL_IMAGE_HASH)));
        r.setEnvelopeJson(c.getString(c.getColumnIndexOrThrow(COL_ENVELOPE_JSON)));
        r.setSignatureB64(c.getString(c.getColumnIndexOrThrow(COL_SIGNATURE_B64)));
        r.setStatus(c.getString(c.getColumnIndexOrThrow(COL_STATUS)));
        r.setRetryCount(c.getInt(c.getColumnIndexOrThrow(COL_RETRY_COUNT)));
        r.setServerReceipt(c.getString(c.getColumnIndexOrThrow(COL_SERVER_RECEIPT)));
        r.setErrorMessage(c.getString(c.getColumnIndexOrThrow(COL_ERROR_MESSAGE)));
        r.setCreatedAt(c.getString(c.getColumnIndexOrThrow(COL_CREATED_AT)));
        r.setUpdatedAt(c.getString(c.getColumnIndexOrThrow(COL_UPDATED_AT)));
        return r;
    }
}
