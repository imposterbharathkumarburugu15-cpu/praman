package org.praman.farmer;

import org.json.JSONObject;
import org.junit.Test;
import org.praman.farmer.crypto.AndroidKeystoreBridge;
import org.praman.farmer.storage.EvidenceRecord;

import java.math.BigInteger;

import static org.junit.Assert.*;

public class EvidenceUnitTest {

    @Test
    public void testEvidenceRecordSerialization() throws Exception {
        EvidenceRecord record = new EvidenceRecord();
        record.setEvidenceId("ev_test_123");
        record.setDeviceId("dev_uuid_456");
        record.setFarmId("farm_uuid_789");
        record.setSequenceNumber(5);
        record.setLifecycleStage("CROP_GROWTH");
        record.setCaptureSource("CAMERA");
        record.setRawFilePath("/data/user/0/org.praman.farmer/files/photo.jpg");
        record.setImageHash("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
        record.setEnvelopeJson("{\"schema_version\":\"1.0\"}");
        record.setSignatureB64("MEQCIBaX0/x9o8Qe6v2A6s==");
        record.setStatus("QUEUED");
        record.setRetryCount(1);
        record.setCreatedAt("2026-11-09T18:00:00Z");

        JSONObject json = record.toJson();
        assertEquals("ev_test_123", json.getString("evidence_id"));
        assertEquals("dev_uuid_456", json.getString("device_id"));
        assertEquals(5, json.getInt("sequence_number"));
        assertEquals("CROP_GROWTH", json.getString("lifecycle_stage"));
        assertEquals("QUEUED", json.getString("status"));
        assertEquals(1, json.getInt("retry_count"));

        // Roundtrip deserialization
        EvidenceRecord restored = EvidenceRecord.fromJson(json);
        assertEquals(record.getEvidenceId(), restored.getEvidenceId());
        assertEquals(record.getDeviceId(), restored.getDeviceId());
        assertEquals(record.getFarmId(), restored.getFarmId());
        assertEquals(record.getSequenceNumber(), restored.getSequenceNumber());
        assertEquals(record.getLifecycleStage(), restored.getLifecycleStage());
        assertEquals(record.getCaptureSource(), restored.getCaptureSource());
        assertEquals(record.getRawFilePath(), restored.getRawFilePath());
        assertEquals(record.getImageHash(), restored.getImageHash());
        assertEquals(record.getEnvelopeJson(), restored.getEnvelopeJson());
        assertEquals(record.getSignatureB64(), restored.getSignatureB64());
        assertEquals(record.getStatus(), restored.getStatus());
        assertEquals(record.getRetryCount(), restored.getRetryCount());
    }

    @Test
    public void testLowSNormalization() {
        // secp256r1 curve order n
        BigInteger curveN = new BigInteger("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16);
        BigInteger halfN = curveN.shiftRight(1);

        // Low-s test
        BigInteger lowS = BigInteger.valueOf(123456);
        assertTrue(lowS.compareTo(halfN) <= 0);

        // High-s test
        BigInteger highS = curveN.subtract(BigInteger.valueOf(999999));
        assertTrue(highS.compareTo(halfN) > 0);

        // Construct DER bytes with high-s: 0x30 [len] 0x02 [rLen] [rBytes] 0x02 [sLen] [sBytes]
        byte[] rBytes = BigInteger.valueOf(42).toByteArray();
        byte[] sBytes = highS.toByteArray();

        int totalLen = 2 + rBytes.length + 2 + sBytes.length;
        byte[] derHighS = new byte[2 + totalLen];
        derHighS[0] = 0x30;
        derHighS[1] = (byte) totalLen;
        derHighS[2] = 0x02;
        derHighS[3] = (byte) rBytes.length;
        System.arraycopy(rBytes, 0, derHighS, 4, rBytes.length);
        int sTagIdx = 4 + rBytes.length;
        derHighS[sTagIdx] = 0x02;
        derHighS[sTagIdx + 1] = (byte) sBytes.length;
        System.arraycopy(sBytes, 0, derHighS, sTagIdx + 2, sBytes.length);

        // Normalize
        byte[] normalized = AndroidKeystoreBridge.normalizeDERToLowS(derHighS);
        assertNotNull(normalized);
        assertEquals(0x30, normalized[0]);

        // Parse normalized s
        int normRLen = normalized[3];
        int normSTagIdx = 4 + normRLen;
        int normSLen = normalized[normSTagIdx + 1];
        byte[] normSBytes = new byte[normSLen];
        System.arraycopy(normalized, normSTagIdx + 2, normSBytes, 0, normSLen);

        BigInteger parsedNormalizedS = new BigInteger(normSBytes);
        assertTrue("Normalized s must be <= halfN", parsedNormalizedS.compareTo(halfN) <= 0);
        assertEquals(BigInteger.valueOf(999999), parsedNormalizedS);
    }
}
