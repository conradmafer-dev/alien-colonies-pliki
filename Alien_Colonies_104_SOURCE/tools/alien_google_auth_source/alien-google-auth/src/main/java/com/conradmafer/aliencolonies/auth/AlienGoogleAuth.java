package com.conradmafer.aliencolonies.auth;

import android.app.Activity;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import androidx.credentials.ClearCredentialStateRequest;
import androidx.credentials.Credential;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.ClearCredentialException;
import androidx.credentials.exceptions.GetCredentialCancellationException;
import androidx.credentials.exceptions.GetCredentialException;
import androidx.credentials.exceptions.GetCredentialProviderConfigurationException;
import androidx.credentials.exceptions.GetCredentialUnsupportedException;
import androidx.credentials.exceptions.NoCredentialException;
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;
import org.godotengine.godot.Godot;
import org.godotengine.godot.plugin.GodotPlugin;
import org.godotengine.godot.plugin.UsedByGodot;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Reconstructed from Alien Colonies code 82's DEX, not the original source text.
 * The server must validate each ID token and nonce before authenticating a user.
 */
public final class AlienGoogleAuth extends GodotPlugin {
    private long activeAttempt;
    private CancellationSignal activeCancellation;
    private CancellationSignal clearCancellation;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final NativeSignInMailbox nativeResults = new NativeSignInMailbox();

    public AlienGoogleAuth(Godot godot) {
        super(godot);
    }

    @Override
    public String getPluginName() {
        return "AlienGoogleAuth";
    }

    @UsedByGodot
    public int getGoogleSignInVersion() {
        return 1;
    }

    @UsedByGodot
    public void beginGoogleSignIn(String requestId, String clientId, String nonce) {
        long attempt = nativeResults.begin(requestId != null ? requestId : "");
        if (requestId == null || !requestId.matches("[A-Za-z0-9_-]{16,256}")
                || clientId == null || !clientId.matches("[A-Za-z0-9._-]{1,240}\\.apps\\.googleusercontent\\.com")
                || nonce == null || !nonce.matches("[A-Za-z0-9_-]{16,256}")) {
            nativeResults.complete(attempt, "error", null, "invalid_request");
            cancelInactiveOnMainThread();
            return;
        }
        mainHandler.post(() -> launchOnMainThread(attempt, clientId, nonce));
    }

    private void launchOnMainThread(long attempt, String clientId, String nonce) {
        if (!nativeResults.isActive(attempt)) return;
        if (clearCancellation != null) {
            clearCancellation.cancel();
            clearCancellation = null;
        }
        if (activeCancellation != null) activeCancellation.cancel();
        activeCancellation = null;
        Activity activity = getActivity();
        if (activity == null || activity.isFinishing()) {
            nativeResults.complete(attempt, "error", null, "activity_unavailable");
            return;
        }
        activeAttempt = attempt;
        activeCancellation = new CancellationSignal();
        try {
            GetSignInWithGoogleOption option = new GetSignInWithGoogleOption.Builder(clientId)
                    .setNonce(nonce).build();
            GetCredentialRequest request = new GetCredentialRequest.Builder()
                    .addCredentialOption(option).build();
            CredentialManager.create(activity.getApplicationContext()).getCredentialAsync(
                    activity, request, activeCancellation, runnable -> mainHandler.post(runnable),
                    new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                        @Override
                        public void onResult(GetCredentialResponse response) {
                            if (!nativeResults.isActive(attempt)) return;
                            try {
                                Credential credential = response.getCredential();
                                if (credential instanceof CustomCredential
                                        && GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(credential.getType())) {
                                    String token = GoogleIdTokenCredential.createFrom(credential.getData()).getIdToken();
                                    if (token != null && token.length() >= 32 && token.length() <= 16384) {
                                        nativeResults.complete(attempt, "success", token, null);
                                        releaseCompletedSignal(attempt);
                                        return;
                                    }
                                }
                                nativeResults.complete(attempt, "error", null, "invalid_credential");
                            } catch (Exception ignored) {
                                nativeResults.complete(attempt, "error", null, "invalid_credential");
                            }
                            releaseCompletedSignal(attempt);
                        }

                        @Override
                        public void onError(GetCredentialException error) {
                            String status = "error";
                            String code;
                            if (error instanceof GetCredentialCancellationException) {
                                status = "cancelled";
                                code = "cancelled";
                            } else if (error instanceof NoCredentialException) {
                                code = "no_credential";
                            } else if (error instanceof GetCredentialProviderConfigurationException) {
                                code = "provider_unavailable";
                            } else if (error instanceof GetCredentialUnsupportedException) {
                                code = "unsupported";
                            } else {
                                code = "provider_error";
                            }
                            nativeResults.complete(attempt, status, null, code);
                            releaseCompletedSignal(attempt);
                        }
                    });
        } catch (Exception ignored) {
            nativeResults.complete(attempt, "error", null, "provider_error");
            releaseCompletedSignal(attempt);
        }
    }

    private void releaseCompletedSignal(long attempt) {
        if (activeAttempt == attempt) activeCancellation = null;
    }

    private void cancelInactiveOnMainThread() {
        mainHandler.post(() -> {
            if (activeCancellation != null && !nativeResults.isActive(activeAttempt)) {
                activeCancellation.cancel();
                activeCancellation = null;
            }
        });
    }

    @UsedByGodot
    public void cancelGoogleSignIn() {
        nativeResults.cancel();
        cancelInactiveOnMainThread();
    }

    @UsedByGodot
    public void clearGoogleSignInState() {
        long generation = nativeResults.cancel();
        cancelInactiveOnMainThread();
        mainHandler.post(() -> {
            if (!nativeResults.isGeneration(generation)) return;
            Activity activity = getActivity();
            if (activity == null || activity.isFinishing()) return;
            if (clearCancellation != null) clearCancellation.cancel();
            CancellationSignal clearing = new CancellationSignal();
            clearCancellation = clearing;
            try {
                CredentialManager.create(activity.getApplicationContext()).clearCredentialStateAsync(
                        new ClearCredentialStateRequest(), clearing, runnable -> mainHandler.post(runnable),
                        new CredentialManagerCallback<Void, ClearCredentialException>() {
                            @Override
                            public void onResult(Void result) {
                                releaseClearSignal(clearing);
                            }

                            @Override
                            public void onError(ClearCredentialException error) {
                                releaseClearSignal(clearing);
                            }
                        });
            } catch (Exception ignored) {
                releaseClearSignal(clearing);
            }
        });
    }

    private void releaseClearSignal(CancellationSignal clearing) {
        if (clearCancellation == clearing) clearCancellation = null;
    }

    @UsedByGodot
    public String takePendingGoogleSignIn() {
        NativeSignInMailbox.Result result = nativeResults.take();
        if (result == null) return "";
        try {
            JSONObject json = new JSONObject();
            json.put("request_id", result.requestId);
            json.put("status", result.status);
            if (result.token != null) json.put("id_token", result.token);
            if (result.error != null) json.put("error_code", result.error);
            return json.toString();
        } catch (JSONException ignored) {
            return "";
        }
    }

    @UsedByGodot
    public void setExpectedFlow(String flow) {
        AuthReturnMailbox.setExpectedFlow(flow);
    }

    @UsedByGodot
    public String takePendingReturn() {
        return AuthReturnMailbox.takePendingReturn();
    }

    @Override
    public void onMainDestroy() {
        cancelGoogleSignIn();
        if (clearCancellation != null) {
            clearCancellation.cancel();
            clearCancellation = null;
        }
        super.onMainDestroy();
    }
}
