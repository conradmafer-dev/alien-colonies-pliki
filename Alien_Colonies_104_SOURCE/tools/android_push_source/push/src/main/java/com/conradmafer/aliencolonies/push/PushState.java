package com.conradmafer.aliencolonies.push;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Build;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import com.google.firebase.messaging.FirebaseMessaging;
import org.json.JSONArray;
import org.json.JSONObject;

public final class PushState {
 static android.content.SharedPreferences prefs(Context c) { return c.getSharedPreferences("alien_report_notifications",Context.MODE_PRIVATE); }
 static boolean allowed(Context c) { return Build.VERSION.SDK_INT<33 || c.checkSelfPermission("android.permission.POST_NOTIFICATIONS")==PackageManager.PERMISSION_GRANTED; }
 static void channels(Context c) {
  if(Build.VERSION.SDK_INT>=26) {
   NotificationManager n=c.getSystemService(NotificationManager.class);
   n.createNotificationChannel(new NotificationChannel("alien_reports","Alien Colonies",NotificationManager.IMPORTANCE_DEFAULT));
   n.createNotificationChannel(new NotificationChannel("alien_attacks","Alien Colonies — attacks",NotificationManager.IMPORTANCE_HIGH));
  }
 }
 static synchronized void restore(Context c) {
  try {
   String saved=prefs(c).getString("firebase_config","");
   if(saved.isEmpty())return;
   JSONObject o=new JSONObject(saved);
   if(FirebaseApp.getApps(c).isEmpty())FirebaseApp.initializeApp(c,new FirebaseOptions.Builder()
     .setApplicationId(o.getString("app_id")).setApiKey(o.getString("api_key"))
     .setGcmSenderId(o.getString("sender_id")).setProjectId(o.getString("project_id")).build());
  } catch(Exception ignored) { }
 }
 static synchronized void configure(Context c,String json) {
  if(!allowed(c))return;
  try {
   JSONObject o=new JSONObject(json);
   if(!o.optBoolean("configured",false))return;
   for(String key:new String[]{"project_id","sender_id","app_id","api_key"})if(o.optString(key).isEmpty())return;
   prefs(c).edit().putString("firebase_config",o.toString()).apply();
   restore(c);
   FirebaseMessaging.getInstance().setAutoInitEnabled(true);
   FirebaseMessaging.getInstance().getToken().addOnSuccessListener(token->prefs(c).edit().putString("fcm_token",token).apply());
  } catch(Exception ignored) { }
 }
 static synchronized void show(Context c,String player,String id,String title,String body,String kind) {
  if(!allowed(c)||player.isEmpty()||id.isEmpty()||!player.equals(prefs(c).getString("active_player","")))return;
  try {
   String key=player+":"+id;
   JSONArray old=new JSONArray(prefs(c).getString("seen","[]"));
   for(int i=0;i<old.length();i++)if(key.equals(old.optString(i)))return;
   JSONArray seen=new JSONArray();for(int i=Math.max(0,old.length()-127);i<old.length();i++)seen.put(old.getString(i));
   seen.put(key);prefs(c).edit().putString("seen",seen.toString()).commit();
   channels(c);
   Intent launch=new Intent(c,ReportOpenActivity.class);
   if(launch==null)return;
   launch.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
   launch.setAction("alien.report."+id);launch.putExtra("ac_report_id",id);launch.putExtra("ac_player_id",player);
   PendingIntent pending=PendingIntent.getActivity(c,key.hashCode(),launch,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
   String channel="attack".equals(kind)?"alien_attacks":"alien_reports";
   Notification.Builder builder=Build.VERSION.SDK_INT>=26?new Notification.Builder(c,channel):new Notification.Builder(c);
   builder.setSmallIcon(R.drawable.ic_stat_alien_report).setContentTitle(title).setContentText(body)
    .setStyle(new Notification.BigTextStyle().bigText(body)).setContentIntent(pending).setAutoCancel(true)
    .setGroup("alien_reports").setVisibility(Notification.VISIBILITY_PRIVATE)
    .setCategory("attack".equals(kind)?Notification.CATEGORY_ALARM:Notification.CATEGORY_EVENT);
   if(Build.VERSION.SDK_INT<26)builder.setPriority("attack".equals(kind)?Notification.PRIORITY_HIGH:Notification.PRIORITY_DEFAULT).setDefaults(Notification.DEFAULT_ALL);
   c.getSystemService(NotificationManager.class).notify(key,1,builder.build());
  } catch(Exception ignored) { }
 }
}

