package com.conradmafer.aliencolonies.push;
import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
public final class ReportOpenActivity extends Activity {
 @Override protected void onCreate(Bundle saved) {
  super.onCreate(saved);
  Intent intent=getIntent();
  if(intent!=null&&PushState.prefs(this).getString("active_player","").equals(intent.getStringExtra("ac_player_id"))) {
   String report=intent.getStringExtra("ac_report_id");
   if(report!=null)PushState.prefs(this).edit().putString("pending_report",report).commit();
  }
  Intent launch=getPackageManager().getLaunchIntentForPackage(getPackageName());
  if(launch!=null){launch.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);startActivity(launch);}
  finish();
 }
}
