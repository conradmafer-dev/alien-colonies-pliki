package com.conradmafer.aliencolonies.push;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
public final class PushInitProvider extends ContentProvider {
 @Override public boolean onCreate(){if(getContext()!=null)PushState.restore(getContext());return true;}
 @Override public Cursor query(Uri u,String[]p,String s,String[]a,String o){return null;}
 @Override public String getType(Uri u){return null;}
 @Override public Uri insert(Uri u,ContentValues v){return null;}
 @Override public int delete(Uri u,String s,String[]a){return 0;}
 @Override public int update(Uri u,ContentValues v,String s,String[]a){return 0;}
}

