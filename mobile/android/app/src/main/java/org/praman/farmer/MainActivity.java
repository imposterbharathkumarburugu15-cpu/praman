package org.praman.farmer;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.util.Log;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import org.json.JSONObject;
import org.praman.farmer.connectivity.NativeConnectivityBridge;
import org.praman.farmer.crypto.AndroidKeystoreBridge;
import org.praman.farmer.location.NativeLocationBridge;
import org.praman.farmer.storage.NativeStorageBridge;
import org.praman.farmer.sync.EvidenceSyncEngine;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private static final String TAG = "PRAMAN_MainActivity";
    private static final int REQUEST_CAMERA_CAPTURE = 1001;
    private static final int REQUEST_FILE_PICKER = 1002;
    private static final int REQUEST_PERMISSIONS = 2001;

    private WebView webView;
    private String currentPhotoPath;
    private final ExecutorService backgroundExecutor = Executors.newSingleThreadExecutor();

    private AndroidKeystoreBridge keystoreBridge;
    private EvidenceSyncEngine syncEngine;
    private NativeStorageBridge storageBridge;
    private NativeLocationBridge locationBridge;
    private NativeConnectivityBridge connectivityBridge;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);

        // Genuine Geolocation Permissions callback for WebView
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                callback.invoke(origin, true, false);
            }
        });
        webView.setWebViewClient(new WebViewClient());

        // Initialize Services & Bridges
        keystoreBridge = new AndroidKeystoreBridge();
        syncEngine = new EvidenceSyncEngine(this);
        storageBridge = new NativeStorageBridge(this, syncEngine);
        locationBridge = new NativeLocationBridge(this, webView);
        connectivityBridge = new NativeConnectivityBridge(this, webView, syncEngine);

        // Register Sync Listener to notify WebView
        syncEngine.setListener(new EvidenceSyncEngine.SyncListener() {
            @Override
            public void onSyncStarted() {
                evaluateJs("if(window.app && window.app.onSyncStarted){window.app.onSyncStarted();}");
            }

            @Override
            public void onItemSynced(String evidenceId, boolean success, String resultOrError) {
                try {
                    JSONObject payload = new JSONObject();
                    payload.put("evidence_id", evidenceId);
                    payload.put("success", success);
                    payload.put("result", resultOrError);
                    String js = String.format("if(window.app && window.app.onSyncItemResult){window.app.onSyncItemResult('%s', %b, %s);}",
                            evidenceId, success, JSONObject.quote(resultOrError));
                    evaluateJs(js);
                } catch (Exception ignored) {}
            }

            @Override
            public void onSyncFinished(int successCount, int failureCount) {
                String js = String.format("if(window.app && window.app.onSyncFinished){window.app.onSyncFinished(%d, %d);}",
                        successCount, failureCount);
                evaluateJs(js);
            }
        });

        // Register Bridges to JavaScript
        webView.addJavascriptInterface(keystoreBridge, "AndroidKeystoreBridge");
        webView.addJavascriptInterface(new NativeMediaBridge(), "NativeMediaBridge");
        webView.addJavascriptInterface(storageBridge, "NativeStorageBridge");
        webView.addJavascriptInterface(locationBridge, "NativeLocationBridge");
        webView.addJavascriptInterface(connectivityBridge, "NativeConnectivityBridge");

        // Request runtime permissions on startup
        requestNecessaryPermissions();

        // Load local app
        webView.loadUrl("file:///android_asset/index.html");
    }

    private void requestNecessaryPermissions() {
        List<String> perms = new ArrayList<>();
        perms.add(Manifest.permission.CAMERA);
        perms.add(Manifest.permission.ACCESS_FINE_LOCATION);
        perms.add(Manifest.permission.ACCESS_COARSE_LOCATION);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) { // Android 14+ (API 34)
            perms.add(Manifest.permission.READ_MEDIA_IMAGES);
            perms.add(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED);
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) { // Android 13 (API 33)
            perms.add(Manifest.permission.READ_MEDIA_IMAGES);
        } else {
            perms.add(Manifest.permission.READ_EXTERNAL_STORAGE);
            if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P) {
                perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
            }
        }

        List<String> needed = new ArrayList<>();
        for (String perm : perms) {
            if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
                needed.add(perm);
            }
        }

        if (!needed.isEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toArray(new String[0]), REQUEST_PERMISSIONS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);

        boolean locationGranted = false;
        for (int i = 0; i < permissions.length; i++) {
            String perm = permissions[i];
            boolean granted = (grantResults.length > i && grantResults[i] == PackageManager.PERMISSION_GRANTED);
            Log.d(TAG, "Permission result: " + perm + " -> " + (granted ? "GRANTED" : "DENIED"));
            if ((Manifest.permission.ACCESS_FINE_LOCATION.equals(perm) || Manifest.permission.ACCESS_COARSE_LOCATION.equals(perm)) && granted) {
                locationGranted = true;
            }

            String js = String.format(Locale.US,
                    "if(window.app && window.app.onPermissionResult){window.app.onPermissionResult('%s', %b);}",
                    perm, granted);
            evaluateJs(js);
        }

        if (locationGranted && locationBridge != null) {
            locationBridge.requestLocationUpdates();
        }
    }

    private File createImageFile() throws IOException {
        String timeStamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
        String imageFileName = "PRAMAN_" + timeStamp + "_";
        File storageDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
        if (storageDir == null) {
            storageDir = getFilesDir();
        }
        if (!storageDir.exists()) {
            storageDir.mkdirs();
        }
        File image = File.createTempFile(imageFileName, ".jpg", storageDir);
        currentPhotoPath = image.getAbsolutePath();
        return image;
    }

    public void launchNativeCamera() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, REQUEST_PERMISSIONS);
            return;
        }

        Intent takePictureIntent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        File photoFile = null;
        try {
            photoFile = createImageFile();
        } catch (IOException ex) {
            Toast.makeText(this, "Storage error creating capture file: " + ex.getMessage(), Toast.LENGTH_SHORT).show();
            return;
        }

        if (photoFile != null) {
            Uri photoURI = FileProvider.getUriForFile(this,
                    "org.praman.farmer.fileprovider",
                    photoFile);
            takePictureIntent.putExtra(MediaStore.EXTRA_OUTPUT, photoURI);

            try {
                startActivityForResult(takePictureIntent, REQUEST_CAMERA_CAPTURE);
            } catch (ActivityNotFoundException e) {
                Toast.makeText(this, "No camera application found on device.", Toast.LENGTH_LONG).show();
                Log.e(TAG, "Camera activity not found", e);
            }
        }
    }

    public void launchFilePicker() {
        Intent intent;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // Android 13+ Modern Photo Picker
            intent = new Intent(MediaStore.ACTION_PICK_IMAGES);
            intent.setType("image/*");
        } else {
            // Android 7-12 Document / Content Picker
            intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("image/*");
        }

        try {
            startActivityForResult(intent, REQUEST_FILE_PICKER);
        } catch (ActivityNotFoundException e) {
            // Fallback to legacy GET_CONTENT
            Intent fallbackIntent = new Intent(Intent.ACTION_GET_CONTENT);
            fallbackIntent.setType("image/*");
            fallbackIntent.addCategory(Intent.CATEGORY_OPENABLE);
            try {
                startActivityForResult(Intent.createChooser(fallbackIntent, "Select Evidence Photo"), REQUEST_FILE_PICKER);
            } catch (Exception ex) {
                Toast.makeText(this, "No photo picker available on device.", Toast.LENGTH_SHORT).show();
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (resultCode == Activity.RESULT_OK) {
            if (requestCode == REQUEST_CAMERA_CAPTURE) {
                if (currentPhotoPath != null) {
                    processPhotoFileAsync(new File(currentPhotoPath), "CAMERA");
                }
            } else if (requestCode == REQUEST_FILE_PICKER && data != null && data.getData() != null) {
                copyUriToLocalFileAsync(data.getData());
            }
        } else if (resultCode == Activity.RESULT_CANCELED) {
            evaluateJs("if(window.app && window.app.onCaptureCancelled){window.app.onCaptureCancelled();}");
        }
    }

    private void copyUriToLocalFileAsync(Uri uri) {
        backgroundExecutor.execute(() -> {
            try {
                String timeStamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
                File storageDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
                if (storageDir == null) {
                    storageDir = getFilesDir();
                }
                File destFile = new File(storageDir, "PRAMAN_PICK_" + timeStamp + ".jpg");

                try (InputStream is = getContentResolver().openInputStream(uri);
                     OutputStream os = new FileOutputStream(destFile)) {
                    if (is == null) {
                        throw new IOException("Cannot open input stream from URI: " + uri);
                    }
                    byte[] buffer = new byte[16384];
                    int read;
                    while ((read = is.read(buffer)) != -1) {
                        os.write(buffer, 0, read);
                    }
                    os.flush();
                }

                // Process the permanently cached raw file
                processPhotoFileAsync(destFile, "FILE_UPLOAD");

            } catch (Exception e) {
                Log.e(TAG, "Failed to copy picked image", e);
                runOnUiThread(() -> Toast.makeText(MainActivity.this,
                        "Failed to import selected image: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        });
    }

    /**
     * Prevents heap OutOfMemoryError on 12MP-48MP smartphone photos by:
     * 1. Streaming SHA-256 calculation without holding entire byte array in RAM.
     * 2. Decoding image dimensions using inJustDecodeBounds = true.
     * 3. Calculating inSampleSize power-of-2 downsampling for the UI preview thumbnail.
     * 4. Retaining the raw file path on disk for verification and offline multipart upload.
     */
    private void processPhotoFileAsync(File file, String source) {
        backgroundExecutor.execute(() -> {
            try {
                if (!file.exists() || file.length() == 0) {
                    throw new IOException("Photo file does not exist or is empty: " + file.getAbsolutePath());
                }

                // 1. Compute SHA-256 via streaming (constant 16KB heap memory)
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                try (InputStream fis = new FileInputStream(file)) {
                    byte[] buffer = new byte[16384];
                    int read;
                    while ((read = fis.read(buffer)) != -1) {
                        digest.update(buffer, 0, read);
                    }
                }
                byte[] hashBytes = digest.digest();
                StringBuilder sb = new StringBuilder();
                for (byte b : hashBytes) {
                    sb.append(String.format("%02x", b));
                }
                String sha256 = sb.toString();

                // 2. Decode original dimensions without loading pixel data
                BitmapFactory.Options boundsOptions = new BitmapFactory.Options();
                boundsOptions.inJustDecodeBounds = true;
                BitmapFactory.decodeFile(file.getAbsolutePath(), boundsOptions);
                int origWidth = boundsOptions.outWidth;
                int origHeight = boundsOptions.outHeight;

                // 3. Compute inSampleSize power-of-2 downsampling (target ~800px max preview)
                int maxDim = 800;
                int inSampleSize = 1;
                if (origHeight > maxDim || origWidth > maxDim) {
                    final int halfHeight = origHeight / 2;
                    final int halfWidth = origWidth / 2;
                    while ((halfHeight / inSampleSize) >= maxDim && (halfWidth / inSampleSize) >= maxDim) {
                        inSampleSize *= 2;
                    }
                }

                BitmapFactory.Options decodeOptions = new BitmapFactory.Options();
                decodeOptions.inSampleSize = inSampleSize;
                decodeOptions.inPreferredConfig = Bitmap.Config.RGB_565; // Saves 50% memory over ARGB_8888

                Bitmap previewBitmap = BitmapFactory.decodeFile(file.getAbsolutePath(), decodeOptions);
                String previewBase64 = "";
                if (previewBitmap != null) {
                    // Final fine resize if needed
                    int currentW = previewBitmap.getWidth();
                    int currentH = previewBitmap.getHeight();
                    int targetW = currentW;
                    int targetH = currentH;
                    if (currentW > maxDim || currentH > maxDim) {
                        float ratio = (float) currentW / (float) currentH;
                        if (ratio > 1) {
                            targetW = maxDim;
                            targetH = (int) (maxDim / ratio);
                        } else {
                            targetH = maxDim;
                            targetW = (int) (maxDim * ratio);
                        }
                        Bitmap scaled = Bitmap.createScaledBitmap(previewBitmap, targetW, targetH, true);
                        if (scaled != previewBitmap) {
                            previewBitmap.recycle();
                            previewBitmap = scaled;
                        }
                    }

                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    previewBitmap.compress(Bitmap.CompressFormat.JPEG, 75, out);
                    previewBase64 = Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP);
                    previewBitmap.recycle();
                }

                // 4. Pass SHA-256, dimensions, preview Base64, AND raw file path to WebView
                String rawFilePathEscaped = file.getAbsolutePath().replace("\\", "\\\\");
                String jsCall = String.format(Locale.US,
                        "if(window.app && window.app.onNativePhotoCaptured){window.app.onNativePhotoCaptured('%s', %d, %d, '%s', '%s', '%s');}",
                        sha256, origWidth, origHeight, source, previewBase64, rawFilePathEscaped);

                evaluateJs(jsCall);

            } catch (Exception e) {
                Log.e(TAG, "Error processing photo file: " + file.getAbsolutePath(), e);
                runOnUiThread(() -> Toast.makeText(MainActivity.this,
                        "Error processing image: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        });
    }

    private void evaluateJs(String js) {
        runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript(js, null);
            }
        });
    }

    public class NativeMediaBridge {
        @JavascriptInterface
        public void openCamera() {
            runOnUiThread(MainActivity.this::launchNativeCamera);
        }

        @JavascriptInterface
        public void openFilePicker() {
            runOnUiThread(MainActivity.this::launchFilePicker);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null) {
            // Let the JS app handle back navigation if modal is open or inside deep wizard
            webView.evaluateJavascript("if(window.app && window.app.handleBackPress){window.app.handleBackPress();} else { false; }",
                    value -> {
                        if ("\"true\"".equals(value) || "true".equals(value)) {
                            // Handled by web app
                            return;
                        }
                        if (webView.canGoBack()) {
                            webView.goBack();
                        } else {
                            super.onBackPressed();
                        }
                    });
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (locationBridge != null) {
            locationBridge.stopLocationUpdates();
        }
        if (connectivityBridge != null) {
            connectivityBridge.onDestroy();
        }
        super.onDestroy();
        backgroundExecutor.shutdown();
    }
}
