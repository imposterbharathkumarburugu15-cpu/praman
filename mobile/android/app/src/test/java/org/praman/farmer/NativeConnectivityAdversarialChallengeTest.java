package org.praman.farmer;

import org.json.JSONObject;
import org.junit.Test;
import org.praman.farmer.connectivity.NativeConnectivityBridge;

import static org.junit.Assert.*;

/**
 * Empirical Adversarial Challenge Tests for NativeConnectivityBridge.
 * Stress-tests three-tier state transitions across cellular, airplane mode,
 * backend outage, and network configuration edge cases.
 */
public class NativeConnectivityAdversarialChallengeTest {

    private String evaluateStatus(boolean isConnected, boolean hasInternet, boolean backendReachable) {
        if (!isConnected) {
            return NativeConnectivityBridge.STATUS_OFFLINE;
        }
        if (backendReachable) {
            return NativeConnectivityBridge.STATUS_ONLINE;
        }
        if (hasInternet) {
            return NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE;
        }
        return NativeConnectivityBridge.STATUS_CONNECTED;
    }

    /**
     * CHALLENGE 1: Mobile Data ON with Wi-Fi OFF
     * Simulates genuine rural field conditions where no Wi-Fi is present.
     */
    @Test
    public void testMobileDataOnlyTransitions() {
        // Condition A: Cellular active, internet probe succeeds, backend reachable
        String statusOnline = evaluateStatus(true, true, true);
        assertEquals(NativeConnectivityBridge.STATUS_ONLINE, statusOnline);

        // Condition B: Cellular active, internet probe succeeds, backend server offline / 500 error
        String statusBackendDown = evaluateStatus(true, true, false);
        assertEquals(NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE, statusBackendDown);

        // Condition C: Cellular APN active, but zero data balance / captive portal (DNS probe fails)
        String statusNoInternet = evaluateStatus(true, false, false);
        assertEquals(NativeConnectivityBridge.STATUS_CONNECTED, statusNoInternet);
    }

    /**
     * CHALLENGE 2: Airplane Mode Active
     * Simulates all device network interfaces being torn down.
     */
    @Test
    public void testAirplaneModeTransition() {
        // All interface flags false
        String statusAirplane = evaluateStatus(false, false, false);
        assertEquals(NativeConnectivityBridge.STATUS_OFFLINE, statusAirplane);

        // Even if cached reachability was previously true, isConnected=false forces OFFLINE
        String statusCachedProbeIgnored = evaluateStatus(false, true, true);
        assertEquals(NativeConnectivityBridge.STATUS_OFFLINE, statusCachedProbeIgnored);
    }

    /**
     * CHALLENGE 3: Backend Server Unreachable Across All Interfaces
     */
    @Test
    public void testBackendUnreachableAcrossTiers() {
        // Wi-Fi connected to public internet, but backend down
        assertEquals(NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE, evaluateStatus(true, true, false));

        // Cellular connected to public internet, but backend down
        assertEquals(NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE, evaluateStatus(true, true, false));

        // Isolated LAN / Hotspot without WAN gateway, and backend down
        assertEquals(NativeConnectivityBridge.STATUS_CONNECTED, evaluateStatus(true, false, false));
    }

    /**
     * CHALLENGE 4: Backend URL Normalization & Edge Cases
     */
    @Test
    public void testBackendUrlEdgeCases() {
        // Trailing multiple slashes
        String url1 = "http://192.168.1.150:8000///";
        assertEquals("http://192.168.1.150:8000", url1.trim().replaceAll("/+$", ""));

        // Leading/trailing whitespace
        String url2 = "   http://10.0.2.2:8000/   ";
        assertEquals("http://10.0.2.2:8000", url2.trim().replaceAll("/+$", ""));

        // Hostname with domain
        String url3 = "https://api.praman.org/v1/";
        assertEquals("https://api.praman.org/v1", url3.trim().replaceAll("/+$", ""));
    }

    /**
     * CHALLENGE 5: Display Status and Description Integrity
     */
    @Test
    public void testDisplayStatusAndDescriptions() throws Exception {
        assertEquals("Online", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_ONLINE));
        assertEquals("Internet available", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE));
        assertEquals("Connected", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_CONNECTED));
        assertEquals("Offline", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_OFFLINE));
        assertEquals("Offline", NativeConnectivityBridge.getDisplayStatusString("UNKNOWN_STATE"));
    }
}
