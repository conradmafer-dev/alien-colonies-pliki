package com.conradmafer.aliencolonies.auth;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.os.Bundle;

/** Browser redirect receiver, reconstructed from the code 82 DEX. */
public final class GoogleAuthReturnActivity extends Activity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        receive(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        receive(intent);
    }

    private void receive(Intent intent) {
        if (intent != null && Intent.ACTION_VIEW.equals(intent.getAction())) {
            AuthReturnMailbox.accept(intent.getDataString());
        }
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        try {
            if (launch != null) {
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
                startActivity(launch);
            }
        } catch (ActivityNotFoundException ignored) {
        }
        finish();
    }
}
