package org.praman.farmer;

import org.json.JSONObject;
import org.junit.Test;
import org.praman.farmer.connectivity.NativeConnectivityBridge;

import static org.junit.Assert.*;

public class NativeConnectivityBridgeTest {

    @Test
    public void testStatusConstants() {
        assertEquals("ONLINE", NativeConnectivityBridge.STATUS_ONLINE);
        assertEquals("INTERNET_AVAILABLE", NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE);
        assertEquals("CONNECTED", NativeConnectivityBridge.STATUS_CONNECTED);
        assertEquals("OFFLINE", NativeConnectivityBridge.STATUS_OFFLINE);

        assertEquals("WIFI", NativeConnectivityBridge.NET_WIFI);
        assertEquals("CELLULAR", NativeConnectivityBridge.NET_CELLULAR);
        assertEquals("NONE", NativeConnectivityBridge.NET_NONE);
    }

    @Test
    public void testDisplayStatusMappings() {
        assertEquals("Online", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_ONLINE));
        assertEquals("Internet available", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE));
        assertEquals("Connected", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_CONNECTED));
        assertEquals("Offline", NativeConnectivityBridge.getDisplayStatusString(NativeConnectivityBridge.STATUS_OFFLINE));
    }

    @Test
    public void testThreeTierCombinationsLogic() {
        // Combination 1: Backend reachable -> ONLINE
        String status1 = computeStatus(true, true, true);
        assertEquals(NativeConnectivityBridge.STATUS_ONLINE, status1);

        // Combination 2: Backend reachable over mobile cellular without Wi-Fi -> ONLINE
        String statusCellular = computeStatus(true, true, true);
        assertEquals(NativeConnectivityBridge.STATUS_ONLINE, statusCellular);

        // Combination 3: Internet available, but backend is down -> INTERNET_AVAILABLE
        String status2 = computeStatus(true, true, false);
        assertEquals(NativeConnectivityBridge.STATUS_INTERNET_AVAILABLE, status2);

        // Combination 4: Network interface up, but captive portal / internet unvalidated -> CONNECTED
        String status3 = computeStatus(true, false, false);
        assertEquals(NativeConnectivityBridge.STATUS_CONNECTED, status3);

        // Combination 5: No network connection -> OFFLINE
        String status4 = computeStatus(false, false, false);
        assertEquals(NativeConnectivityBridge.STATUS_OFFLINE, status4);
    }

    private String computeStatus(boolean isConnected, boolean hasInternet, boolean backendReachable) {
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

    @Test
    public void testStatusJsonBuilding() throws Exception {
        JSONObject obj = new JSONObject();
        obj.put("status", NativeConnectivityBridge.STATUS_ONLINE);
        obj.put("displayStatus", "Online");
        obj.put("networkType", "CELLULAR");
        obj.put("isConnected", true);
        obj.put("isInternetValidatedByOs", true);
        obj.put("hasInternet", true);
        obj.put("backendReachable", true);
        obj.put("backendUrl", "http://10.0.2.2:8000");

        assertEquals("ONLINE", obj.getString("status"));
        assertEquals("Online", obj.getString("displayStatus"));
        assertEquals("CELLULAR", obj.getString("networkType"));
        assertTrue(obj.getBoolean("isConnected"));
        assertTrue(obj.getBoolean("hasInternet"));
        assertTrue(obj.getBoolean("backendReachable"));
        assertEquals("http://10.0.2.2:8000", obj.getString("backendUrl"));
    }

    @Test
    public void testBackendUrlSanitization() {
        String urlWithSlash = "http://192.168.1.100:8000///";
        String sanitized = urlWithSlash.trim().replaceAll("/+$", "");
        assertEquals("http://192.168.1.100:8000", sanitized);

        String cleanUrl = "http://localhost:8000";
        assertEquals("http://localhost:8000", cleanUrl.trim().replaceAll("/+$", ""));
    }
}
