package org.praman.farmer;

import org.json.JSONObject;
import org.junit.Test;
import org.praman.farmer.location.NativeLocationBridge;

import static org.junit.Assert.*;

/**
 * Empirical Adversarial Challenge Tests for NativeLocationBridge.
 * Stress-tests state transitions, threshold boundaries, mock provider detection,
 * and contract naming consistency.
 */
public class NativeLocationAdversarialChallengeTest {

    /**
     * CHALLENGE 1: GPS Disabled State Naming Discrepancy
     * Verifies what is actually returned when GPS is disabled.
     * PROJECT.md specifies "GPS_DISABLED", while ORIGINAL_REQUEST.md §2 mandates "GPS unavailable".
     */
    @Test
    public void testGpsDisabledStateNamingEmpirical() {
        // Empirical observation: The code implements STATE_GPS_UNAVAILABLE ("GPS_UNAVAILABLE")
        assertEquals("GPS_UNAVAILABLE", NativeLocationBridge.STATE_GPS_UNAVAILABLE);

        // Verify that NativeLocationBridge does NOT use "GPS_DISABLED"
        assertNotEquals("GPS_DISABLED", NativeLocationBridge.STATE_GPS_UNAVAILABLE);

        // Verify JSON response formatting with GPS_UNAVAILABLE
        JSONObject response = NativeLocationBridge.formatLocationJson(
                0.0, 0.0, 0.0f, System.currentTimeMillis(), "none", false,
                NativeLocationBridge.STATE_GPS_UNAVAILABLE, "Location providers disabled on device."
        );
        assertEquals("GPS_UNAVAILABLE", response.optString("state"));
        assertEquals("Location providers disabled on device.", response.optString("error"));
    }

    /**
     * CHALLENGE 2: Accuracy Boundary Stress-Testing
     * Tests exact boundaries: sub-threshold, exact threshold, epsilon above threshold,
     * extreme values, zero, negative, and NaN behavior.
     */
    @Test
    public void testAccuracyBoundaryConditions() {
        float threshold = 25.0f;

        // Sub-threshold -> LOCATION_ACQUIRED
        assertEquals(NativeLocationBridge.STATE_LOCATION_ACQUIRED,
                NativeLocationBridge.evaluateAccuracy(0.1f, threshold));
        assertEquals(NativeLocationBridge.STATE_LOCATION_ACQUIRED,
                NativeLocationBridge.evaluateAccuracy(24.999f, threshold));

        // Exact threshold boundary -> LOCATION_ACQUIRED
        assertEquals(NativeLocationBridge.STATE_LOCATION_ACQUIRED,
                NativeLocationBridge.evaluateAccuracy(25.0f, threshold));

        // Epsilon above threshold -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(25.001f, threshold));

        // Well above threshold -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(150.0f, threshold));

        // Zero accuracy (invalid / uncalibrated GPS sensor) -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(0.0f, threshold));

        // Negative accuracy (corrupted sensor reading) -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(-10.0f, threshold));

        // Float.POSITIVE_INFINITY -> ACCURACY_INSUFFICIENT
        assertEquals(NativeLocationBridge.STATE_ACCURACY_INSUFFICIENT,
                NativeLocationBridge.evaluateAccuracy(Float.POSITIVE_INFINITY, threshold));
    }

    /**
     * CHALLENGE 3: Float.NaN Accuracy Edge Case
     * In IEEE 754: (NaN <= 0.0f) is false, and (NaN > threshold) is false.
     * Documents how the current evaluateAccuracy implementation handles NaN.
     */
    @Test
    public void testAccuracyNaNEvaluation() {
        float threshold = 25.0f;
        String result = NativeLocationBridge.evaluateAccuracy(Float.NaN, threshold);
        // If evaluateAccuracy returns LOCATION_ACQUIRED on NaN, this is a verified edge case anomaly!
        // We observe the actual behavior:
        boolean isHandledAsAcquired = NativeLocationBridge.STATE_LOCATION_ACQUIRED.equals(result);
        System.out.println("Adversarial finding: evaluateAccuracy(Float.NaN, 25.0f) produced: " + result);
        // Note for handoff report: If NaN returns LOCATION_ACQUIRED, it should be hardened with Float.isNaN().
    }

    /**
     * CHALLENGE 4: Mock Location Flag Detection & Non-Suppression
     * Verifies that mock location indicators are captured as risk signals without
     * aborting or replacing coordinates with fake data.
     */
    @Test
    public void testMockLocationDetectionAndPreservation() throws Exception {
        double lat = 17.385044;
        double lng = 78.486671;
        float acc = 12.0f;
        long ts = 1731216000000L;

        // When mock provider is active
        JSONObject mockLocJson = NativeLocationBridge.formatLocationJson(
                lat, lng, acc, ts, "gps", true,
                NativeLocationBridge.STATE_LOCATION_ACQUIRED, null
        );

        assertTrue("Mock location flag must be true", mockLocJson.getBoolean("isMock"));
        assertEquals(17.385044, mockLocJson.getDouble("latitude"), 0.000001);
        assertEquals(78.486671, mockLocJson.getDouble("longitude"), 0.000001);
        assertEquals(12.0, mockLocJson.getDouble("accuracy"), 0.01);
        assertEquals("LOCATION_ACQUIRED", mockLocJson.getString("state"));
        assertFalse(mockLocJson.has("error"));
    }

    /**
     * CHALLENGE 5: Geographical Coordinate Boundary Extremes
     */
    @Test
    public void testCoordinateBoundaryExtremes() throws Exception {
        // Equator & Prime Meridian
        JSONObject equator = NativeLocationBridge.formatLocationJson(
                0.0, 0.0, 5.0f, 1000L, "fused", false, NativeLocationBridge.STATE_LOCATION_ACQUIRED, null
        );
        assertEquals(0.0, equator.getDouble("latitude"), 0.0001);
        assertEquals(0.0, equator.getDouble("longitude"), 0.0001);

        // North pole boundary
        JSONObject northPole = NativeLocationBridge.formatLocationJson(
                90.0, 0.0, 10.0f, 1000L, "gps", false, NativeLocationBridge.STATE_LOCATION_ACQUIRED, null
        );
        assertEquals(90.0, northPole.getDouble("latitude"), 0.0001);

        // Antimeridian boundary
        JSONObject antimeridian = NativeLocationBridge.formatLocationJson(
                -45.0, 180.0, 8.0f, 1000L, "gps", false, NativeLocationBridge.STATE_LOCATION_ACQUIRED, null
        );
        assertEquals(180.0, antimeridian.getDouble("longitude"), 0.0001);
    }
}
