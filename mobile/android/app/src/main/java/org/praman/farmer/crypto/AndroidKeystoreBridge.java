package org.praman.farmer.crypto;

import android.os.Build;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyInfo;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.util.Log;
import android.webkit.JavascriptInterface;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.ProviderException;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;

/**
 * Native Hardware Keystore Bridge for NIST P-256 (secp256r1) ECDSA cryptographic operations.
 * Inspects hardware security levels (StrongBox, TEE, Software), normalizes DER signatures
 * to strict low-s form, and returns structured JSON responses.
 */
public class AndroidKeystoreBridge {
    private static final String TAG = "AndroidKeystoreBridge";
    private static final String KEYSTORE_PROVIDER = "AndroidKeyStore";
    private static final String DEFAULT_ALIAS = "praman_device_key";
    
    // secp256r1 curve order n
    private static final BigInteger CURVE_N = new BigInteger("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16);
    private static final BigInteger HALF_N = CURVE_N.shiftRight(1);

    @JavascriptInterface
    public String generateKey(String alias) {
        JSONObject response = new JSONObject();
        try {
            if (alias == null || alias.trim().isEmpty()) {
                alias = DEFAULT_ALIAS;
            } else {
                alias = alias.trim();
            }

            KeyPair kp = null;
            KeyPairGenerator kpg = KeyPairGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_EC, KEYSTORE_PROVIDER);

            // Attempt StrongBox hardware security if available on Android 9+ (API 28+)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                try {
                    KeyGenParameterSpec spec = new KeyGenParameterSpec.Builder(
                            alias,
                            KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
                            .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                            .setDigests(KeyProperties.DIGEST_SHA256)
                            .setIsStrongBoxBacked(true)
                            .build();
                    kpg.initialize(spec);
                    kp = kpg.generateKeyPair();
                    Log.i(TAG, "Generated key with StrongBox backing: " + alias);
                } catch (ProviderException sbEx) {
                    Log.i(TAG, "StrongBox unavailable, falling back to TEE/standard Keystore: " + sbEx.getMessage());
                }
            }

            if (kp == null) {
                KeyGenParameterSpec spec = new KeyGenParameterSpec.Builder(
                        alias,
                        KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
                        .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                        .setDigests(KeyProperties.DIGEST_SHA256)
                        .build();
                kpg.initialize(spec);
                kp = kpg.generateKeyPair();
            }

            String securityLevel = probeSecurityLevel(alias);
            String pem = exportPublicKeyPEM(kp.getPublic());

            response.put("success", true);
            response.put("alias", alias);
            response.put("securityLevel", securityLevel);
            response.put("publicKeyPem", pem);
            return response.toString();
        } catch (Exception e) {
            Log.e(TAG, "Key generation failed", e);
            try {
                response.put("success", false);
                response.put("error", e.getMessage() != null ? e.getMessage() : e.toString());
            } catch (Exception ignored) {}
            return response.toString();
        }
    }

    @JavascriptInterface
    public String getPublicKeyPEM(String alias) {
        JSONObject response = new JSONObject();
        try {
            if (alias == null || alias.trim().isEmpty()) {
                alias = DEFAULT_ALIAS;
            } else {
                alias = alias.trim();
            }

            KeyStore ks = KeyStore.getInstance(KEYSTORE_PROVIDER);
            ks.load(null);

            if (!ks.containsAlias(alias)) {
                // Auto-generate if not existing
                return generateKey(alias);
            }

            PublicKey pub = ks.getCertificate(alias).getPublicKey();
            String securityLevel = probeSecurityLevel(alias);
            String pem = exportPublicKeyPEM(pub);

            response.put("success", true);
            response.put("alias", alias);
            response.put("securityLevel", securityLevel);
            response.put("publicKeyPem", pem);
            return response.toString();
        } catch (Exception e) {
            Log.e(TAG, "Failed to get public key", e);
            try {
                response.put("success", false);
                response.put("error", e.getMessage() != null ? e.getMessage() : e.toString());
            } catch (Exception ignored) {}
            return response.toString();
        }
    }

    @JavascriptInterface
    public String getSecurityInfo(String alias) {
        JSONObject response = new JSONObject();
        try {
            if (alias == null || alias.trim().isEmpty()) {
                alias = DEFAULT_ALIAS;
            } else {
                alias = alias.trim();
            }
            String level = probeSecurityLevel(alias);
            response.put("success", true);
            response.put("alias", alias);
            response.put("securityLevel", level);
            response.put("algorithm", "EC");
            response.put("curve", "secp256r1");
            return response.toString();
        } catch (Exception e) {
            try {
                response.put("success", false);
                response.put("error", e.getMessage());
            } catch (Exception ignored) {}
            return response.toString();
        }
    }

    @JavascriptInterface
    public String signPayload(String alias, String canonicalJson) {
        JSONObject response = new JSONObject();
        try {
            if (alias == null || alias.trim().isEmpty()) {
                alias = DEFAULT_ALIAS;
            } else {
                alias = alias.trim();
            }

            if (canonicalJson == null || canonicalJson.isEmpty()) {
                response.put("success", false);
                response.put("error", "Payload to sign cannot be empty");
                return response.toString();
            }

            KeyStore ks = KeyStore.getInstance(KEYSTORE_PROVIDER);
            ks.load(null);

            if (!ks.containsAlias(alias)) {
                generateKey(alias);
                ks.load(null);
            }

            PrivateKey priv = (PrivateKey) ks.getKey(alias, null);
            if (priv == null) {
                response.put("success", false);
                response.put("error", "Private key unavailable for alias: " + alias);
                return response.toString();
            }

            Signature s = Signature.getInstance("SHA256withECDSA");
            s.initSign(priv);
            s.update(canonicalJson.getBytes(StandardCharsets.UTF_8));
            byte[] derSignature = s.sign();
            byte[] normalized = normalizeDERToLowS(derSignature);
            String sigB64 = Base64.encodeToString(normalized, Base64.NO_WRAP);
            String securityLevel = probeSecurityLevel(alias);

            response.put("success", true);
            response.put("signature", sigB64);
            response.put("securityLevel", securityLevel);
            return response.toString();
        } catch (Exception e) {
            Log.e(TAG, "Signing error", e);
            try {
                response.put("success", false);
                response.put("error", e.getMessage() != null ? e.getMessage() : e.toString());
            } catch (Exception ignored) {}
            return response.toString();
        }
    }

    public String probeSecurityLevel(String alias) {
        try {
            KeyStore ks = KeyStore.getInstance(KEYSTORE_PROVIDER);
            ks.load(null);
            if (!ks.containsAlias(alias)) {
                return "SOFTWARE";
            }
            PrivateKey priv = (PrivateKey) ks.getKey(alias, null);
            if (priv == null) {
                return "SOFTWARE";
            }

            KeyFactory factory = KeyFactory.getInstance(KeyProperties.KEY_ALGORITHM_EC, KEYSTORE_PROVIDER);
            KeyInfo keyInfo = factory.getKeySpec(priv, KeyInfo.class);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                int level = keyInfo.getSecurityLevel();
                if (level == KeyProperties.SECURITY_LEVEL_STRONGBOX) {
                    return "STRONGBOX";
                } else if (level == KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT) {
                    return "TEE";
                } else {
                    return "SOFTWARE";
                }
            } else {
                // Android 7.0 - 11 (API 24-30)
                boolean insideHardware = keyInfo.isInsideSecureHardware();
                return insideHardware ? "TEE" : "SOFTWARE";
            }
        } catch (Exception e) {
            Log.w(TAG, "Could not determine exact key security level: " + e.getMessage());
            return "TEE"; // Standard Android Keystore default
        }
    }

    private String exportPublicKeyPEM(PublicKey pub) {
        String b64 = Base64.encodeToString(pub.getEncoded(), Base64.NO_WRAP);
        return "-----BEGIN PUBLIC KEY-----\n" + b64 + "\n-----END PUBLIC KEY-----";
    }

    public static byte[] normalizeDERToLowS(byte[] derSignature) {
        try {
            if (derSignature == null || derSignature.length < 8 || derSignature[0] != 0x30) {
                return derSignature;
            }
            int rTagIndex = 2;
            if ((derSignature[1] & 0x80) != 0) {
                int numBytes = derSignature[1] & 0x7F;
                rTagIndex = 2 + numBytes;
            }
            if (derSignature[rTagIndex] != 0x02) return derSignature;
            int rLen = derSignature[rTagIndex + 1];
            int rStart = rTagIndex + 2;

            int sTagIndex = rStart + rLen;
            if (derSignature[sTagIndex] != 0x02) return derSignature;
            int sLen = derSignature[sTagIndex + 1];
            int sStart = sTagIndex + 2;

            byte[] rBytes = new byte[rLen];
            System.arraycopy(derSignature, rStart, rBytes, 0, rLen);
            byte[] sBytes = new byte[sLen];
            System.arraycopy(derSignature, sStart, sBytes, 0, sLen);

            BigInteger s = new BigInteger(sBytes);
            if (s.compareTo(HALF_N) > 0) {
                s = CURVE_N.subtract(s);
                byte[] newS = s.toByteArray();

                ByteArrayOutputStream out = new ByteArrayOutputStream();
                out.write(0x30); // SEQUENCE
                int totalLen = 2 + rBytes.length + 2 + newS.length;
                out.write(totalLen);
                out.write(0x02); // INTEGER r
                out.write(rBytes.length);
                out.write(rBytes);
                out.write(0x02); // INTEGER s
                out.write(newS.length);
                out.write(newS);
                return out.toByteArray();
            }
        } catch (Exception e) {
            Log.w(TAG, "Normalization to low-s encountered issue, returning original: " + e.getMessage());
        }
        return derSignature;
    }
}
