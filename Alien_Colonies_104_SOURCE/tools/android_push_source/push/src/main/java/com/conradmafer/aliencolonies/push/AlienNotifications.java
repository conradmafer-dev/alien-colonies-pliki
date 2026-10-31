package com.conradmafer.aliencolonies.push;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.os.Build;
import org.godotengine.godot.Godot;
import org.godotengine.godot.plugin.GodotPlugin;
import org.godotengine.godot.plugin.UsedByGodot;

public final class AlienNotifications extends GodotPlugin {
 public AlienNotifications(Godot godot){super(godot);}
 @Override public String getPluginName(){return "AlienNotifications";}
 @UsedByGodot public boolean isAllowed(){return getActivity()!=null&&PushState.allowed(getActivity());}
 @UsedByGodot public void requestPermission(){
  Activity a=getActivity();if(a==null)return;
  if(Build.VERSION.SDK_INT>=33&&!PushState.allowed(a)&&!PushState.prefs(a).getBoolean("prompted",false)){
   PushState.prefs(a).edit().putBoolean("prompted",true).apply();
   a.runOnUiThread(()->a.requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},30590));
  }
 }
 @UsedByGodot public void setActivePlayer(String id){
  Activity a=getActivity();if(a==null)return;
  String old=PushState.prefs(a).getString("active_player","");
  if(!old.equals(id)){
   a.getSystemService(NotificationManager.class).cancelAll();
   PushState.prefs(a).edit().remove("pending_report").apply();
  }
  PushState.prefs(a).edit().putString("active_player",id).apply();
  PushState.channels(a);
 }
 @UsedByGodot public void configure(String json){Activity a=getActivity();if(a!=null)a.runOnUiThread(()->PushState.configure(a,json));}
 @UsedByGodot public String getToken(){return getActivity()==null?"":PushState.prefs(getActivity()).getString("fcm_token","");}
 @UsedByGodot public void showReport(String player,String id,String title,String body,String kind){
  Activity a=getActivity();if(a!=null)PushState.show(a,player,id,title,body,kind);
 }
 @UsedByGodot public String consumeReport(){
  Activity a=getActivity();if(a==null)return "";
  String id=PushState.prefs(a).getString("pending_report","");
  if(!id.isEmpty()){PushState.prefs(a).edit().remove("pending_report").apply();return id;}
  Intent i=a.getIntent();
  if(i!=null&&PushState.prefs(a).getString("active_player","").equals(i.getStringExtra("ac_player_id"))){
   id=i.getStringExtra("ac_report_id");i.removeExtra("ac_report_id");return id==null?"":id;
  }return "";
 }
}
