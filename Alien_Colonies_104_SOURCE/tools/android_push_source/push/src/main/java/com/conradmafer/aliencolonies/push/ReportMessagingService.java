package com.conradmafer.aliencolonies.push;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
import java.util.Map;
public final class ReportMessagingService extends FirebaseMessagingService {
 @Override public void onNewToken(String token){PushState.prefs(this).edit().putString("fcm_token",token).apply();}
 @Override public void onMessageReceived(RemoteMessage message){
  Map<String,String>d=message.getData();
  PushState.show(this,d.getOrDefault("player_id",""),d.getOrDefault("report_id",""),
   d.getOrDefault("title","Alien Colonies"),d.getOrDefault("body",""),d.getOrDefault("kind","report"));
 }
}

