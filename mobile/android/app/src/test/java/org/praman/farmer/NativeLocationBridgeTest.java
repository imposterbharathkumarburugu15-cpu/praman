package org.praman.farmer;

import org.json.JSONObject;
import org.junit.Test;
import org.praman.farmer.location.NativeLocationBridge;

import static org.junit.Assert.*;

public class NativeLocationBridgeTest {

    @Test
    public void testLocationStateConstants() {
        assertEquals("ACQUIRING", NativeLocationBridge.STATE_ACQUIRING);
        assertEquals("LOCATION_ACQUIRED", NativeLocationBridge.STATE_LOCATION_ACQUIRED);
        assertEquals("ACCURACY_INSUFFICIENT", NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT);
        assertEquals("PERMISSION_REQUIRED", NativeLocationBridge.STATE_PERMISSION_REQUIRED);
        assertEquals("GPS_UNAVAILABLE", NativeLocationBridge.STATE_GPS_UNAVAILABLE);
        assertEquals("LOCATION_UNAVAILABLE", NativeLocationBridge.STATE_LOCATION_UNAVAILABLE);
    }

    @Test
    public void testEvaluateLocationAccuracyThresholds() {
        float standardThreshold = 25.0f;

        // 8.5m <= 25.0m -> LOCATION_ACQUIRED
        assertEquals(NativeLocationBridge.STATE_LOCATION_ACQUIRED,
                NativeLocationBridge.evaluateAccuracy(8.5f, standardThreshold));

        // 25.0m boundary -> LOCATION_ACQUIRED
        assertEquals(NativeLocationBridge.STATE_LOCATION_ACQUIRED,
                NativeLocationBridge.evaluateAccuracy(25.0f, standardThreshold));

        // 25.1m > 25.0m -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(25.1f, standardThreshold));

        // 45.0m > 25.0m -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(45.0f, standardThreshold));

        // 0.0m invalid/unreported -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(0.0f, standardThreshold));

        // Negative accuracy -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(-1.0f, standardThreshold));

        // Custom threshold 50.0m: 45.0m is now acceptable
        assertEquals(NativeLocationBridge.STATE_LOCATION_ACQUIRED,
                NativeLocationBridge.evaluateAccuracy(45.0f, 50.0f));

        // Custom threshold 5.0m: 8.5m is now insufficient
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(8.5f, 5.0f));
    }

    @Test
    public void testLocationJsonFormatting() throws Exception {
        double lat = 17.401234;
        double lng = 78.504321;
        float acc = 4.2f;
        long time = 1731215123456L;
        String provider = "gps";
        boolean isMock = false;
        String state = NativeLocationBridge.STATE_LOCATION_ACQUIRED;

        JSONObject obj = NativeLocationBridge.formatLocationJson(lat, lng, acc, time, provider, isMock, state, null);

        assertEquals("LOCATION_ACQUIRED", obj.getString("state"));
        assertEquals(17.401234, obj.getDouble("latitude"), 0.000001);
        assertEquals(78.504321, obj.getDouble("longitude"), 0.000001);
        assertEquals(4.2, obj.getDouble("accuracy"), 0.01);
        assertEquals(1731215123456L, obj.getLong("timestamp"));
        assertEquals("gps", obj.getString("provider"));
        assertFalse(obj.getBoolean("isMock"));
        assertFalse(obj.has("error"));
    }

    @Test
    public void testLocationJsonWithError() throws Exception {
        JSONObject obj = NativeLocationBridge.formatLocationJson(
                17.385, 78.486, 65.0f, 1731215000000L, "network", true,
                NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT, "Move to open sky"
        );

        assertEquals("ACCURACY_INSUFFICIENT", obj.getString("state"));
        assertTrue(obj.getBoolean("isMock"));
        assertEquals("Move to open sky", obj.getString("error"));
    }

    @Test
    public void testMockLocationDetectionLogic() {
        assertFalse(NativeLocationBridge.isMockLocation(null));
    }
}
