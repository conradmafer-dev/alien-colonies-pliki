package com.conradmafer.aliencolonies.updates;

import android.app.Activity;
import android.content.Intent;
import com.google.android.play.core.appupdate.AppUpdateInfo;
import com.google.android.play.core.appupdate.AppUpdateManager;
import com.google.android.play.core.appupdate.AppUpdateManagerFactory;
import com.google.android.play.core.appupdate.AppUpdateOptions;
import com.google.android.play.core.install.InstallStateUpdatedListener;
import com.google.android.play.core.install.model.AppUpdateType;
import com.google.android.play.core.install.model.InstallStatus;
import com.google.android.play.core.install.model.UpdateAvailability;
import org.godotengine.godot.Godot;
import org.godotengine.godot.plugin.GodotPlugin;
import org.godotengine.godot.plugin.UsedByGodot;
import org.json.JSONObject;

/** Google Play owns executable delivery, user consent, verification and install. */
public final class AlienUpdates extends GodotPlugin {
    private static final int REQUEST = 30693;
    private AppUpdateManager manager;
    private volatile String snapshot = "{\"state\":\"idle\",\"downloaded\":0,\"total\":0}";
    private boolean querying = false;
    private boolean flowOpen = false;
    private boolean registered = false;
    private final InstallStateUpdatedListener listener = state -> publishInstall(
            state.installStatus(), state.bytesDownloaded(), state.totalBytesToDownload());

    public AlienUpdates(Godot godot) { super(godot); }
    @Override public String getPluginName() { return "AlienUpdates"; }
    @UsedByGodot public String getStatus() { return snapshot; }

    private void publish(String state, long downloaded, long total) {
        try {
            snapshot = new JSONObject().put("state", state)
                    .put("downloaded", downloaded).put("total", total).toString();
        } catch (Exception ignored) { /* All values are finite primitives. */ }
    }
    private boolean init() {
        Activity activity = getActivity();
        if (activity == null) { publish("unsupported", 0, 0); return false; }
        if (manager == null) manager = AppUpdateManagerFactory.create(activity);
        if (!registered) { manager.registerListener(listener); registered = true; }
        return true;
    }
    private void publishInstall(int status, long bytes, long total) {
        switch (status) {
            case InstallStatus.DOWNLOADING: publish("downloading", bytes, total); break;
            case InstallStatus.PENDING: publish("pending", bytes, total); break;
            case InstallStatus.DOWNLOADED: publish("downloaded", bytes, total); break;
            case InstallStatus.INSTALLING: publish("installing", bytes, total); break;
            case InstallStatus.INSTALLED: publish("installed", bytes, total); break;
            case InstallStatus.CANCELED: flowOpen = false; publish("cancelled", bytes, total); break;
            case InstallStatus.FAILED: flowOpen = false; publish("error", bytes, total); break;
        }
    }
    private boolean inProgress(AppUpdateInfo info) {
        int status = info.installStatus();
        if (status == InstallStatus.PENDING || status == InstallStatus.DOWNLOADING
                || status == InstallStatus.DOWNLOADED || status == InstallStatus.INSTALLING) {
            publishInstall(status, info.bytesDownloaded(), info.totalBytesToDownload());
            return true;
        }
        return false;
    }
    @UsedByGodot public void checkUpdate() {
        Activity activity = getActivity();
        if (activity != null) activity.runOnUiThread(() -> query(false));
    }
    @UsedByGodot public void startUpdate() {
        Activity activity = getActivity();
        if (activity != null) activity.runOnUiThread(() -> query(true));
    }
    private void query(boolean start) {
        if (querying || flowOpen || !init()) return;
        querying = true;
        if (start) publish("checking", 0, 0);
        // Never reuse AppUpdateInfo after an attempt: Play permits one flow per instance.
        manager.getAppUpdateInfo().addOnSuccessListener(info -> {
            querying = false;
            if (info.updateAvailability() == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS) {
                launch(info, AppUpdateType.IMMEDIATE);
                return;
            }
            if (inProgress(info)) return;
            if (info.updateAvailability() != UpdateAvailability.UPDATE_AVAILABLE) {
                publish("unavailable", 0, 0);
                return;
            }
            int type = info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE) ? AppUpdateType.FLEXIBLE
                    : info.isUpdateTypeAllowed(AppUpdateType.IMMEDIATE) ? AppUpdateType.IMMEDIATE : -1;
            if (type < 0) { publish("unsupported", 0, 0); return; }
            if (start) launch(info, type); else publish("available", 0, 0);
        }).addOnFailureListener(error -> {
            querying = false;
            publish("error", 0, 0);
        });
    }
    private void launch(AppUpdateInfo info, int type) {
        Activity activity = getActivity();
        if (activity == null) { publish("error", 0, 0); return; }
        try {
            flowOpen = true;
            publish("consent", 0, 0);
            if (!manager.startUpdateFlowForResult(info, activity,
                    AppUpdateOptions.newBuilder(type).build(), REQUEST)) {
                flowOpen = false;
                publish("error", 0, 0);
            }
        } catch (Exception error) { flowOpen = false; publish("error", 0, 0); }
    }
    @UsedByGodot public void completeUpdate() {
        Activity activity = getActivity();
        if (activity == null) return;
        activity.runOnUiThread(() -> {
            if (!init()) return;
            manager.getAppUpdateInfo().addOnSuccessListener(info -> {
                if (info.installStatus() != InstallStatus.DOWNLOADED) { inProgress(info); return; }
                publish("installing", info.bytesDownloaded(), info.totalBytesToDownload());
                manager.completeUpdate().addOnFailureListener(error -> publish("downloaded", info.bytesDownloaded(), info.totalBytesToDownload()));
            }).addOnFailureListener(error -> publish("error", 0, 0));
        });
    }
    @Override public void onMainActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != REQUEST) return;
        flowOpen = false;
        if (resultCode == Activity.RESULT_OK) query(false);
        else publish(resultCode == Activity.RESULT_CANCELED ? "cancelled" : "error", 0, 0);
    }
    @Override public void onMainResume() {
        flowOpen = false;
        checkUpdate();
    }
    @Override public void onMainDestroy() {
        if (manager != null && registered) manager.unregisterListener(listener);
        registered = false;
    }
}
