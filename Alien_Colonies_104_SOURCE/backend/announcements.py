"""Server-managed public login announcement and password-protected draft editor.

All records live inside the existing SQLite world snapshot; no separate database
and no client update are needed to publish/change/hide a bulletin. Public readers
never receive drafts. All text must be rendered as text, not HTML.
"""
from __future__ import annotations

import hmac
import math
import os
import time

MAX_TITLE = 100
MAX_BODY = 1600
ONLINE_WINDOW_SECONDS = 60
CATEGORIES = frozenset(("", "news", "event", "maintenance", "update"))


def _empty_draft():
    return {"category": "news", "title": "", "body": ""}


def _record(world):
    row = world.data.get("login_announcement")
    return row if isinstance(row, dict) else {}


def _validate_draft(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid announcement")
    category, title, body = value.get("category", "news"), value.get("title", ""), value.get("body", "")
    if category not in CATEGORIES or not isinstance(title, str) or not isinstance(body, str):
        raise ValueError("Invalid announcement content")
    title, body = title.strip(), body.strip()
    if len(title) > MAX_TITLE or len(body) > MAX_BODY or "\x00" in title + body:
        raise ValueError("Announcement too long")
    return {"category": category, "title": title, "body": body}


def public(world):
    with world.lock:
        published = _record(world).get("published")
        if not isinstance(published, dict):
            return {"ok": True, "visible": False}
        return {"ok": True, "visible": True,
                "announcement": {key: published[key] for key in ("title", "body", "category")},
                "revision": int(_record(world).get("revision", 0))}


def enabled():
    key = os.environ.get("ALIEN_ANNOUNCEMENT_ADMIN_KEY", "")
    return isinstance(key, str) and len(key) >= 24


def authorized(value):
    configured = os.environ.get("ALIEN_ANNOUNCEMENT_ADMIN_KEY", "")
    if not isinstance(value, str) or not isinstance(configured, str) or len(configured) < 24:
        return False
    if len(value) > 512:
        return False
    return hmac.compare_digest(value, configured)


def editor(world):
    with world.lock:
        row = _record(world)
        return {"ok": True, "draft": dict(row.get("draft") or _empty_draft()),
                "published": dict(row["published"]) if isinstance(row.get("published"), dict) else None,
                "revision": int(row.get("revision", 0)),
                "updated_at": float(row.get("updated_at", 0))}



def activity_stats(world, *, at=None):
    """Count unique existing empires by their last verified activity timestamp.

    The client foreground activity marker, authenticated sign-ins and successful
    actions update last_active_at. Passive world polling does not. This view is
    read-only and must only be reachable through the authenticated admin API.
    """
    now = time.time() if at is None else float(at)
    with world.lock:
        players = world.data["players"]
        timestamps = []
        for player in players.values():
            raw = player.get("last_active_at") if isinstance(player, dict) else None
            if type(raw) not in (int, float):
                continue
            last = float(raw)
            if math.isfinite(last) and 0 < last <= now:
                timestamps.append(last)
        # ONLINE is separate from gameplay activity. Polling never changes last_active_at.
        # Presence is ephemeral, so it resets after a server restart.
        clock = time.monotonic()
        presence = world._state_poll_presence
        for player_id, seen_at in tuple(presence.items()):
            if (player_id not in players or type(seen_at) not in (int, float)
                    or not math.isfinite(seen_at)
                    or not 0 <= clock - seen_at <= ONLINE_WINDOW_SECONDS):
                del presence[player_id]
        return {
            "ok": True,
            "online_60s": len(presence),
            "online_window_seconds": ONLINE_WINDOW_SECONDS,
            "active_24h": sum(last >= now - 86400 for last in timestamps),
            "active_48h": sum(last >= now - 2 * 86400 for last in timestamps),
            "active_72h": sum(last >= now - 3 * 86400 for last in timestamps),
            "active_7d": sum(last >= now - 7 * 86400 for last in timestamps),
            "active_30d": sum(last >= now - 30 * 86400 for last in timestamps),
            "total_players": len(players),
            "as_of": int(now),
        }


def update(world, payload):
    """Atomic edit with optimistic revision to avoid one tab overwriting another."""
    if not isinstance(payload, dict) or payload.get("action") not in ("save", "publish", "hide"):
        raise ValueError("Unknown announcement action")
    expected = payload.get("revision")
    if type(expected) is not int or expected < 0:
        raise ValueError("Revision is required")
    with world._atomic():
        previous = _record(world)
        revision = int(previous.get("revision", 0))
        if expected != revision:
            raise RuntimeError("The announcement was changed in another tab. Reload before saving.")
        row = dict(previous)
        action = payload["action"]
        if action in ("save", "publish"):
            draft = _validate_draft(payload.get("draft"))
            if action == "publish" and not draft["title"]:
                raise ValueError("A published announcement needs a title")
            row["draft"] = draft
            if action == "publish":
                row["published"] = dict(draft)
        else:
            row["published"] = None
        row["revision"] = revision + 1
        row["updated_at"] = time.time()
        world.data["login_announcement"] = row
    return editor(world)


# Rendered only as a standalone first-party HTML page, never into the Android app.
# The existing HTTP handler adds no-frame, no-referrer and restrictive CSP headers.
EDITOR_HTML = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Ogłoszenia — Alien Colonies</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif;--cyan:#67d9f9;--muted:#9cb6c7}
*{box-sizing:border-box}body{margin:0;color:#e9f6ff;background:radial-gradient(ellipse at 50% -20%,#173d5d,transparent 65%),#060c14;min-height:100vh}
main{width:min(760px,calc(100% - 30px));margin:48px auto 80px}header{text-align:center;padding-bottom:16px}
.kicker{letter-spacing:.24em;color:var(--cyan);font-size:.74rem;font-weight:800}h1{font-size:clamp(1.7rem,5vw,2.7rem);margin:.3rem 0}
.desc,.muted{color:var(--muted);line-height:1.5}.card{margin:16px 0;padding:25px;border:1px solid #35789a;border-radius:18px;background:#071725ee;box-shadow:0 12px 60px #0008}
label{display:block;margin:14px 0 7px;font-weight:650}input,textarea,select{width:100%;padding:13px;color:#e9f6ff;background:#06111b;border:1px solid #44738b;border-radius:10px;font:inherit}
textarea{resize:vertical;min-height:150px;line-height:1.55}input:focus,textarea:focus,select:focus{outline:2px solid #47cbed}
.row{display:flex;gap:12px;flex-wrap:wrap}button{border:1px solid #407997;border-radius:10px;padding:12px 17px;background:#12364c;color:white;font-weight:700;cursor:pointer;min-height:45px}
button.primary{background:linear-gradient(105deg,#00a1de,#35cbd4);color:#00233b;border-color:#4edfee}
button.danger{border-color:#8c5364;background:#34202f}button:hover{filter:brightness(1.18)}
#editor,#preview{display:none}#status{min-height:23px}#status.error{color:#ffaeaf}
.stats-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:18px 0}
.stat{padding:16px;border:1px solid #33586c;border-radius:12px;background:#081d2b}
.stat strong{display:block;font-size:clamp(1.75rem,4vw,2.35rem);line-height:1.15;color:#b5f4ff;font-variant-numeric:tabular-nums}
.stat span{display:block;color:var(--muted);font-size:.83rem;margin-top:8px}
@media(min-width:650px){.stats-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.preview{padding:20px;border:1px solid #4e96b3;border-radius:16px;background:#081b28;white-space:pre-wrap;overflow-wrap:anywhere}
#preview-title{font-size:1.2rem;font-weight:800}small{color:#a5bdcb}
</style></head><body>
<main><header><div class="kicker">ALIEN COLONIES · PANEL ADMINISTRATORA</div><h1>Komunikat na ekranie logowania</h1>
<p class="desc">Zapisuj szkice, publikuj wiadomości i wyłączaj je w każdej chwili — bez aktualizacji Androida.</p></header>
<section class="card" id="login"><label for="password">Klucz administratora</label>
<input id="password" type="password" autocomplete="off" spellcheck="false" placeholder="Wklej klucz z konfiguracji serwera">
<div class="row" style="margin-top:16px"><button class="primary" id="unlock">Otwórz edytor</button></div></section>
<section class="card" id="editor"><div class="kicker">EDYCJA OGŁOSZENIA</div>
<label for="category">Rodzaj wiadomości</label><select id="category">
<option value="">Bez kategorii</option><option value="news">Aktualność</option><option value="update">Aktualizacja gry</option>
<option value="event">Wydarzenie</option><option value="maintenance">Przerwa techniczna</option></select>
<label for="title">Nagłówek (maks. 100 znaków)</label><input id="title" maxlength="100" placeholder="Np. Nowa galaktyka już dostępna">
<label for="body">Treść (maks. 1600 znaków)</label>
<textarea id="body" maxlength="1600" placeholder="Wiadomość widoczna nad logowaniem po opublikowaniu..."></textarea>
<p class="muted" id="publication"></p><div class="row">
<button id="save">Zapisz szkic</button><button class="primary" id="publish">Publikuj</button>
<button class="danger" id="hide">Ukryj komunikat</button><button id="logout">Zablokuj edytor</button></div>
<p class="muted">Szkic pozostaje na serwerze także po ukryciu komunikatu. Gracze widzą wyłącznie opublikowaną wersję.</p></section>
<section id="stats" class="card" hidden>
<div class="row" style="align-items:center;justify-content:space-between">
<div><div class="kicker">AKTYWNOŚĆ GRACZY</div><p class="muted">Unikalne konta, których ostatnia aktywność przypada na wybrany okres.</p></div>
<button id="refresh-stats" type="button">Odśwież</button></div>
<div class="stat" style="margin-top:16px"><strong id="stats-online">–</strong><span>Online teraz · połączenie w ostatnich 60 sekundach</span></div>
<div class="stats-grid">
<div class="stat"><strong id="stats-24h">–</strong><span>Ostatnie 24 godziny</span></div>
<div class="stat"><strong id="stats-48h">–</strong><span>Ostatnie 48 godzin</span></div>
<div class="stat"><strong id="stats-72h">–</strong><span>Ostatnie 72 godziny</span></div>
<div class="stat"><strong id="stats-7d">–</strong><span>Ostatnie 7 dni</span></div>
<div class="stat"><strong id="stats-30d">–</strong><span>Ostatnie 30 dni</span></div>
<div class="stat"><strong id="stats-total">–</strong><span>Wszystkie imperia</span></div></div>
<p class="muted" id="stats-status" aria-live="polite"></p></section>
<section id="preview" class="card"><div class="kicker">PODGLĄD OPUBLIKOWANEJ WIADOMOŚCI</div>
<div class="preview"><div id="preview-category" class="kicker"></div><p id="preview-title"></p><div id="preview-body"></div></div></section>
<p id="status" aria-live="polite"></p><p class="muted"><small>Wiadomości są zwykłym tekstem. Wprowadzona treść nie może wykonywać kodu ani HTML.</small></p>
</main><script>
'use strict';
let key = '', revision=0;
const $ = id => document.getElementById(id);
const setStatus = (value,error=false) => { $('status').textContent=value; $('status').className=error?'error':''; };
function draft(){return {category:$('category').value,title:$('title').value,body:$('body').value};}
function render(data){
 revision=data.revision;
 const d=data.draft||{};
 $('category').value=d.category??'news'; $('title').value=d.title||''; $('body').value=d.body||'';
 const p=data.published;
 $('publication').textContent=p?'Komunikat jest opublikowany · Wersja '+revision:'Brak opublikowanego komunikatu · Szkic jest zachowany';
 $('preview').style.display=p?'block':'none';
 if(p){$('preview-category').hidden=!p.category; $('preview-category').textContent= p.category ? (({news:'AKTUALNOŚĆ',update:'AKTUALIZACJA',event:'WYDARZENIE',maintenance:'PRZERWA TECHNICZNA'})[p.category]||'OGŁOSZENIE') : '';
 $('preview-title').textContent=p.title; $('preview-body').textContent=p.body;}
}
async function api(method,payload,endpoint='/api/admin/announcement'){
 const r=await fetch(endpoint,{method,headers:{'X-AC-Announcement-Key':key,'Content-Type':'application/json'},
 body:payload?JSON.stringify(payload):undefined,cache:'no-store',credentials:'omit'});
 let data={};try{data=await r.json();}catch(e){}
 if(!r.ok)throw new Error(data.error||'Błąd '+r.status);
 return data;
}
async function refreshStats(){
 $('stats-status').textContent='Wczytuję statystyki...';
 try{
   const data=await api('GET',undefined,'/api/admin/stats');
   if(!key || $('stats').hidden)return;
   const format=value=>Number(value).toLocaleString('pl-PL');
   $('stats-online').textContent=format(data.online_60s);
   $('stats-24h').textContent=format(data.active_24h);
   $('stats-48h').textContent=format(data.active_48h);
   $('stats-72h').textContent=format(data.active_72h);
   $('stats-7d').textContent=format(data.active_7d);
   $('stats-30d').textContent=format(data.active_30d);
   $('stats-total').textContent=format(data.total_players);
   $('stats-status').textContent='Stan na '+new Date(Number(data.as_of)*1000).toLocaleString('pl-PL')+' · Online: połączenia z ostatniej minuty. Pozostałe statystyki: rzeczywista aktywność.';
 }catch(e){if(key && !$('stats').hidden)$('stats-status').textContent='Nie udało się pobrać statystyk: '+e.message;}
}
$('refresh-stats').onclick=refreshStats;
$('unlock').onclick=async()=>{
 key=$('password').value;setStatus('Sprawdzam dostęp...');
 try {render(await api('GET'));$('password').value='';$('login').style.display='none';$('editor').style.display='block';$('stats').hidden=false;refreshStats();setStatus('Możesz edytować wiadomość.');}
 catch(e){key='';setStatus(e.message,true);}
};
$('password').addEventListener('keydown',e=>{if(e.key==='Enter')$('unlock').click()});
for(const action of ['save','publish','hide']) $(''+action).onclick=async()=>{
 setStatus('Zapisuję...');
 try{render(await api('POST',{action,revision,draft:draft()}));
 setStatus(action==='publish'?'Opublikowano — gracze zobaczą komunikat na logowaniu.':action==='hide'?'Komunikat ukryty. Szkic zachowany.':'Szkic zapisany na serwerze.');}
 catch(e){setStatus(e.message,true);}
};
$('logout').onclick=()=>{key='';$('editor').style.display='none';$('preview').style.display='none';$('stats').hidden=true;$('login').style.display='block';setStatus('Edytor zablokowany.');};
</script></body></html>"""

