package org.praman.farmer;

import org.json.JSONObject;
import org.junit.Test;
import org.praman.farmer.sync.EvidenceSyncEngine;

import static org.junit.Assert.*;

public class EvidenceAutoEnrollmentTest {

    @Test
    public void testDefaultBackendUrl() {
        assertEquals("http://10.0.2.2:8000", EvidenceSyncEngine.DEFAULT_BACKEND_URL);
    }

    @Test
    public void testIndianPhoneNumberValidationAndFormatting() {
        // Raw 10-digit number
        String raw10 = "9848012345";
        String formatted = raw10.startsWith("+91") ? raw10 : ("+91" + raw10);
        assertEquals("+919848012345", formatted);
        assertTrue(formatted.matches("^\\+91[6-9]\\d{9}$"));

        // Already formatted E.164 number
        String alreadyFormatted = "+919876543210";
        String result = alreadyFormatted.startsWith("+91") ? alreadyFormatted : ("+91" + alreadyFormatted);
        assertEquals("+919876543210", result);
        assertTrue(result.matches("^\\+91[6-9]\\d{9}$"));
    }

    @Test
    public void testFarmerEnrollmentPayloadGeneration() throws Exception {
        String farmerId = "farmer_dev_abc123";
        String fullName = "Anand Rao";
        String phone = "+919848012345";
        String lang = "te";

        JSONObject fPayload = new JSONObject();
        fPayload.put("id", farmerId);
        fPayload.put("farmer_id", farmerId);
        fPayload.put("full_name", fullName);
        fPayload.put("phone_number", phone);
        fPayload.put("language_pref", lang);

        assertEquals("farmer_dev_abc123", fPayload.getString("id"));
        assertEquals("farmer_dev_abc123", fPayload.getString("farmer_id"));
        assertEquals("Anand Rao", fPayload.getString("full_name"));
        assertEquals("+919848012345", fPayload.getString("phone_number"));
        assertEquals("te", fPayload.getString("language_pref"));
    }

    @Test
    public void testDeviceEnrollmentPayloadGeneration() throws Exception {
        String deviceId = "dev_hardware_test_01";
        String farmerId = "farmer_dev_abc123";
        String samplePublicKeyPem = "-----BEGIN PUBLIC KEY-----\n" +
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE1234567890abcdef1234567890abcdef\n" +
                "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef==\n" +
                "-----END PUBLIC KEY-----";

        JSONObject dPayload = new JSONObject();
        dPayload.put("device_id", deviceId);
        dPayload.put("id", deviceId);
        dPayload.put("farmer_id", farmerId);
        dPayload.put("public_key_pem", samplePublicKeyPem.trim());

        assertEquals("dev_hardware_test_01", dPayload.getString("device_id"));
        assertEquals("dev_hardware_test_01", dPayload.getString("id"));
        assertEquals("farmer_dev_abc123", dPayload.getString("farmer_id"));
        assertTrue(dPayload.getString("public_key_pem").contains("BEGIN PUBLIC KEY"));
    }
}
