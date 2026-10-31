#!/usr/bin/env python3
"""Pogranicze Galaktyki: authoritative, dependency-free multiplayer test server."""
from __future__ import annotations

try:
    from .i18n import t, join_text, language_scope, store_text, render_text, public_report, format_number
    from . import report_kinds
except ImportError:  # Flat Railway deployment.
    from i18n import t, join_text, language_scope, store_text, render_text, public_report, format_number
    import report_kinds

import argparse
import copy
import hashlib
import hmac
import ipaddress
import json
import math
import os
import re
import secrets
import signal
import sqlite3
import threading
import time
import unicodedata
from collections import defaultdict, deque
from contextlib import contextmanager
from functools import wraps
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

try:  # Both `python -m server.main` and Railway's direct app.py import work.
    from . import fleet_expansion, fleet_balance85, flight_balance85, catalog_descriptions, economy85, galaxy_topology, push_notifications, rankings, expeditions
    from .races import NEUTRAL_RULES, RACES, UNIQUE_BUILDINGS, UNIQUE_RESEARCH, SHIP_REQUIREMENTS, SHIP_TRAITS, art_key, public_race, building_effect_value, unique_effect_text, research_effect_text
    from . import skill_tree, swarm, onboarding, defenses, production_timing, planetary, battle_replay, planet_traits, ogame_economy, announcements, review_invite, subscription_invite
    from .expeditions import ExpeditionMixin
    from .accounts import AccountManagementMixin
    from .inactivity import InactivityMixin, ACTIVITY_HEADER
    from .beginner_protection import BeginnerProtectionMixin, PROTECTION_SECONDS, PROTECTION_DURATION_VERSION
    from .communications import CommunicationsMixin
    from .planned_queues import PlannedQueuesMixin
    from .play_billing import BillingVerifier, BillingError
    from .google_signin import GoogleAccountMixin, GoogleSignInService, GoogleSignInError, serve_google_browser
    from .email_signin import EmailAccountMixin, EmailSignInService, EmailSignInError, handle_email_api, serve_email_browser
    from .backups import SQLiteBackups
    from .balance_reset import BalanceResetMixin, BALANCE_RESET_ID, verified_reset_backup
    from .swarm_reset import SwarmResetMixin
    from .launch_reset import LaunchResetMixin, LAUNCH_RESET_ID
    from .swarm_ai import SwarmAIMixin
    from .intelligence import IntelligenceMixin
except ImportError:
    import fleet_expansion, fleet_balance85, flight_balance85, catalog_descriptions, economy85, galaxy_topology, push_notifications, rankings, expeditions
    from races import NEUTRAL_RULES, RACES, UNIQUE_BUILDINGS, UNIQUE_RESEARCH, SHIP_REQUIREMENTS, SHIP_TRAITS, art_key, public_race, building_effect_value, unique_effect_text, research_effect_text
    import skill_tree, swarm, onboarding, defenses, production_timing, planetary, battle_replay, planet_traits, ogame_economy, announcements, review_invite, subscription_invite
    from expeditions import ExpeditionMixin
    from accounts import AccountManagementMixin
    from inactivity import InactivityMixin, ACTIVITY_HEADER
    from beginner_protection import BeginnerProtectionMixin, PROTECTION_SECONDS, PROTECTION_DURATION_VERSION
    from communications import CommunicationsMixin
    from planned_queues import PlannedQueuesMixin
    from play_billing import BillingVerifier, BillingError
    from google_signin import GoogleAccountMixin, GoogleSignInService, GoogleSignInError, serve_google_browser
    from email_signin import EmailAccountMixin, EmailSignInService, EmailSignInError, handle_email_api, serve_email_browser
    from backups import SQLiteBackups
    from balance_reset import BalanceResetMixin, BALANCE_RESET_ID, verified_reset_backup
    from swarm_reset import SwarmResetMixin
    from launch_reset import LaunchResetMixin, LAUNCH_RESET_ID
    from swarm_ai import SwarmAIMixin
    from intelligence import IntelligenceMixin

VERSION = "0.12.37"
UPDATE_DEFAULT_VERSION = "0.12.25"
CLIENT_VERSION_CODE = 88
ECONOMY_MULTIPLIER = 0.1
# A small planetary energy reserve powers a first mine before an energy plant
# exists. It creates no metal, crystal or fuel on its own.
STARTER_ENERGY_SUPPLY = 40
MAX_VERSION_CODE = 2_100_000_000
MAX_APK_SIZE_BYTES = 268_435_456
RESOURCES = ("metal", "crystal", "fuel")
BUILDINGS = {
    "expedition_base": expeditions.SPEC,
    "observatory": planetary.OBSERVATORY_SPEC,
    "metal_mine": ("Kopalnia metalu", "Metal do budowy imperium.", (200, 70, 0), 120),
    "crystal_mine": ("Kopalnia kryształów", "Kryształy do badań i elektroniki.", (150, 110, 0), 150),
    "refinery": ("Rafineria", "Paliwo dla twoich flot.", (220, 130, 0), 180),
    "power_plant": ("Elektrownia", "Energia zasila wydobycie.", (180, 80, 0), 120),
    "shipyard": ("Stocznia", "Buduje statki. Poziom 2 odblokowuje krążownik.", (400, 230, 80), 240),
    "lab": ("Laboratorium", "Pozwala ulepszać napęd i uzbrojenie.", (350, 280, 80), 240),
}
RESEARCH = {
    "propulsion": ("Napęd", "Każdy poziom przyspiesza podróże o 15%.", (350, 400, 200), 240),
    "weapons": ("Uzbrojenie", "Każdy poziom zwiększa siłę ataku o 10%.", (500, 300, 150), 240),
}
SHIPS = {
    # name, description, cost, build seconds, attack, hull, hold, fuel, speed
    "scout": ("Zwiadowca", "Odkrywa zasoby i obronę planety.", (100, 100, 30), 60, 2, 15, 10, 1, 1.8),
    "cargo": ("Transportowiec", "Przewozi zapasy i zdobycz.", (250, 150, 60), 120, 3, 50, 1500, 3, 1.0),
    "colonizer": ("Kolonizator", "Zakłada kolonię na wolnej planecie.", (1600, 1000, 400), 420, 2, 90, 600, 8, 0.8),
    "frigate": ("Fregata", "Podstawowy okręt bojowy.", (350, 180, 80), 150, 28, 95, 80, 3, 1.2),
    "cruiser": ("Krążownik", "Ciężki okręt do przełamywania obrony.", (1200, 750, 250), 360, 90, 320, 220, 9, 0.85),
    "interceptor": ("Przechwytywacz", "Szybki okręt do błyskawicznych wypraw bojowych.", (700, 450, 200), 270, 58, 170, 50, 5, 2.0),
    "siege": ("Okręt oblężniczy", "Ciężki okręt; jego atak przeciw broniącemu się Rojowi jest o 50% silniejszy.", (3600, 2400, 900), 900, 210, 850, 350, 22, 0.65),
    "freighter": ("Frachtowiec", "Ogromna ładownia do transportu zapasów i łupów.", (1700, 1100, 350), 540, 8, 360, 6500, 8, 0.75),
}
SHIPS.update(fleet_expansion.NEUTRAL_SHIPS)
SYSTEM_NAMES = ["Helios", "Vega", "Orion", "Lyra", "Nadir", "Aster", "Talos", "Iris", "Atlas", "Selene", "Draco", "Aurora", "Kronos", "Eos", "Polaris", "Mira", "Nexus", "Arden", "Ereb", "Cygnus", "Boreas", "Zefir", "Tytan", "Perseusz", "Arka", "Solara", "Kepler", "Andara", "Vesper", "Rubież"]
MAX_RESOURCE = ogame_economy.RESOURCE_LIMIT
MAX_BODY = 16_384
MAX_COLONIES = 12
COLONIZATION_WARNING = 'Uwaga: przy braku floty, obrony planetarnej i wsparcia sojuszników dodatkowa kolonia może zostać przejęta przez inną cywilizację. Planeta macierzysta jest chroniona przed przejęciem.'
WELCOME_REPORT_TEXT = 'Rozwijaj kolonię, badania i flotę swojej rasy. Przed wyprawą po Kryształy Roju zbadaj obronę gniazda. Możesz zniszczyć przyczółki Roju: pokonaj całą ich flotę i obronę, zachowując przynajmniej jeden atakujący statek. Uwolnioną planetę można zasiedlić kolonizatorem. Główny ul każdej galaktyki przetrwa atak, zachowa budynki i odbuduje flotę z własnych zasobów; jego planety nie można skolonizować. Zniszczenie przyczółka daje do 3 dodatkowych Kryształów Roju, zależnie od miejsca w ładowniach. W ataku sojuszniczym jest to jedna wspólna premia. Łup i premię otrzymasz po powrocie ocalałej floty. Rój czasem napada po zwykłe surowce; ochrona nowych graczy trwa 3 dni. Zwykłe kryształy służą gospodarce, a rzadkie Kryształy Roju — umiejętnościom w kole.'
LEGACY_WELCOME_REPORT_TEXT = WELCOME_REPORT_TEXT.replace('ochrona nowych graczy trwa 3 dni.', 'ochrona nowych graczy trwa 24 godziny.', 1)

PRIVACY_HTML = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="robots" content="index,follow">\n<title>Alien Colonies — Privacy Policy / Polityka prywatności</title>\n<style>\n:root{color-scheme:dark;background:#07110d;color:#e7f3ea;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}body{margin:0;background:#07110d}main{max-width:920px;margin:auto;padding:32px 20px 64px}.card{background:#0d2118;border:1px solid #254638;border-radius:18px;padding:24px;margin:18px 0}h1{font-size:2rem;margin:.2em 0}.muted{color:#a9bdb1}h2{color:#bce9c7;margin-top:1.4em}h3{color:#d8eadc}a{color:#8fd7a1}code{background:#08150f;padding:.15em .35em;border-radius:5px}li{margin:.45em 0;line-height:1.55}p{line-height:1.6}.pill{display:inline-block;background:#18382a;border:1px solid #2c5a43;border-radius:999px;padding:6px 10px;margin-right:7px}.lang{margin-top:12px}.warning{border-left:4px solid #d6a85f;padding-left:14px}</style>\n</head>\n<body><main>\n<div class="card">\n<h1>Alien Colonies — Privacy Policy</h1>\n<p class="muted">Effective date: 23 October 2026</p>\n<p><span class="pill">Android game</span><span class="pill">Multiplayer backend</span></p>\n<p>Operator: the developer of <strong>Alien Colonies</strong>. Privacy contact: <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n<p>This policy explains how Alien Colonies processes information when you use the Android game, its multiplayer server and the public account/privacy pages hosted with the service.</p>\n\n<h2>1. Information processed in the current account system</h2>\n<ul>\n<li><strong>Empire/account name.</strong> It is used to identify the account and can be visible to other players in the galaxy and in multiplayer reports. Do not use sensitive real-world information as your empire name.</li>\n<li><strong>Authentication data.</strong> The server stores a salted password hash, not the plain-text password. Session tokens are stored as cryptographic hashes with expiry times. If you create a recovery code, only its hash is retained after it is shown to you.</li>\n<li><strong>Sign-in options.</strong> Where enabled, new empires use Google verification or a one-use email sign-in link. Existing password accounts retain their credentials. Email sign-in does not automatically link an existing Google or password account.</li>\n<li><strong>Gameplay and save data.</strong> This includes your race, planets, resources, buildings, research, ships, fleets, skill progression, protection timers, reports, actions and other information needed to maintain your multiplayer empire.</li>\n<li><strong>Player communications.</strong> The server stores chat text, sender/recipient account identifiers, timestamps, read positions, blocks and abuse reports. Global chat is visible to logged-in players; direct messages are available through the game only to their participants. The operator can review reported messages for moderation. Chat history is available for up to 30 days, with up to 1,000 messages in global chat; expired records are removed when another message is sent. Deleting an account removes its sent messages and private conversations from the active database. Copies can remain temporarily in rotating backups.</li>\n<li><strong>Technical connection data.</strong> An IP address and request metadata are necessarily processed to deliver network traffic, apply rate limits and protect the service from abuse. The game server is designed not to write passwords, bearer tokens, request bodies or full query strings to its own request logs. Hosting and network providers may process ordinary infrastructure metadata as part of operating the service.</li>\n</ul>\n\n<h2>Queue subscriptions</h2>\n<p>Google Play processes subscription payments. To verify access, renewals and changes in payment status, the game server retains the purchase token, a pseudonymous game-account identifier, the product and plan identifiers, verification status and paid-period timestamps. These records are not shown to other players. Alien Colonies does not receive your card details. Records are retained with your game account and are removed from the active database when the account is deleted; copies may remain temporarily in rotating backups. You can manage or cancel the subscription through Google Play.</p>\n\n<h2>2. Why the data is used</h2>\n<ul>\n<li>to create, authenticate and recover accounts;</li>\n<li>to keep the multiplayer galaxy and your progress synchronized;</li>\n<li>to provide game reports, combat, trading/transport and other multiplayer features;</li>\n<li>to prevent abuse, excessive requests and unauthorized account access;</li>\n<li>to maintain backups, diagnose service failures and keep the service secure;</li>\n<li>to comply with applicable legal obligations.</li>\n</ul>\n\n<h2>3. Service providers and sharing</h2>\n<p>Alien Colonies does not sell player personal data. Data may be processed by infrastructure providers needed to operate and distribute the game, including <strong>Railway</strong> for server hosting and <strong>Google Play</strong> for Android distribution. These providers may process technical information under their own terms and privacy policies.</p>\n\n<h2>4. Google sign-in</h2>\n<p><strong>Sign in with Google</strong> uses Google to verify your identity and limit each Google account to one active empire. The server stores your stable Google account identifier separately from public game data. The requested basic-profile scope may provide a profile name or picture during verification; the game discards these profile details and does not store them. Google may provide an email address and profile information during verification; these fields are discarded and only the stable Google subject is retained for account identity. Linking Google to an existing empire requires signing into that empire and confirming its current password. Your existing empire and progress remain intact. Alien Colonies never receives your Google password. For a Google-only account, recent Google sign-in confirms sensitive account actions, including deletion or setting an optional recovery password.</p>\n\n<h2>4a. Email sign-in</h2>\n<p>When email sign-in is enabled and you request a link, the server temporarily processes the address to deliver the message through <strong>Resend</strong>. Resend receives the recipient address and authentication message, including its short-lived link. These messages are for authentication, not marketing. The game database stores a cryptographic identifier derived from the normalized address, associated with your account, rather than the address itself. This identifier is not public and is removed with the account. Recent email authentication timestamps are stored with hashed sessions to authorize sensitive account actions.</p>\n<p>Pending sign-in data is held temporarily in server memory and expires after 15 minutes; expired entries are removed during subsequent email requests or a server restart. Browser sign-in uses short-lived, essential security cookies. Links work once and do not log you in merely because a mail scanner opens them. For an email-only account, signing in again by email confirms account deletion and other sensitive changes. The email provider may retain delivery records under its own retention settings and <a href="https://resend.com/legal/privacy-policy">privacy policy</a>.</p>\n\n<h2>Optional Android report notifications</h2>\n<p>If Android notifications are enabled, Firebase Cloud Messaging processes an app installation token, a pseudonymous empire identifier and notification content. The game stores the token with the current account, session and language. Logging out or deleting the account unlinks the device and removes pending deliveries. Undelivered messages expire within 24 hours. Notifications can be disabled in Android settings. No Firebase service-account key is included in the application.</p>\n<h2>5. Advertising</h2>\n<p>Some versions of Alien Colonies may include advertising through <strong>Google AdMob</strong>. When advertising is enabled in the installed version, Google and its advertising partners may process device identifiers, IP address, approximate location derived from IP, ad interaction data and other technical information for ad delivery, measurement, fraud prevention and, where permitted and consented to, personalization. Consent choices may be collected through Google\'s consent tools where required.</p>\n<p class="warning"><strong>If the installed version does not display ads, this advertising processing is not active in that version.</strong> The Google Play “contains ads” declaration and Data safety form should always reflect the actual released build.</p>\n\n<h2>6. Retention and account deletion</h2>\n<p>Active account and gameplay data are kept while the account exists and while needed to operate the multiplayer service. Session records expire automatically. The standard server keeps a rotating set of hourly disaster-recovery backups; deleted information may remain temporarily in those backups until they rotate out.</p>\n<p>You can permanently delete the account and empire from the in-game account settings. A web deletion option is also available at <a href="/delete-account">/delete-account</a>. Deletion removes the active account, credentials, sessions, recovery record, colonies and fleets. A public empire name may remain temporarily in historical multiplayer reports already stored for other players until those reports rotate out, and residual copies may remain in short-lived backups.</p>\n\n<h2>7. Security</h2>\n<p>Alien Colonies uses HTTPS in hosted operation, password hashing, hashed session tokens, rate limiting and restricted server logging. No internet service can guarantee absolute security, so use a unique password and keep recovery codes private.</p>\n\n<h2>8. Your choices</h2>\n<p>You may stop using the service, log out other devices, change your password, replace your recovery code, or delete the account. Questions about privacy or deletion can be sent to <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n\n<h2>9. Changes to this policy</h2>\n<p>This policy may be updated when Alien Colonies adds or removes features, providers, sign-in methods or advertising. The effective date at the top of this page will be updated when material changes are made.</p>\n</div>\n\n<div class="card" lang="pl">\n<h1>Alien Colonies — Polityka prywatności</h1>\n<p class="muted">Data obowiązywania: 13 października 2026 r.</p>\n<p>Operator: twórca gry <strong>Alien Colonies</strong>. Kontakt w sprawach prywatności: <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n<p>Niniejsza polityka opisuje przetwarzanie informacji podczas korzystania z gry Alien Colonies na Androidzie, serwera multiplayer oraz publicznych stron dotyczących prywatności i usuwania konta.</p>\n\n<h2>1. Dane przetwarzane w obecnym systemie kont</h2>\n<ul>\n<li><strong>Nazwa imperium/konta.</strong> Służy do identyfikacji konta i może być widoczna dla innych graczy w galaktyce oraz raportach multiplayer. Nie wpisuj w nazwie imperium wrażliwych danych z życia prywatnego.</li>\n<li><strong>Dane uwierzytelniające.</strong> Serwer przechowuje solony skrót hasła, a nie hasło w postaci jawnej. Tokeny sesji są przechowywane jako skróty kryptograficzne z terminem ważności. Po utworzeniu kodu odzyskiwania serwer zachowuje wyłącznie jego skrót.</li>\n<li><strong>Metody logowania.</strong> Jeśli dana opcja jest włączona, nowe imperia korzystają z weryfikacji Google lub jednorazowego linku e-mail. Istniejące konta z hasłem zachowują swoje dane logowania. Logowanie e-mailem nie łączy automatycznie istniejącego konta Google ani konta z hasłem.</li>\n<li><strong>Dane rozgrywki i zapisu.</strong> Obejmują m.in. rasę, planety, zasoby, budynki, badania, statki, floty, rozwój umiejętności, ochronę nowego gracza, raporty, wykonane akcje oraz inne informacje potrzebne do utrzymania imperium multiplayer.</li>\n<li><strong>Łączność graczy.</strong> Serwer zapisuje treść wiadomości, identyfikatory kont nadawcy i odbiorcy, czas, oznaczenia przeczytania, blokady i zgłoszenia nadużyć. Czat ogólny jest widoczny dla zalogowanych graczy; wiadomości prywatne są dostępne przez grę tylko uczestnikom rozmowy. Operator może przeglądać zgłoszone wiadomości w celu moderacji. Historia jest dostępna do 30 dni, a czat ogólny przechowuje do 1000 wiadomości; starsze rekordy są usuwane przy wysłaniu kolejnej wiadomości. Usunięcie konta usuwa jego wysłane wiadomości i rozmowy prywatne z aktywnej bazy. Kopie mogą tymczasowo pozostać w rotujących kopiach bezpieczeństwa.</li>\n<li><strong>Techniczne dane połączenia.</strong> Adres IP i metadane żądania są przetwarzane w zakresie niezbędnym do transmisji sieciowej, ograniczania liczby żądań i ochrony przed nadużyciami. Serwer gry jest zaprojektowany tak, aby we własnych logach żądań nie zapisywać haseł, tokenów Bearer, treści żądań ani pełnych parametrów zapytań. Dostawcy hostingu i sieci mogą przetwarzać zwykłe metadane infrastruktury podczas świadczenia usługi.</li>\n</ul>\n\n<h2>Subskrypcja kolejek</h2>\n<p>Płatności za subskrypcję obsługuje Google Play. W celu weryfikacji dostępu, odnowień i zmian stanu płatności serwer gry przechowuje token zakupu, pseudonimowy identyfikator konta gry, identyfikatory produktu i abonamentu, stan weryfikacji oraz daty opłaconych okresów. Dane te nie są pokazywane innym graczom. Alien Colonies nie otrzymuje danych Twojej karty. Dane są przechowywane wraz z kontem gry i usuwane z aktywnej bazy po usunięciu konta; kopie mogą czasowo pozostawać w rotacyjnych kopiach zapasowych. Subskrypcją można zarządzać i ją anulować w Google Play.</p>\n\n<h2>2. Cele przetwarzania</h2>\n<ul>\n<li>tworzenie, uwierzytelnianie i odzyskiwanie kont;</li>\n<li>utrzymywanie galaktyki multiplayer i synchronizacja postępów;</li>\n<li>realizacja raportów, walk, transportu i pozostałych funkcji multiplayer;</li>\n<li>ochrona przed nadużyciami, nadmierną liczbą żądań i nieautoryzowanym dostępem;</li>\n<li>wykonywanie kopii bezpieczeństwa, diagnozowanie awarii i zabezpieczenie usługi;</li>\n<li>realizacja obowiązków prawnych, jeśli mają zastosowanie.</li>\n</ul>\n\n<h2>3. Dostawcy usług i udostępnianie</h2>\n<p>Alien Colonies nie sprzedaje danych osobowych graczy. Dane mogą być przetwarzane przez dostawców infrastruktury niezbędnych do działania i dystrybucji gry, w szczególności <strong>Railway</strong> jako hosting serwera oraz <strong>Google Play</strong> jako platformę dystrybucji Android. Dostawcy ci mogą przetwarzać dane techniczne zgodnie z własnymi warunkami i politykami prywatności.</p>\n\n<h2>4. Logowanie przez Google</h2>\n<p><strong>Zaloguj przez Google</strong> potwierdza Twoją tożsamość i ogranicza każde konto Google do jednego aktywnego imperium. Serwer zapisuje stały identyfikator konta Google oddzielnie od publicznych danych gry. Zakres podstawowego profilu może udostępnić nazwę profilu lub zdjęcie podczas weryfikacji; gra pomija te dane i ich nie przechowuje. Google może przekazać adres e-mail i dane profilu podczas weryfikacji; te dane są odrzucane, a do identyfikacji konta zachowywany jest wyłącznie stały identyfikator Google. Połączenie Google z istniejącym imperium wymaga zalogowania do tego imperium i potwierdzenia jego obecnego hasła. Imperium i postęp zostają zachowane. Alien Colonies nigdy nie otrzymuje Twojego hasła Google. Dla konta używającego wyłącznie Google ponowne, niedawne logowanie potwierdza wrażliwe operacje, w tym usunięcie konta lub ustawienie opcjonalnego hasła odzyskiwania.</p>\n\n<h2>4a. Logowanie przez e-mail</h2>\n<p>Jeśli logowanie e-mailem jest włączone i poprosisz o link, serwer tymczasowo przetwarza podany adres, aby wysłać wiadomość przez <strong>Resend</strong>. Resend otrzymuje adres odbiorcy i wiadomość uwierzytelniającą z krótkotrwałym linkiem. Te wiadomości służą logowaniu, a nie marketingowi. Baza gry zapisuje powiązany z kontem identyfikator kryptograficzny wyliczony ze znormalizowanego adresu, zamiast samego adresu. Identyfikator nie jest publiczny i jest usuwany wraz z kontem. Czas ostatniego potwierdzenia e-mail jest przechowywany przy hashowanej sesji w celu autoryzacji wrażliwych operacji.</p>\n<p>Dane oczekującego logowania są przechowywane tymczasowo w pamięci serwera i tracą ważność po 15 minutach; wygasłe wpisy są usuwane podczas kolejnych żądań logowania e-mail lub restartu serwera. Logowanie w przeglądarce używa krótkotrwałych, niezbędnych ciasteczek bezpieczeństwa. Link działa raz, a samo otwarcie go przez skaner poczty nie powoduje zalogowania. Dla konta używającego wyłącznie e-mail ponowne logowanie potwierdza usunięcie konta i inne wrażliwe zmiany. Dostawca poczty może zachowywać informacje o dostarczeniu zgodnie ze swoimi ustawieniami retencji i <a href="https://resend.com/legal/privacy-policy">polityką prywatności</a>.</p>\n\n<h2>Opcjonalne powiadomienia o raportach na Androidzie</h2>\n<p>Po włączeniu powiadomień Firebase Cloud Messaging przetwarza identyfikator instalacji, pseudonimowy identyfikator imperium i treść powiadomienia. Gra przechowuje identyfikator urządzenia z bieżącym kontem, sesją i językiem. Wylogowanie lub usunięcie konta odłącza urządzenie i usuwa oczekujące powiadomienia. Niewysłane wiadomości wygasają po 24 godzinach. Powiadomienia można wyłączyć w ustawieniach Androida. Aplikacja nie zawiera prywatnego klucza konta usługi Firebase.</p>\n<h2>5. Reklamy</h2>\n<p>Niektóre wersje Alien Colonies mogą zawierać reklamy obsługiwane przez <strong>Google AdMob</strong>. Gdy reklamy są włączone w zainstalowanej wersji, Google i jego partnerzy reklamowi mogą przetwarzać identyfikatory urządzenia, adres IP, przybliżoną lokalizację ustalaną na podstawie IP, dane o interakcjach z reklamami i inne dane techniczne w celu wyświetlania reklam, pomiaru skuteczności, zapobiegania nadużyciom oraz — tam, gdzie jest to dozwolone i użytkownik wyrazi zgodę — personalizacji. W wymaganych regionach zgody mogą być obsługiwane przez narzędzia zgód Google.</p>\n<p class="warning"><strong>Jeżeli dana wersja gry nie wyświetla reklam, opisane przetwarzanie reklamowe nie jest w niej aktywne.</strong> Deklaracja „zawiera reklamy” i formularz Bezpieczeństwo danych w Google Play powinny zawsze odpowiadać faktycznie publikowanej wersji.</p>\n\n<h2>6. Okres przechowywania i usuwanie konta</h2>\n<p>Aktywne dane konta i rozgrywki są przechowywane tak długo, jak istnieje konto i jak długo są potrzebne do działania usługi multiplayer. Sesje wygasają automatycznie. Standardowy serwer utrzymuje rotacyjny zestaw godzinowych kopii awaryjnych; po usunięciu konta dane mogą pozostać w nich tymczasowo do czasu rotacji.</p>\n<p>Konto i całe imperium można trwale usunąć w ustawieniach konta w grze. Dostępna jest również strona internetowa <a href="/delete-account">/delete-account</a>. Usunięcie kasuje aktywne konto, dane uwierzytelniające, sesje, zapis kodu odzyskiwania, kolonie i floty. Publiczna nazwa imperium może przez pewien czas pozostawać w historycznych raportach multiplayer zapisanych u innych graczy, dopóki raporty nie zostaną usunięte przez rotację, a szczątkowe kopie mogą przez krótki czas znajdować się w kopiach bezpieczeństwa.</p>\n\n<h2>7. Bezpieczeństwo</h2>\n<p>W środowisku hostingowym Alien Colonies korzysta z HTTPS, hashowania haseł, hashowanych tokenów sesji, limitowania żądań i ograniczonego logowania serwera. Żadna usługa internetowa nie zapewnia całkowitego bezpieczeństwa, dlatego używaj unikalnego hasła i chroń kod odzyskiwania.</p>\n\n<h2>8. Twoje możliwości</h2>\n<p>Możesz przestać korzystać z usługi, wylogować inne urządzenia, zmienić hasło, zastąpić kod odzyskiwania lub usunąć konto. Pytania dotyczące prywatności lub usunięcia danych można wysłać na <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n\n<h2>9. Zmiany polityki</h2>\n<p>Polityka może zostać zaktualizowana po dodaniu lub usunięciu funkcji, dostawców, metod logowania lub reklam. Przy istotnej zmianie zostanie zaktualizowana data obowiązywania podana na początku strony.</p>\n</div>\n</main></body></html>'

ACCOUNT_DELETION_HTML = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="robots" content="index,follow"><title>Alien Colonies — Delete account / Usuń konto</title>\n<style>:root{color-scheme:dark;background:#07110d;color:#e7f3ea;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}body{margin:0}main{max-width:760px;margin:auto;padding:32px 20px 64px}.card{background:#0d2118;border:1px solid #254638;border-radius:18px;padding:24px}h1{margin-top:0}label{display:block;margin:16px 0 7px;color:#bce9c7}input{box-sizing:border-box;width:100%;font:inherit;padding:13px;border-radius:10px;border:1px solid #3e6552;background:#07140e;color:#fff}button{margin-top:20px;width:100%;padding:14px;font:inherit;font-weight:700;border:0;border-radius:10px;background:#9e3f3f;color:#fff;cursor:pointer}button:disabled{opacity:.55;cursor:wait}.muted{color:#a9bdb1;line-height:1.55}.danger{color:#ffb2a8}a{color:#8fd7a1}#status{margin-top:16px;min-height:1.5em;white-space:pre-wrap}.split{border-top:1px solid #2c4d3d;margin-top:26px;padding-top:22px}</style></head>\n<body><main><div class="card">\n<h1>Delete Alien Colonies account</h1>\n<p class="danger"><strong>This permanently deletes your active account and empire. This cannot be undone.</strong></p>\n<p class="muted">Use the same empire name and password that you use in the game. Credentials are sent directly to the Alien Colonies server over HTTPS and are not stored by this web page. You can also delete the account from the in-game Account settings.</p>\n<div class="split"><h2>Google account / Konto Google</h2><p class="muted">Sign in with Google in the <a href="/play/">browser game</a>, open Settings (the gear button), choose Delete account and confirm your Google account before deleting.</p><p class="muted" lang="pl">Zaloguj się przez Google w <a href="/play/">grze przeglądarkowej</a>, otwórz Ustawienia (przycisk z kołem zębatym), wybierz Usuń konto i potwierdź konto Google przed usunięciem.</p></div><div class="split"><h2>Email account / Konto e-mail</h2><p class="muted">Use Continue with email in the <a href="/play/">browser game</a>, confirm your link, then open Settings and choose Delete account. If your recent confirmation expires, request a fresh email link to confirm deletion.</p><p class="muted" lang="pl">Wybierz logowanie e-mailem w <a href="/play/">grze przeglądarkowej</a>, potwierdź link, a następnie otwórz Ustawienia i wybierz Usuń konto. Jeśli potwierdzenie straci ważność, poproś o nowy link e-mail, aby potwierdzić usunięcie.</p></div><h2>Account with a password / Konto z hasłem</h2>\n<label for="name">Empire name / Nazwa imperium</label><input id="name" maxlength="20" autocomplete="username">\n<label for="password">Password / Hasło</label><input id="password" type="password" maxlength="128" autocomplete="current-password">\n<label for="confirm">Type exactly / Wpisz dokładnie: DELETE ACCOUNT</label><input id="confirm" maxlength="32" autocomplete="off">\n<button id="delete">Permanently delete account / Trwale usuń konto</button><div id="status" role="status" aria-live="polite"></div>\n<div class="split" lang="pl"><h2>Usuwanie konta</h2><p class="muted">Po poprawnym potwierdzeniu serwer usuwa aktywne konto, sesje, kod odzyskiwania, kolonie, floty oraz pozostałe dane imperium. Krótkotrwałe kopie awaryjne mogą wygasnąć dopiero wraz z rotacją. W razie problemu napisz na <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p></div>\n<p><a href="/privacy">Privacy Policy / Polityka prywatności</a></p>\n</div></main>\n<script>\n(()=>{const q=id=>document.getElementById(id),btn=q(\'delete\'),status=q(\'status\');\nconst headers=()=>({\'Content-Type\':\'application/json\',\'Accept-Language\':navigator.language||\'en\',\'X-PGR-Client-Version\':\'2100000000\'});\nbtn.addEventListener(\'click\',async()=>{const name=q(\'name\').value.trim(),password=q(\'password\').value,confirmation=q(\'confirm\').value;\nif(name.length<3||password.length<8){status.textContent=\'Enter the account name and password. / Wpisz nazwę konta i hasło.\';return}\nif(confirmation!==\'DELETE ACCOUNT\'){status.textContent=\'Type exactly: DELETE ACCOUNT\';return}\nif(!confirm(\'Permanently delete this Alien Colonies account and empire? / Trwale usunąć konto i imperium?\'))return;\nbtn.disabled=true;status.textContent=\'Deleting… / Usuwanie…\';\ntry{let r=await fetch(\'/api/login\',{method:\'POST\',headers:headers(),body:JSON.stringify({name,password})});let j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||\'Login failed\');\nlet h=headers();h.Authorization=\'Bearer \'+j.token;r=await fetch(\'/api/account/delete\',{method:\'POST\',headers:h,body:JSON.stringify({password,confirmation:\'DELETE ACCOUNT\'})});j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||\'Deletion failed\');\nq(\'password\').value=\'\';q(\'confirm\').value=\'\';status.textContent=\'Account deleted. / Konto zostało usunięte.\';btn.remove();\n}catch(e){status.textContent=\'Could not delete the account: \'+e.message+\' / Nie udało się usunąć konta.\';btn.disabled=false;}\n});})();\n</script></body></html>'


class GameError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def validate_download_url(value):
    """Check an ASCII HTTPS DNS download link; same subset as the Android client."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError(t('PGR_DOWNLOAD_URL: podaj adres HTTPS do 2048 znaków.'))
    if not value:
        return ""
    if (any(ord(c) <= 32 or ord(c) >= 127 for c in value) or "\\" in value
            or re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f|5c)", value, re.IGNORECASE)):
        raise ValueError("PGR_DOWNLOAD_URL: adres zawiera niedozwolone znaki.")
    try:
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?(?:[/?].*)?", value):
            raise ValueError
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
        if (parsed.scheme != "https" or not host or parsed.username is not None
                or parsed.password is not None or parsed.fragment or "#" in value
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            labels = host.split(".")
            if (len(host) > 253 or len(labels) < 2
                    or not all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part)
                               for part in labels)
                    or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]*", labels[-1])
                    or labels[-1].lower() in ("localhost", "local", "internal", "lan", "home", "test", "invalid", "example", "onion")
                    or host.lower() == "home.arpa" or host.lower().endswith(".home.arpa")):
                raise ValueError
        else:
            raise ValueError
    except ValueError:
        raise ValueError(t('PGR_DOWNLOAD_URL: wymagany publiczny adres HTTPS bez hasła ani fragmentu #.')) from None
    return value


PLAY_STORE_PACKAGE_ID = "com.conradmafer.aliencolonies"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=" + PLAY_STORE_PACKAGE_ID


class UpdatePolicy:
    """Compatibility gate only; app installation belongs exclusively to Google Play.

    Legacy APK arguments remain accepted for old local callers, but are ignored.
    They cannot change the destination, require an APK, or prevent startup.
    The version header is a compatibility signal, NOT proof of app integrity.
    min_version_code applies to Android only, independently of the hosted web.
    """

    def __init__(self, latest_version_code=CLIENT_VERSION_CODE, latest_version=UPDATE_DEFAULT_VERSION,
                 min_version_code=0, download_url="", message="",
                 apk_sha256="", apk_size_bytes=0):
        for name, value in (("PGR_LATEST_VERSION_CODE", latest_version_code),
                            ("PGR_MIN_VERSION_CODE", min_version_code)):
            if type(value) is not int or not 0 <= value <= MAX_VERSION_CODE:
                raise ValueError(t('{0}: podaj liczbę całkowitą od 0 do {1}.').format(name, MAX_VERSION_CODE))
        if latest_version_code < min_version_code:
            raise ValueError(t('PGR_LATEST_VERSION_CODE nie może być mniejsze od PGR_MIN_VERSION_CODE.'))
        for name, value, limit in (("PGR_LATEST_VERSION", latest_version, 40),
                                   ("PGR_UPDATE_MESSAGE", message, 300)):
            if (not isinstance(value, str) or len(value) > limit
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise ValueError(t('{0}: maksymalnie {1} znaków, bez znaków sterujących.').format(name, limit))
        if not latest_version.strip():
            raise ValueError(t('PGR_LATEST_VERSION nie może być puste.'))
        self.latest_version_code = latest_version_code
        self.latest_version = latest_version
        self.min_version_code = min_version_code
        self.message = message
        # Never expose a direct installer link to any client, including legacy clients.
        self.download_url = ""
        self.apk_sha256 = ""
        self.apk_size_bytes = 0

    def manifest(self):
        return {"ok": True, "latest_version_code": self.latest_version_code,
                "latest_version": self.latest_version, "min_version_code": self.min_version_code,
                "distribution": "google_play", "play_store_url": PLAY_STORE_URL,
                "package_id": PLAY_STORE_PACKAGE_ID, "message": self.message,
                "download_url": "", "apk_sha256": "", "apk_size_bytes": 0}


def load_update_policy(env=None):
    """Read Railway config once on startup. Redeploy to apply a changed minimum.

    PGR_DOWNLOAD_URL / PGR_APK_SHA256 / PGR_APK_SIZE_BYTES are obsolete.
    They are intentionally not parsed, even if old deployments still define them.
    """
    env = os.environ if env is None else env

    def version_code(name, default):
        value = env.get(name, str(default))
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value):
            raise ValueError(t('{0}: podaj nieujemną liczbę całkowitą.').format(name))
        return int(value)

    return UpdatePolicy(latest_version_code=version_code("PGR_LATEST_VERSION_CODE", CLIENT_VERSION_CODE),
                        latest_version=env.get("PGR_LATEST_VERSION", UPDATE_DEFAULT_VERSION),
                        min_version_code=version_code("PGR_MIN_VERSION_CODE", 0),
                        message=env.get("PGR_UPDATE_MESSAGE", ""))


class UpdateRequired(GameError):
    def __init__(self, policy):
        super().__init__(t('Zaktualizuj grę, aby kontynuować.'), 426)
        self.update = policy.manifest()


def is_web_client(headers):
    """Identify browser requests independently of Android versionCode.

    Older, already loaded web builds have no platform header, but same-origin
    browser fetches provide Fetch Metadata. Native clients keep the Android
    gate. These headers are compatibility signals, never authentication.
    """
    platforms = headers.get_all("X-PGR-Client-Platform", [])
    if platforms:
        return len(platforms) == 1 and platforms[0].strip().lower() == "web"
    return (headers.get_all("Sec-Fetch-Site", []) == ["same-origin"]
            and headers.get_all("Sec-Fetch-Dest", []) == ["empty"]
            and headers.get_all("Sec-Fetch-Mode", []) in (["cors"], ["same-origin"]))


def ident(prefix):
    return prefix + secrets.token_hex(8)


def integer(value, label, low=0, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise GameError(t('{0}: podaj liczbę całkowitą od {1} do {2}.').format(label, low, high))
    return value


def counts(value, valid_keys, label, maximum=1_000_000):
    if not isinstance(value, dict) or any(k not in valid_keys for k in value):
        raise GameError(t('Nieprawidłowe dane: {0}.').format(label))
    return {k: integer(value.get(k, 0), label, 0, maximum) for k in valid_keys}


def scaled_cost(base, level):
    return dict(zip(RESOURCES, [int(math.ceil(v * 1.65 ** level)) for v in base]))


def affordable(planet, cost):
    return all(planet["resources"][k] >= v for k, v in cost.items())


def spend(planet, cost):
    for k, v in cost.items():
        planet["resources"][k] -= v


def blank_ships():
    return dict.fromkeys(SHIPS, 0)


def fleet_capacity(specs, ships):
    # Stat bonuses have at most six decimal places. Remove binary floating-point
    # noise before flooring the combined hold, without rounding real fractions up.
    return math.floor(round(math.fsum(specs[key][6] * n for key, n in ships.items() if n), 6))


def atomic_mutation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._atomic():
            return method(self, *args, **kwargs)
    return wrapped


def restore_snapshot(target, saved):
    """Restore existing containers in place so held planet/player references agree."""
    if isinstance(target, dict) and isinstance(saved, dict):
        for key in list(target):
            if key not in saved:
                del target[key]
        for key, value in saved.items():
            if key in target and isinstance(value, (dict, list)) and type(target[key]) is type(value):
                restore_snapshot(target[key], value)
            else:
                target[key] = copy.deepcopy(value)
    elif isinstance(target, list) and isinstance(saved, list):
        target[:] = copy.deepcopy(saved)


try:
    from .galaxies import UniverseMixin, BY_ID as GALAXIES_BY_ID, separation, inferred_id, JUMP_BASE_FUEL, JUMP_FUEL_PER_MASS, JUMP_SECONDS_PER_MLY
    from . import technology
    from .megastructures import MegastructureMixin, empty_project
    from .planetary import PlanetaryMixin
    from .observation import ObservationMixin, ranges as observation_ranges
    from .alliances import AllianceMixin
    from .alliance_operations import AllianceOperationsMixin
except ImportError:
    from galaxies import UniverseMixin, BY_ID as GALAXIES_BY_ID, separation, inferred_id, JUMP_BASE_FUEL, JUMP_FUEL_PER_MASS, JUMP_SECONDS_PER_MLY
    import technology
    from megastructures import MegastructureMixin, empty_project
    from planetary import PlanetaryMixin
    from observation import ObservationMixin, ranges as observation_ranges
    from alliances import AllianceMixin
    from alliance_operations import AllianceOperationsMixin


class World(ExpeditionMixin, BeginnerProtectionMixin, InactivityMixin, EmailAccountMixin, GoogleAccountMixin, PlannedQueuesMixin, LaunchResetMixin, SwarmResetMixin, AllianceMixin, AllianceOperationsMixin, PlanetaryMixin, ObservationMixin, MegastructureMixin, BalanceResetMixin, UniverseMixin, SwarmAIMixin, IntelligenceMixin, AccountManagementMixin, CommunicationsMixin):
    """All public operations are locked. advance(now) makes time injectable in tests."""

    account_error_class = GameError
    planned_error_class = GameError
    ECONOMY_MULTIPLIER = ECONOMY_MULTIPLIER
    MAX_RESOURCE = MAX_RESOURCE
    expedition_counts = staticmethod(counts)
    expedition_affordable = staticmethod(affordable)
    expedition_capacity = staticmethod(fleet_capacity)

    def __init__(self, db_path="galaxy.sqlite3", speed=1.0, now=None,
                 max_players=0, apply_balance_reset=False, billing_verifier=None):
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.1 <= speed <= 1000:
            raise ValueError("speed must be finite and between 0.1 and 1000")
        if type(max_players) is not int or max_players < 0:
            raise ValueError("max_players must be a nonnegative integer (0 disables the account cap)")
        self.max_players = max_players
        self.db_path = str(db_path)
        self.speed = float(speed)
        self.lock = threading.RLock()
        # Ephemeral presence: successful authenticated state polls, not saved game activity.
        # Do not persist this or let it resume suspended resource production.
        self._state_poll_presence = {}
        self.billing_verifier = BillingVerifier.from_env() if billing_verifier is None else billing_verifier
        self.require_google_registration = False
        self._atomic_depth = 0
        self.write_healthy = True
        self.backups = SQLiteBackups(db_path)
        self.now = float(time.time() if now is None else now)
        if str(db_path) != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(str(db_path))), exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, name_key TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, player_id TEXT NOT NULL REFERENCES accounts(id), expires REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS sessions_player ON sessions(player_id);
        """)
        self._init_google_accounts()
        self._init_email_accounts()
        self._init_account_management()
        self._init_communications()
        push_notifications.init_db(self.db)
        self.db.commit()
        row = self.db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
        if row:
            self.data = json.loads(row[0])
            # The release owner explicitly authorized deletion of every old
            # player account and a fresh Swarm. Do this before NPC migrations or
            # offline simulation, with a verified permanent pre-reset backup.
            if self.data.get("launch_reset_id") != LAUNCH_RESET_ID:
                self.now = max(self.now, self.data["last_update"])
                try:
                    self._apply_launch_reset()
                except BaseException:
                    self.db.close()
                    raise
                return
            if apply_balance_reset and self.data.get("balance_reset_id") != BALANCE_RESET_ID:
                try:
                    self._apply_balance_reset()
                except BaseException:
                    self.db.close()
                    raise
                return
            # Back up the committed pre-migration database before adding galaxies.
            # Refuse a disk-backed migration when its backup cannot be written.
            if (self.data.get("galaxy_schema_version", 0) < galaxy_topology.SCHEMA or self.data.get("activity_schema_version", 0) < 1 or self.data.get("recon_defense_schema", 0) < 1 or self.data.get("technology_schema", 0) < 2 or self.data.get("planetary_schema", 0) < 1 or self.data.get("observation_schema", 0) < 1 or self.data.get("planet_traits_schema", 0) < 1 or self.data.get("alliances_schema", 0) < 1 or "ogame_economy_from" not in self.data or "economy85_from" not in self.data) and self.backups.directory is not None:
                if self.backups.maybe_create(self.db, force=True) is None:
                    self.db.close()
                    raise OSError("Nie zapisano kopii przed migracją świata. Sprawdz wolne miejsce na Volume.")
            self.now = max(self.now, self.data["last_update"])
            swarm_reset_needed = self.data.get("swarm_reset_id") != swarm.RESET_ID
            expansion_needed = (self.data.get("galaxy_schema_version", 0) < galaxy_topology.SCHEMA
                                or self.data.get("activity_schema_version", 0) < 1)
            try:
                # Reuse the verified-copy helper only; this never calls a reset.
                # Keep the original world outside normal rolling retention.
                expansion_backup = (verified_reset_backup(self.db, self.db_path, reset_id="galaxy-rings-01232")
                                    if expansion_needed else None)
                if expansion_needed:
                    print(f"Alien Colonies {VERSION}: verified pre-expansion backup: "
                          + str(expansion_backup or "test in-memory"), flush=True)
                # Dedicated permanent backup, BEFORE any in-memory migration or
                # transaction. Failure leaves the committed database untouched.
                swarm_backup = (verified_reset_backup(self.db, self.db_path, reset_id=swarm.RESET_ID)
                                if swarm_reset_needed else None)
                with self._atomic():
                    if expansion_needed:
                        self.data.update(galaxy_expansion_backup=expansion_backup.name if expansion_backup else "memory-only",
                                         galaxy_expansion_at=self.now)
                    self._ensure_activity_policy()
                    self._ensure_progression()
                    self._ensure_universe()
                    self._ensure_planetary()
                    self._ensure_observation()
                    planet_traits.ensure(self.data, self.now)
                    self._ensure_alliances()
                    self._ensure_alliance_operations()
                    self.data.setdefault("economy_slow_from", self.now)
                    self.data.setdefault("ogame_economy_from", self.now)
                    self.data.setdefault("economy85_from", self.now)
                    self.data["economy85_schema"] = 1
                    self.data["recon_defense_schema"] = 1
                    self._apply_swarm_reset(swarm_backup)
                    rankings.ensure_rewards(self)
                    # Existing player queue/flight deadlines remain absolute.
                    self.advance(self.now)
            except BaseException:
                self.db.close()
                raise
            if expansion_needed:
                print(f"Alien Colonies {VERSION}: additive galaxy expansion committed; "
                      f"systems={len(self.data['systems'])}; planets={len(self.data['planets'])}; "
                      f"players={len(self.data['players'])}; world_epoch={self.data.get('launch_reset_id', '')}", flush=True)
            if swarm_reset_needed:
                print("Alien Colonies 0.11.3: NPC-only plague reset committed; "
                      "player progression preserved; backup: " + str(swarm_backup or "memory-only"), flush=True)
        else:
            self.data = self._new_world()
            rankings.ensure_rewards(self)
            self._save()
            self.backups.maybe_create(self.db)

    def _new_world(self):
        systems, planets = [], {}
        for i, name in enumerate(SYSTEM_NAMES):
            sid = f"s{i+1}"
            ids = []
            for slot in range(1, planetary.system_count(sid) + 1):
                pid = f"{sid}p{slot}"
                ids.append(pid)
                planets[pid] = self._planet(pid, f"{name} {slot}", sid, slot)
            systems.append({"id": sid, "name": name, "x": (i % 6) * 1.0, "y": (i // 6) * 1.0, "planet_ids": ids})
        for sid in ("s15",):
            swarm.seed(planets[f"{sid}p2"], self.now, hive=True)
        data = {"progression_version": 2, "last_update": self.now, "systems": systems, "planets": planets, "players": {}, "fleets": {}, "alien": {"name": t('Rój Khar'), "next_expansion_at": self.now + 120, "swarm_next_colonization_by_galaxy": {g: self.now + swarm.COLONY_MATURITY_SECONDS for g in GALAXIES_BY_ID}, "swarm_next_raid_at": self.now + swarm.RAID_INTERVAL_SECONDS}}
        self._ensure_universe(data)
        self._ensure_swarm_activation(data)
        self._ensure_planetary(data)
        planet_traits.ensure(data, self.now)
        self._ensure_alliances(data)
        self._ensure_alliance_operations(data)
        data["observation_schema"] = 1
        data.update(recon_defense_schema=1, technology_schema=2, economy_slow_from=self.now, ogame_economy_from=self.now,
                    economy85_from=self.now, economy85_schema=1, balance_reset_id=BALANCE_RESET_ID,
                    swarm_reset_id=swarm.RESET_ID, swarm_reset_at=self.now, swarm_reset_backup="fresh-world")
        # A world created on this release must never lose accounts on restart.
        data.update(launch_reset_id=LAUNCH_RESET_ID, launch_reset_at=self.now,
                    launch_reset_backup="fresh-world")
        self._ensure_activity_policy(data)
        return data

    def _ensure_progression(self):
        """Additive migration: no wallet grant, and existing race signatures stay active."""
        self.data["technology_schema"] = 2
        # Existing 0.4.0 worlds gain a grace period once, without reseeding NPCs.
        self.data["alien"].setdefault("swarm_next_raid_at", self.now + swarm.RAID_INTERVAL_SECONDS)
        for player in self.data["players"].values():
            review_invite.ensure(player)
            player.setdefault("planned_orders", [])
            player.setdefault("swarm_crystals", 0)
            player.setdefault("scout_intel", {})
            player["skill_nodes"] = skill_tree.unlocked_for(player.get("race_id", ""), player.get("skill_nodes", []))
            self._ensure_racial_research(player)
            protection_extended = self._upgrade_beginner_protection(player)
            self._ensure_legacy_report_i18n(player, protection_extended=protection_extended)
            onboarding.ensure(self.data, player)
        self._ensure_protection_notices()
        for planet in self.data["planets"].values():
            planet.setdefault("defenses", {})
            self._ensure_race_buildings(planet)
            for key in self._specs(planet["owner_id"], "ships"):
                planet["ships"].setdefault(key, 0)
        for fleet in self.data["fleets"].values():
            for key in self._specs(fleet["owner_id"], "ships"):
                fleet["ships"].setdefault(key, 0)
        # Old fortress migrations are superseded by the transactional NPC-only
        # plague reset. Never create huge fleets and then erase them again.
        self.data["progression_version"] = max(2, self.data.get("progression_version", 0))

    def _ensure_legacy_report_i18n(self, player, *, protection_extended=False):
        """Attach safe templates to known pre-localization reports without touching names."""
        race_id = player.get("race_id", "")
        for report in player.get("reports", []):
            if (protection_extended and report.get("title") == 'Witaj w Alien Colonies'
                    and report.get("text") == LEGACY_WELCOME_REPORT_TEXT):
                # Keep the same delivered report, identity and read metadata.
                report["text"] = WELCOME_REPORT_TEXT
                if not isinstance(report.get("i18n"), dict):
                    report["i18n"] = {}
                report["i18n"].setdefault("title", store_text(t('Witaj w Alien Colonies')))
                report["i18n"]["text"] = store_text(t(WELCOME_REPORT_TEXT))
            if isinstance(report.get("i18n"), dict):
                continue
            title = report.get("title", "")
            text = report.get("text", "")
            if title == 'Witaj w Alien Colonies' and text in (WELCOME_REPORT_TEXT, LEGACY_WELCOME_REPORT_TEXT):
                report["i18n"] = {"title": store_text(t('Witaj w Alien Colonies')),
                                  "text": store_text(t(text))}
                continue
            if title != 'Narodziny cywilizacji' or race_id not in RACES:
                continue
            race = RACES[race_id]
            intro = t('Wybrano rasę: {0}. To stały wybór tego imperium.').format(t(race['name']))
            composed = intro + " " + t(race["trait"]) + " " + t(race["tradeoff"])
            if text == render_text(store_text(composed), "pl"):
                report["i18n"] = {"title": store_text(t('Narodziny cywilizacji')),
                                  "text": store_text(composed)}


    @staticmethod
    def _planet(pid, name, sid, slot):
        return {"id": pid, "name": name, "system_id": sid, "galaxy_id": inferred_id(sid), "slot": slot, "owner_type": "empty", "owner_id": "", "resources": dict.fromkeys(RESOURCES, 0.0), "buildings": dict.fromkeys(BUILDINGS, 0), "ships": blank_ships(), "defenses": {}, "queue": []}

    @contextmanager
    def _atomic(self):
        """A public mutation succeeds only when both SQL and its RAM snapshot commit.

        A failed advance restores last_update and now, so its elapsed time and
        completed events can be retried. Failed actions restore replay ids too.
        """
        with self.lock:
            if self._atomic_depth:
                self._atomic_depth += 1
                try:
                    yield
                finally:
                    self._atomic_depth -= 1
                return
            before, before_now = copy.deepcopy(self.data), self.now
            self._atomic_depth = 1
            saving = False
            try:
                self.db.execute("SAVEPOINT world_mutation")
                yield
                saving = True
                self._save(commit=False)
                self.db.execute("RELEASE SAVEPOINT world_mutation")
                self.db.commit()
            except BaseException as exc:
                rollback_failed = False
                try:
                    self.db.rollback()
                except sqlite3.Error:
                    rollback_failed = True
                finally:
                    restore_snapshot(self.data, before)
                    self.now = before_now
                if rollback_failed or saving or isinstance(exc, (sqlite3.Error, OSError)):
                    self.write_healthy = False
                    raise GameError(t('Zapis gry jest chwilowo niedostępny. Spróbuj ponownie za chwilę.'), 503) from None
                raise
            else:
                self.write_healthy = True
            finally:
                self._atomic_depth = 0
            self.backups.maybe_create(self.db)

    def _save(self, commit=True):
        try:
            if self.data.get("planet_traits_schema", 0) >= 1:
                self._refresh_trait_intel()
            body = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            self.db.execute("INSERT INTO snapshot(id,body) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (body,))
            if commit and not self._atomic_depth:
                self.db.commit()
                self.write_healthy = True
        except (sqlite3.Error, OSError, ValueError, TypeError):
            self.write_healthy = False
            raise

    def close(self):
        with self.lock:
            try:
                self._save()
            finally:
                self.db.close()

    def _race_id(self, owner_id):
        # Khar is an NPC without a skill root; its own catalog is handled in _specs.
        race_id = self.data["players"].get(owner_id, {}).get("race_id", "")
        return race_id if isinstance(race_id, str) and race_id in RACES else ""

    def _bonuses(self, owner_id):
        player = self.data["players"].get(owner_id, {})
        return skill_tree.bonuses(self._race_id(owner_id), player.get("skill_nodes", []))

    def _ensure_race_buildings(self, p):
        if p["owner_id"] != "khar":
            p["buildings"].setdefault(expeditions.KEY, 0)
        for key in UNIQUE_BUILDINGS.get(self._race_id(p["owner_id"]), {}):
            p["buildings"].setdefault(key, 0)

    def _ensure_racial_research(self, player):
        # New effects start at zero. Loading an old save never grows existing ships.
        for key in UNIQUE_RESEARCH.get(player.get("race_id", ""), {}):
            player["research"].setdefault(key, 0)
        for key in technology.RESEARCH:
            player["research"].setdefault(key, 0)
        player.setdefault("megastructure", empty_project())
        player.setdefault("fleet_growth_credits", {})

    def _racial_research_level(self, owner_id, key):
        if key not in UNIQUE_RESEARCH.get(self._race_id(owner_id), {}):
            return 0
        level = self.data["players"][owner_id]["research"].get(key, 0)
        return max(0, min(5, level)) if type(level) is int else 0

    def _fleet_multiplier(self, owner_id):
        return Fraction(5 + self._racial_research_level(owner_id, "multiplication"), 5)

    @staticmethod
    def _growth_credit(player, key):
        value = player.get("fleet_growth_credits", {}).get(key, [0, 1])
        return Fraction(value[0], value[1])

    @staticmethod
    def _store_growth_credit(player, key, value):
        player.setdefault("fleet_growth_credits", {})[key] = [value.numerator, value.denominator]

    def _produced_ships(self, owner_id, key, amount):
        multiplier = self._fleet_multiplier(owner_id)
        if multiplier == 1:
            return amount
        player = self.data["players"][owner_id]
        exact = amount * multiplier + self._growth_credit(player, key)
        count = math.floor(exact)
        self._store_growth_credit(player, key, exact - count)
        return count

    def _multiply_existing_fleet(self, owner_id, old_level, new_level):
        """Grow surviving ships once; exact credits make batch size immaterial.

        Credits belong to a ship type across the empire. Whole new ships are split
        proportionally over occupied locations, with stable largest-remainder ties.
        Neither cargo nor mission identity/deadlines are copied or recalculated.
        """
        if self._race_id(owner_id) != "symbionts" or new_level <= old_level:
            return 0
        ratio = Fraction(5 + new_level, 5 + old_level)
        player = self.data["players"][owner_id]
        locations = sorted(
            [("planet:" + p["id"], p["ships"]) for p in self.data["planets"].values() if p["owner_id"] == owner_id]
            + [("fleet:" + f["id"], f["ships"]) for f in self.data["fleets"].values() if f["owner_id"] == owner_id],
            key=lambda row: row[0])
        grown = 0
        for key in self._specs(owner_id, "ships"):
            occupied = [(name, ships, ships.get(key, 0)) for name, ships in locations if ships.get(key, 0) > 0]
            total = sum(count for _, _, count in occupied)
            if not total:
                # A remembered fraction cannot resurrect a completely lost type.
                continue
            exact = (total + self._growth_credit(player, key)) * ratio
            extra = math.floor(exact) - total
            self._store_growth_credit(player, key, exact - math.floor(exact))
            shares = [extra * count // total for _, _, count in occupied]
            remaining = extra - sum(shares)
            order = sorted(range(len(occupied)), key=lambda i: (-(extra * occupied[i][2] % total), occupied[i][0]))
            for i in order[:remaining]:
                shares[i] += 1
            for (_, ships, _), share in zip(occupied, shares):
                ships[key] += share
            grown += extra
        return grown

    def _building_effects(self, p):
        """Only the owner's local structures apply; foreign skill roots do not."""
        return {meta["effect"]: building_effect_value(meta, p["buildings"].get(key, 0))
                for key, meta in UNIQUE_BUILDINGS.get(self._race_id(p["owner_id"]), {}).items()}

    def _racial_research_effects(self, owner_id):
        """Empire-wide bonuses from completed research; signatures remain separate."""
        effects = {}
        for key, meta in UNIQUE_RESEARCH.get(self._race_id(owner_id), {}).items():
            if "effect" not in meta:
                continue
            value = min(meta["cap"], meta["per_level"] * self._racial_research_level(owner_id, key))
            effects[meta["effect"]] = round(effects.get(meta["effect"], 0) + value, 6)
        common = self._technology_effects(owner_id)
        for key in ("flight_speed", "fuel_efficiency"):
            effects[key] = effects.get(key, 0) + common.get(key, 0)
        return effects

    def _entry_requirements(self, owner_id, planet, group, key):
        """Resolve local-building requirements and mixed prerequisites."""
        if group == "defenses":
            return [{"group": "buildings", "key": "shipyard", "name": self._specs(owner_id, "buildings")["shipyard"][0],
                     "level": 1, "met": planet["buildings"].get("shipyard", 0) >= 1}]
        race_id = self._race_id(owner_id)
        if group == "ships":
            default = (("shipyard", 2 if key == "cruiser" else
                        6 if key == "siege" else 4 if key == "freighter" else
                        3 if key == "interceptor" else 1),)
            required = SHIP_REQUIREMENTS.get(race_id, {}).get(key, fleet_expansion.COMMON_REQUIREMENTS.get(key, default))
        else:
            catalog = UNIQUE_BUILDINGS if group == "buildings" else UNIQUE_RESEARCH
            required = catalog.get(race_id, {}).get(key, {}).get("requirements", ())
            if group == "buildings" and key == "observatory":
                required = (("lab", 2),)
            if group == "buildings" and key == expeditions.KEY:
                required = (("shipyard", 3), ("lab", 4))
            if group == "research" and key in technology.RESEARCH:
                required = technology.RESEARCH[key]["requirements"]
            if group == "research":
                required = (*required, ("lab", 1))
        player = self.data["players"].get(owner_id, {})
        normalized = {}
        for entry in required:
            prerequisite_group, prerequisite_key, minimum = ("buildings", *entry) if len(entry) == 2 else entry
            if prerequisite_group not in ("buildings", "research", "megastructures"):
                raise ValueError("Unsupported prerequisite group: " + prerequisite_group)
            identity = (prerequisite_group, prerequisite_key)
            normalized[identity] = max(minimum, normalized.get(identity, 0))
        result = []
        for (prerequisite_group, prerequisite_key), minimum in normalized.items():
            if prerequisite_group == "megastructures":
                project = player.get("megastructure", {})
                # A Titan must be built at the star powering its core.
                current = project.get("dyson_stage", 0) if project.get("origin_id") == planet["id"] else 0
                result.append({"group": prerequisite_group, "key": prerequisite_key,
                               "name": t("Sfera Dysona w tej kolonii"), "level": minimum,
                               "current": current, "met": current >= minimum})
                continue
            specs = self._specs(owner_id, prerequisite_group)
            if prerequisite_key not in specs:
                raise ValueError("Unknown prerequisite: " + prerequisite_key)
            levels = planet["buildings"] if prerequisite_group == "buildings" else player.get("research", {})
            result.append({"group": prerequisite_group, "key": prerequisite_key,
                           "name": specs[prerequisite_key][0], "level": minimum,
                           "current": levels.get(prerequisite_key, 0), "met": levels.get(prerequisite_key, 0) >= minimum})
        return result

    def _lootable_resources(self, planet):
        """A local vault shields each ordinary stock before the 35% loot fraction."""
        protected = self._building_effects(planet).get("protected_resources", 0)
        return {key: math.floor(max(0, planet["resources"][key] - protected) * .35)
                for key in RESOURCES}

    def _rules(self, owner_id):
        if owner_id == "khar":
            return swarm.RULES
        race_id = self._race_id(owner_id)
        rules = copy.deepcopy(RACES[race_id]["rules"] if race_id else NEUTRAL_RULES)
        bonuses = self._bonuses(owner_id)
        # Signatures now come from roots exactly once; foreign roots can be earned.
        rules["first_volley_multiplier"] = 1.0 + bonuses.get("first_volley", 0)
        rules["regeneration_fraction"] = bonuses.get("regeneration", 0)
        rules["damage_reduction"] = bonuses.get("damage_reduction", 0)
        for resource in RESOURCES:
            rules["production_multipliers"][resource] *= 1.0 + bonuses.get("production_" + resource, 0)
        rules["energy_supply_per_level"] *= (1.0 + bonuses.get("energy", 0)) * (1.0 + self._technology_effects(owner_id).get("energy", 0))
        return rules

    def _specs(self, owner_id, group):
        # Offline arrivals are replayed at their actual timestamp. Preserve the
        # pre-release balance for battles that occurred before the migration.
        legacy_balance = self.now < self.data.get("economy85_from", 0)
        if group == "defenses":
            race_id = "swarm" if owner_id == "khar" else self._race_id(owner_id)
            specs = defenses.specs_for(race_id)
            bonuses = self._bonuses(owner_id)
            research = self._racial_research_effects(owner_id)
            result = {}
            for key, spec in specs.items():
                if owner_id != "khar" and not legacy_balance:
                    spec = fleet_balance85.defense_spec(key, spec)
                values = [t(spec[0]), t(spec[1]), *spec[2:]]
                for index, effect in ((4, "attack"), (5, "hull")):
                    values[index] = round(values[index] * (1 + bonuses.get(effect, 0)) * (1 + research.get(effect, 0)), 6)
                result[key] = tuple(values)
            return result
        if owner_id == "khar":
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in {"buildings": swarm.BUILDINGS, "ships": swarm.SHIPS, "research": swarm.RESEARCH}[group].items()}
        race_id = self._race_id(owner_id)
        specs = RACES[race_id][group] if race_id else {"buildings": BUILDINGS, "ships": SHIPS, "research": RESEARCH}[group]
        if group == "research":
            specs = {**specs, **{key: meta["spec"] for key, meta in technology.RESEARCH.items()}}
        if group == "buildings":
            specs = {**specs, "observatory": planetary.OBSERVATORY_SPEC, expeditions.KEY: expeditions.SPEC}
        if group == "buildings" and race_id:
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in {**specs, **{key: meta["spec"] for key, meta in UNIQUE_BUILDINGS[race_id].items()}}.items()}
        if group == "research" and race_id:
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in {**{key: meta["spec"] for key, meta in UNIQUE_RESEARCH[race_id].items()}, **specs}.items()}
        if group != "ships":
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in specs.items()}
        bonuses = self._bonuses(owner_id)
        result = {}
        research = self._racial_research_effects(owner_id)
        for key, spec in specs.items():
            if not legacy_balance:
                spec = fleet_balance85.ship_spec(key, race_id, spec)
            values = [t(spec[0]), t(spec[1]), *spec[2:]]
            for index, effect in ((4, "attack"), (5, "hull"), (6, "capacity"), (8, "flight_speed")):
                values[index] = round(values[index] * (1.0 + bonuses.get(effect, 0)) * (1.0 + research.get(effect, 0)), 6)
            values[7] = round(values[7] * (1.0 - bonuses.get("fuel_efficiency", 0)) * (1.0 - research.get("fuel_efficiency", 0)), 6)
            if key in fleet_expansion.CAPITAL_ROLES:
                values[4] = round(values[4] * (1 + self._technology_effects(owner_id).get("capital_attack", 0)), 6)
            result[key] = tuple(values)
        return result

    def _unit_construction_cost(self, owner_id, key, spec, *, stationary=False):
        """Current unit price for wreck valuation, including mixed coalitions.

        Player units use the same authority as purchases. Khar retains its own
        NPC economy and must never inherit player OGame prices. Historical
        battles retain their original raw-price wreck valuation.
        """
        if owner_id == "khar" or self.now < self.data.get("economy85_from", 0):
            return dict(zip(RESOURCES, spec[2]))
        return ogame_economy.cost("defenses" if stationary else "ships", key,
                                 spec[2], 0, resource_cap=MAX_RESOURCE)

    def _ship_traits(self, owner_id):
        return fleet_expansion.traits(self._race_id(owner_id))

    def _ship_round_factors(self, owner_id, round_no):
        return fleet_expansion.round_factors(self._race_id(owner_id), round_no)

    def _race_choice_reason(self, player_id):
        if self._race_id(player_id):
            return t('Rasa tego imperium została już wybrana.')
        owned_ids = {p["id"] for p in self.data["planets"].values() if p["owner_id"] == player_id}
        if any(p["queue"] for p in self.data["planets"].values() if p["id"] in owned_ids):
            return t('Poczekaj na zakończenie wszystkich projektów przed wyborem rasy.')
        if any(f["owner_id"] == player_id or f["target_id"] in owned_ids for f in self.data["fleets"].values()):
            return t('Poczekaj na zakończenie własnych lotów i misji do twoich planet przed wyborem rasy.')
        return ""

    def energy(self, p, *, traits_enabled=True, economy85_enabled=True):
        b = p["buildings"]
        rules = self._rules(p["owner_id"])
        power_bonus = planet_traits.multiplier(p, "power") if traits_enabled else 1
        modern = economy85_enabled and p["owner_id"] != "khar"
        reduction = ((1 - self._building_effects(p).get("mining_energy_reduction", 0))
                     * (1 - self._technology_effects(p["owner_id"]).get("mining_energy_reduction", 0)))
        if modern:
            supply = economy85.power_supply(b["power_plant"], rules, power_bonus)
            used = sum(economy85.mine_use(key, b[key], rules, reduction)
                       for key in rules["energy_use_per_level"])
        else:
            # Historical offline intervals and the Khar NPC keep their prior rules.
            supply = b["power_plant"] * rules["energy_supply_per_level"] * power_bonus
            used = sum(b[key] * amount for key, amount in rules["energy_use_per_level"].items()) * reduction
        supply += self._dyson_power(p)
        if p["owner_id"] != "khar":
            # Without this small energy reserve, the first level of a mine
            # would produce zero resources when no power plant exists yet.
            supply += STARTER_ENERGY_SUPPLY
        used = round(used, 6)
        return {"supply": supply, "used": used, "factor": min(1.0, supply / used) if used else 1.0}

    def storage(self, p):
        race_id = self._race_id(p["owner_id"])
        key = economy85.VAULTS.get(race_id, "")
        meta = UNIQUE_BUILDINGS.get(race_id, {}).get(key)
        return economy85.storage(p, race_id, MAX_RESOURCE,
                                 vault_base=meta["spec"][2] if meta else None)

    def production(self, p, *, traits_enabled=True, terrain_enabled=True, at=None,
                   ogame_enabled=True, economy85_enabled=True):
        """Player mines plus passive colony income; preserve historical and Khar rates."""
        if (self.now if at is None else at) >= self._production_cutoff(p["owner_id"]):
            return dict.fromkeys(RESOURCES, 0.0)
        factor = self.energy(p, traits_enabled=traits_enabled, economy85_enabled=economy85_enabled)["factor"] * self.speed * ECONOMY_MULTIPLIER * (1 + self._technology_effects(p["owner_id"]).get("production_all", 0))
        multipliers = self._rules(p["owner_id"])["production_multipliers"]
        effects = self._building_effects(p)
        modern = ogame_enabled and p["owner_id"] != "khar"
        # Mine output starts at level one. The passive colony income is added
        # separately below, without energy, faction, terrain or research bonuses.
        # Pre-OGame intervals and Khar NPCs retain their historical formulas.
        production_specs = (("metal", "metal_mine", 0, 300),
                            ("crystal", "crystal_mine", 0, 200),
                            ("fuel", "refinery", 0, 100)) if modern else (
                            ("metal", "metal_mine", 90, 450),
                            ("crystal", "crystal_mine", 60, 330),
                            ("fuel", "refinery", 30, 180))
        rates = {resource: (base + per_level * p["buildings"][key] * (1.1 ** p["buildings"][key] if modern else 1)) * factor * multipliers[resource]
                * (1 + effects.get("production_all", 0)) * (1 + effects.get("production_" + resource, 0)) * (planetary.multipliers(p, traits_enabled)[resource] if terrain_enabled else
                   planet_traits.multiplier(p, resource) if traits_enabled else 1)
                for resource, key, base, per_level in production_specs}
        if economy85_enabled and p["owner_id"] != "khar":
            full = self.storage(p)["full"]
            rates = {resource: 0.0 if full[resource] else rate + economy85.PASSIVE_PRODUCTION[resource] * self.speed
                     for resource, rate in rates.items()}
        return rates

    def _produce(self, dt, start_at=None):
        if dt <= 0:
            return
        start = self.now if start_at is None else start_at
        self._advance_megastructures(start, start + dt)
        for p in self.data["planets"].values():
            if p["owner_type"] == "empty":
                continue
            elapsed = dt
            if p["owner_id"] == "khar":
                # A freshly migrated fortress cannot earn the old offline
                # interval. Player production and existing deadlines are intact.
                elapsed = max(0.0, start + dt - max(start, p.get("swarm_established_at", start)))
            # Settle time before this update at the old rate once, not retroactively
            # at 1/10. Existing stocks, queues and refunds are never divided.
            actual_start = start + dt - elapsed
            old_elapsed = min(elapsed, max(0.0, self.data.get("economy_slow_from", 0) - actual_start))
            weighted_elapsed = old_elapsed / ECONOMY_MULTIPLIER + (elapsed - old_elapsed)
            # Clip at the account's exact real-time inactivity deadline. All
            # colonies share it; existing stocks and scheduled events survive.
            end = min(start + dt, self._production_cutoff(p["owner_id"]))
            if end <= actual_start:
                continue
            # Split at release epochs. New deposits/geothermal power never
            # grant retroactive income for offline time preceding the migration.
            epochs = [self.data.get(key, 0) for key in
                      ("economy_slow_from", "planetary_from", "planet_traits_from", "ogame_economy_from", "economy85_from")]
            boundaries = sorted({actual_start, end, *(at for at in epochs if actual_start < at < end)})
            for left, right in zip(boundaries, boundaries[1:]):
                midpoint = (left + right) / 2
                economy85_active = midpoint >= epochs[4] and p["owner_id"] != "khar"
                rates = self.production(p, traits_enabled=midpoint >= epochs[2], terrain_enabled=midpoint >= epochs[1], at=midpoint,
                                        ogame_enabled=midpoint >= epochs[3], economy85_enabled=economy85_active)
                weight = 1 / ECONOMY_MULTIPLIER if midpoint < epochs[0] else 1
                capacity = self.storage(p)["capacity"] if economy85_active else dict.fromkeys(RESOURCES, MAX_RESOURCE)
                for k, rate in rates.items():
                    # Cargo, loot and refunds may exceed storage. Never delete
                    # those resources: only new mining stops at the capacity.
                    if rate > 0 and p["resources"][k] < capacity[k]:
                        p["resources"][k] = min(capacity[k], p["resources"][k] + rate * (right - left) * weight / 3600)
            if p["owner_id"] == "khar" and self._swarm_ready(p):
                p["swarm_loot_sealed"] = False
                stage = swarm.kind(p)
                # Rare production follows real time, never the testing speed.
                stock = p.get("swarm_crystals", 0) + weighted_elapsed / swarm.CRYSTAL_REGEN_SECONDS
                if abs(stock - round(stock)) < 1e-9:
                    stock = float(round(stock))
                p["swarm_crystals"] = min(swarm.CRYSTAL_CAPS[stage], stock)

    @atomic_mutation
    def advance(self, now=None):
        """Set real UNIX time, settle existing events in order, then one NPC decision.

        Offline production and scheduled flights complete exactly once. NPC decisions
        are deliberately not replayed over the offline interval, avoiding instant
        galaxy-wide colonization after a server restart.
        """
        with self.lock:
            now = float(time.time() if now is None else now)
            if not math.isfinite(now):
                raise ValueError("now must be finite")
            now = max(now, self.data["last_update"])
            cursor = self.data["last_update"]
            self.now = cursor
            self._ensure_protection_notices()
            self._expire_protection_notices()
            self._start_planned_projects()
            while True:
                deadlines = [task["ends_at"] for p in self.data["planets"].values() for task in p["queue"]]
                deadlines.extend(f["arrives_at"] for f in self.data["fleets"].values())
                deadlines.extend(self._mega_deadlines())
                deadlines.extend(self._alliance_deadlines())
                deadlines.extend(self._protection_deadlines())
                deadlines.extend(self._planned_queue_deadlines(cursor, now))
                deadline = min(deadlines, default=float("inf"))
                if deadline > now:
                    break
                event_time = max(cursor, deadline)
                self._produce(event_time - cursor, start_at=cursor)
                cursor = event_time
                self.now = event_time
                rankings.accrue_rewards(self, event_time)
                self._expire_protection_notices()
                self._complete_megastructures(event_time)
                for p in self.data["planets"].values():
                    while any(task["ends_at"] <= event_time for task in p["queue"]):
                        self._complete_queue(p)
                self._advance_alliance_operations()
                for fid in list(self.data["fleets"]):
                    fleet = self.data["fleets"].get(fid)
                    if fleet and fleet["arrives_at"] <= event_time:
                        self._complete_fleet(fleet)
                self._start_planned_projects()
            self._produce(now - cursor, start_at=cursor)
            self.now = now
            rankings.accrue_rewards(self, now)
            self._start_planned_projects()
            self.data["last_update"] = now
            if now >= self.data["alien"]["next_expansion_at"]:
                self._alien_turn()
                self.data["alien"]["next_expansion_at"] = now + max(8, 120 / self.speed)
            self.db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            self._save()

    def _complete_queue(self, p):
        if not p["queue"]:
            return
        # Parallel lanes finish by deadline, independent of purchase order.
        task = min(p["queue"], key=lambda task: task["ends_at"])
        p["queue"].remove(task)
        grown = 0
        if task["kind"] == "build":
            p["buildings"][task["key"]] = task["level"]
        elif task["kind"] == "defense":
            produced = task["amount"]  # No Symbiont fleet multiplication for structures.
            p.setdefault("defenses", {})[task["key"]] = p.get("defenses", {}).get(task["key"], 0) + produced
        elif task["kind"] == "ship":
            produced = self._produced_ships(p["owner_id"], task["key"], task["amount"])
            p["ships"][task["key"]] = p["ships"].get(task["key"], 0) + produced
        else:
            player = self.data["players"][p["owner_id"]]
            old_level = player["research"].get(task["key"], 0)
            new_level = max(old_level, task["level"])
            player["research"][task["key"]] = new_level
            if task["key"] == "multiplication":
                grown = self._multiply_existing_fleet(p["owner_id"], old_level, new_level)
            # Fixed at purchase, paid once at completion, never from Swarm currency.
            refund = int(task.get("crystal_refund", 0))
            p["resources"]["crystal"] = min(MAX_RESOURCE, p["resources"]["crystal"] + refund)
        construction_refund = task.get("construction_refund", {}) if task["kind"] in ("build", "ship", "defense") else {}
        received = {}
        for resource in RESOURCES:
            refund = max(0, int(construction_refund.get(resource, 0)))
            before = p["resources"][resource]
            p["resources"][resource] = min(MAX_RESOURCE, before + refund)
            received[resource] = int(p["resources"][resource] - before)
        if p["owner_type"] == "player":
            if task["kind"] == "build":
                review_invite.record_completed_build(self._player(p["owner_id"]))
            if task["kind"] == "build" and task["key"] in BUILDINGS:
                onboarding.record(self._player(p["owner_id"]), "first_building")
            names = self._specs(p["owner_id"], {"build": "buildings", "ship": "ships", "defense": "defenses", "research": "research"}[task["kind"]])
            self._report(p["owner_id"], t('Ukończono projekt'), t('{0}: {1}').format(p['name'], names[task['key']][0]) + (t(' ×{0}.').format(produced) if task["kind"] in ("ship", "defense") else t(', poziom {0}.').format(task['level'])), report_kind=report_kinds.PROJECT_KINDS.get(task["kind"]))
            if task["kind"] == "research" and task["key"] in UNIQUE_RESEARCH.get(self._race_id(p["owner_id"]), {}):
                effect = research_effect_text(task["key"], new_level)
                if task["key"] == "multiplication":
                    effect += t('. Przybyło {0} statków w koloniach i podróży.').format(grown)
                self._report(p["owner_id"], names[task["key"]][0], effect + t(' Działa w całym imperium.'), art_key(self._race_id(p["owner_id"]), task["key"]))
            if any(received.values()):
                self._report(p["owner_id"], t('Recykling'), t('{0}: odzyskano {1} metalu, {2} kryształów i {3} paliwa.').format(p['name'], received['metal'], received['crystal'], received['fuel']), art_key("automatons", "recycling"))
            if task.get("crystal_refund", 0):
                self._report(p["owner_id"], t('Archiwum Synaps'), t('{0}: ukończone badanie zwróciło {1} zwykłych kryształów.').format(p['name'], task['crystal_refund']), art_key(self._race_id(p["owner_id"]), "synapse_archive"))

    @staticmethod
    def _credentials(name, password):
        if not isinstance(name, str) or not isinstance(password, str):
            raise GameError(t('Podaj nazwę i hasło.'))
        name = unicodedata.normalize("NFKC", name.strip())
        if not 3 <= len(name) <= 20 or not all(c.isalnum() or c in " _-" for c in name):
            raise GameError(t('Nazwa musi mieć 3–20 znaków: litery, cyfry, spacje, _ lub -.'))
        if not 8 <= len(password) <= 128:
            raise GameError(t('Hasło musi mieć 8–128 znaków.'))
        return name, password

    @staticmethod
    def _password_hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 240_000).hex()

    def _session(self, player_id):
        self._touch_player_activity(player_id)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.db.execute("INSERT INTO sessions VALUES(?,?,?)", (token_hash, player_id, self.now + 30 * 86400))
        self.db.execute("DELETE FROM sessions WHERE player_id=? AND token_hash NOT IN (SELECT token_hash FROM sessions WHERE player_id=? ORDER BY expires DESC LIMIT 10)", (player_id, player_id))
        return token

    def _available_start_planets(self):
        """Only allow new empires in wholly empty systems without arriving colonizers."""
        reserved = {f["target_id"] for f in self.data["fleets"].values()
                    if f["mission"] == "colonize" and f["status"] == "outbound"}
        blocked_systems = {p["system_id"] for p in self.data["planets"].values()
                           if p["owner_type"] != "empty" or p["id"] in reserved}
        return [p for p in self.data["planets"].values()
                if p["owner_type"] == "empty" and p["system_id"] not in blocked_systems]

    def _choose_start_planet(self, available):
        # A vacant planet in a settled system is not a valid starting world.
        # Reserve entire systems targeted by outbound colonization fleets.
        legal_ids = {p["id"] for p in self._available_start_planets()}
        available = [p for p in available if p["id"] in legal_ids]
        if not available:
            raise GameError(t('W galaktyce nie ma już wolnej planety startowej.'), 409)
        order = {key: index for index, key in enumerate(GALAXIES_BY_ID)}
        settled_systems = {p["system_id"] for p in self.data["planets"].values()
                           if p["owner_type"] != "empty"}
        totals, occupied = defaultdict(int), defaultdict(int)
        for system in self.data["systems"]:
            galaxy = system.get("galaxy_id", inferred_id(system["id"]))
            totals[galaxy] += 1
            occupied[galaxy] += system["id"] in settled_systems
        candidates = sorted({self._galaxy_id(p) for p in available},
                            key=lambda key: (order.get(key, len(order)), key))
        below_half = [key for key in candidates if occupied[key] * 2 < totals[key]]
        # At 50% of star systems (not planets), move to the next galaxy.
        # Player and Khar settlements count; outbound reservations do not.
        # If all galaxies have reached 50%, choose the least occupied one.
        chosen_galaxy = below_half[0] if below_half else min(
            candidates, key=lambda key: Fraction(occupied[key], totals[key]))
        local = [p for p in available if self._galaxy_id(p) == chosen_galaxy]
        roomy = [p for p in local if planetary.fields(p)["total"] >= 86]
        return secrets.choice(roomy or local)

    def _initialize_starter_colony(self, pid, name, planet, race_id=""):
        """One canonical starting balance, shared by signup and the 0.7.2 reset."""
        race_id = race_id if race_id in RACES else ""
        player = {"id": pid, "name": name, "race_id": race_id, "swarm_crystals": 0,
                  "last_active_at": self.now,
                  "skill_nodes": skill_tree.unlocked_for(race_id, []), "home_id": planet["id"],
                  "protected_until": self.now + PROTECTION_SECONDS,
                  "protection_duration_version": PROTECTION_DURATION_VERSION,
                  "research": dict.fromkeys(RESEARCH, 0),
                  "reports": [], "requests": {}, "scout_intel": {}}
        player["planned_orders"] = []
        review_invite.ensure(player)
        self.data["players"][pid] = player
        planet["owner_type"], planet["owner_id"] = "player", pid
        planet["buildings"] = dict.fromkeys(BUILDINGS, 0)
        planet["buildings"]["observatory"] = 0
        player.update(system_intel={}, planet_intel={})
        planet["resources"] = {"metal": 500.0, "crystal": 500.0, "fuel": 0.0}
        planet["ships"] = blank_ships()
        planet["defenses"] = {}
        planet["queue"] = []
        self._ensure_race_buildings(planet)
        self._ensure_racial_research(player)
        onboarding.ensure(self.data, player)
        self._ensure_swarm_activation()
        self._ensure_protection_notice(player)
        return player

    @atomic_mutation
    def register(self, name, password, invite="", *, _google_verified=False, _email_verified=False):
        if self.require_google_registration and not (_google_verified or _email_verified):
            raise GameError(t('Nowe imperium załóż przez Google.'), 403)
        # Older clients may still send an invitation; registration is now open.
        # The legacy field is deliberately ignored and never stored or returned.
        name, password = self._credentials(name, password)
        salt = secrets.token_hex(16)
        password_hash = self._password_hash(password, salt)
        with self.lock:
            if self.db.execute("SELECT 1 FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone():
                raise GameError(t('Ta nazwa jest już zajęta.'), 409)
            if self.max_players and len(self.data["players"]) >= self.max_players:
                raise GameError(t('Ten sektor osiągnął ustawiony przez gospodarza limit {0} kont. Jeśli masz już konto, wybierz Zaloguj.').format(self.max_players), 409)
            empty = self._available_start_planets()
            if not empty:
                raise GameError(t('W galaktyce nie ma już wolnej planety startowej.'), 409)
            p = self._choose_start_planet(empty)
            pid = ident("u")
            self._initialize_starter_colony(pid, name, p)
            self._report(pid, t('Witaj w Alien Colonies'), t(WELCOME_REPORT_TEXT))
            self.db.execute("INSERT INTO accounts VALUES(?,?,?,?)", (pid, name.casefold(), salt, password_hash))
            self._chat_register(pid)
            token = self._session(pid)
            self._save()
            return {"ok": True, "token": token, "state": self.state(pid), "message": t('Założono imperium.')}

    @atomic_mutation
    def login(self, name, password):
        name, password = self._credentials(name, password)
        with self.lock:
            row = self.db.execute("SELECT id,salt,password_hash FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone()
            salt = row[1] if row else "00" * 16
            candidate = self._password_hash(password, salt)
            if not row or not hmac.compare_digest(candidate, row[2]):
                raise GameError(t('Nieprawidłowa nazwa lub hasło.'), 401)
            token = self._session(row[0])
            return {"ok": True, "token": token, "state": self.state(row[0]), "message": t('Witaj ponownie.')}

    def authenticate(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise GameError(t('Zaloguj się ponownie.'), 401)
        with self.lock:
            row = self.db.execute("SELECT player_id FROM sessions WHERE token_hash=? AND expires>?", (hashlib.sha256(token.encode()).hexdigest(), self.now)).fetchone()
            if not row:
                raise GameError(t('Sesja wygasła. Zaloguj się ponownie.'), 401)
            return row[0]

    @atomic_mutation
    def logout(self, token):
        with self.lock:
            self.db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def _player(self, player_id):
        player = self.data["players"].get(player_id)
        if not player:
            raise GameError(t('Nie znaleziono gracza.'), 401)
        return player

    def _owned(self, player_id, planet_id=None):
        player = self._player(player_id)
        if planet_id is None:
            planet_id = player["home_id"]
        if not isinstance(planet_id, str):
            raise GameError(t('Nieprawidłowa planeta.'))
        p = self.data["planets"].get(planet_id)
        if not p or p["owner_id"] != player_id or p["owner_type"] != "player":
            raise GameError(t('Ta planeta nie należy do ciebie.'), 403)
        return p

    def _report(self, player_id, title, text, art_key="", swarm_crystals=0, *, replay=None, report_kind=None):
        player = self.data["players"].get(player_id)
        if player:
            player["reports"].insert(0, {"id": ident("r"), "at": self.now, "title": render_text(store_text(title), "pl"), "text": render_text(store_text(text), "pl"), "art_key": art_key, "swarm_crystals": swarm_crystals, "i18n": {"title": store_text(t(title)), "text": store_text(text)}})
            if replay is not None:
                player["reports"][0]["battle_replay"] = copy.deepcopy(replay)
            report = player["reports"][0]
            report["kind"] = report_kind if report_kind in report_kinds.KINDS else report_kinds.kind(report)
            push_notifications.enqueue_report(self, player_id, player["reports"][0])
            del player["reports"][80:]

    def _local_distance(self, a, b):
        return self._system_navigation_distance(a, b)

    def _distance(self, a, b):
        return self._local_distance(a, b) + separation(self._galaxy_id(a), self._galaxy_id(b)) * 1_000_000

    def _fuel_distance(self, origin, target):
        gap = separation(self._galaxy_id(origin), self._galaxy_id(target))
        same_system = origin["system_id"] == target["system_id"]
        lane_distance = 0.0
        if not gap and not same_system:
            lane_distance = self._galaxy_navigation().route(origin["system_id"], target["system_id"])["distance"]
            if lane_distance is None:
                raise ValueError("Disconnected local galaxy navigation")
        return flight_balance85.distance(galaxy_gap=gap, same_system=same_system,
                                         slot_delta=origin["slot"] - target["slot"],
                                         lane_distance=lane_distance)

    def _flight_numbers(self, origin, target, fleet, propulsion=0):
        distance = self._local_distance(origin, target)
        specs = self._specs(origin["owner_id"], "ships")
        slowest = min(specs[k][8] for k, n in fleet.items() if n)
        antigravity = 1 + .2 * self._racial_research_level(origin["owner_id"], "antigravity")
        speed_factor = slowest * (1 + propulsion * .15) * antigravity * self.speed
        local_fuel_factor = 1 - self._building_effects(origin).get("fleet_fuel_reduction", 0)
        mass = sum(specs[k][7] * n for k, n in fleet.items() if n)
        gap = separation(self._galaxy_id(origin), self._galaxy_id(target))
        if gap:
            seconds = max(8, math.ceil((JUMP_SECONDS_PER_MLY * gap + 100 + distance * 130) / speed_factor))
            # Legacy NPC cost; player fuel is replaced below. Existing fleet
            # records retain their prepaid cost and absolute arrival deadline.
            fuel = math.ceil(gap * (JUMP_BASE_FUEL + JUMP_FUEL_PER_MASS * mass * local_fuel_factor))
        else:
            seconds = max(8, math.ceil((100 + distance * 130) / speed_factor))
            fuel = max(1, math.ceil(mass * (1 + distance) * 2 * local_fuel_factor))
        if origin["owner_id"] != swarm.OWNER_ID and self.now >= self.data.get("economy85_from", 0):
            fuel = flight_balance85.fuel_cost(specs, fleet, self._fuel_distance(origin, target), local_fuel_factor)
        return seconds, fuel

    def _fleet_quote(self, player_id, payload, *, require_affordable=True):
        if payload.get("mission") == "expedition":
            return self._expedition_quote(player_id, payload, require_affordable)
        p = self._owned(player_id, payload.get("planet_id"))
        target_id = payload.get("target_id")
        if not isinstance(target_id, str) or target_id not in self.data["planets"]:
            raise GameError(t('Wybierz planetę docelową.'))
        target = self.data["planets"][target_id]
        mission = payload.get("mission")
        if mission not in ("scout", "transport", "colonize", "attack"):
            raise GameError(t('Nieznany rodzaj misji.'))
        scout_scope = payload.get("scout_scope", "planet")
        if scout_scope not in ("planet", "system") or (scout_scope == "system" and mission != "scout"):
            raise GameError(t('Nieprawidłowy zakres zwiadu.'))
        if scout_scope == "system" and payload.get("target_system_id") != target["system_id"]:
            raise GameError(t('Wybrana planeta nie należy do wskazanego układu.'))
        if target_id == p["id"] and scout_scope != "system":
            raise GameError(t('Wybierz inną planetę.'))
        if mission != "scout" and not self._known_planet(player_id, target):
            raise GameError(t("Najpierw zbadaj ten układ albo obejmij go zasięgiem obserwatorium."), 409)
        specs = self._specs(player_id, "ships")
        race_id = self._race_id(player_id)
        ships = counts(payload.get("ships"), specs, t('Liczba statków'), 10_000)
        cargo = counts(payload.get("cargo", {}), RESOURCES, t('Ładunek'), MAX_RESOURCE)
        if not sum(ships.values()):
            raise GameError(t('Wybierz przynajmniej jeden statek.'))
        if any(n > p["ships"].get(k, 0) for k, n in ships.items()):
            raise GameError(t('Nie masz tylu statków na tej planecie.'))
        if len([f for f in self.data["fleets"].values() if f["owner_id"] == player_id and f["mission"] != "expedition"]) >= 8:
            raise GameError(t('Możesz prowadzić najwyżej 8 misji naraz.'), 409)
        if mission == "scout" and ships["scout"] < 1:
            raise GameError(t('Wymagany okręt do zwiadu: {0}.').format(specs['scout'][0]) if race_id else t('Zwiad wymaga zwiadowcy.'))
        if mission == "transport" and target["owner_id"] != player_id and not self._allied(player_id, target["owner_id"]):
            raise GameError(t('Transport jest dostępny do własnych kolonii i kolonii sojuszników.'))
        if mission == "colonize":
            if ships["colonizer"] < 1:
                raise GameError(t('Kolonizacja wymaga okrętu {0}.').format(specs['colonizer'][0]))
            blocked = self._colonization_block(player_id, target)
            if blocked:
                raise GameError(blocked, 409)
            colonies = sum(q["owner_id"] == player_id for q in self.data["planets"].values())
            pending = sum(f["owner_id"] == player_id and f["mission"] == "colonize" and f["status"] == "outbound" for f in self.data["fleets"].values())
            if colonies + pending >= MAX_COLONIES:
                raise GameError(t('Limit to {0} kolonii, wliczając wysłane ekspedycje.').format(MAX_COLONIES), 409)
        if mission == "attack":
            if not any(ships.get(key, 0) for key in fleet_expansion.COMBAT_ROLES):
                raise GameError(t('Do ataku potrzebny jest co najmniej jeden okręt bojowy.'))
            if target["owner_type"] == "empty" or target["owner_id"] == player_id:
                raise GameError(t('Możesz atakować obce kolonie lub innych graczy.'))
            if self._alliance_attack_block(player_id, target["owner_id"]):
                raise GameError(t('Nie można atakować sojusznika ani byłego sojusznika w czasie rozejmu.'), 403)
            if target["owner_type"] == "player" and self._player(target["owner_id"])["protected_until"] > self.now:
                raise GameError(t('Ten gracz jest objęty ochroną startową.'), 403)
        if mission not in ("transport", "colonize") and sum(cargo.values()):
            raise GameError(t('Ładunek można zabrać na transport lub kolonizację.'))
        capacity = fleet_capacity(specs, ships)
        if sum(cargo.values()) > capacity:
            raise GameError(t('Ładunek przekracza pojemność {0}.').format(capacity))
        seconds, fuel = self._flight_numbers(p, target, ships, self._player(player_id)["research"]["propulsion"])
        effects = self._building_effects(p)
        if mission == "scout":
            seconds = max(8, math.ceil(seconds * (1 - effects.get("scout_time_reduction", 0))))
        travel_mode = payload.get("travel_mode", "normal")
        if travel_mode not in ("normal", "tunnel"):
            raise GameError(t("Nieznany sposób podróży."))
        if travel_mode == "tunnel":
            tunnel = self._tunnel_quote(player_id, p, target, ships, cargo, require_affordable)
            seconds, fuel = tunnel["seconds"], 0
        cost = dict(cargo)
        cost["fuel"] += fuel
        if require_affordable and not affordable(p, cost):
            raise GameError(t('Brakuje zapasów. Lot wymaga {0} paliwa, oprócz zabieranego ładunku.').format(fuel))
        return p, target, ships, cargo, cost, seconds, fuel, capacity

    def preview(self, player_id, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise GameError(t('Nieprawidłowe dane misji.'))
            p, target, ships, cargo, cost, seconds, fuel, capacity = self._fleet_quote(player_id, payload, require_affordable=payload.get("allow_unaffordable") is not True)
            result = {"ok": True, "fuel_cost": fuel, "seconds": seconds, "capacity": capacity, "message": t('Paliwo obejmuje podróż w obie strony.')}
            result["route"] = self._route_details(p, target)
            if payload.get("mission") == "expedition":
                result["expedition"] = self._expedition_preview(player_id, p, payload, seconds)
                result["round_trip_seconds"] = result["expedition"]["round_trip_seconds"]
                result["return_at"] = self.now + result["round_trip_seconds"]
            if payload.get("mission") == "scout":
                result.update(scout_scope=payload.get("scout_scope", "planet"), target_system_id=target["system_id"])
            result["affordable"] = affordable(p, cost)
            result["shortfall"] = {k: max(0, math.ceil(v - p["resources"][k])) for k, v in cost.items()}
            if payload.get("travel_mode") == "tunnel":
                tunnel = self._tunnel_quote(player_id, p, target, ships, cargo, False)
                result["tunnel"] = tunnel
                result["route"]["travel_mode"] = "tunnel"
                result["affordable"] = result["affordable"] and tunnel["affordable"]
                result["message"] = t("Tunel: energia {0}, w tym rezerwa powrotu {1}. Zamknięcie okna nie blokuje powrotu floty.").format(tunnel["energy_cost"], tunnel["return_reserved"])
            elif result["route"]["intergalactic"]:
                result["message"] += " " + t('Lot między galaktykami: koszt zależy od dystansu i składu floty. Cała kwota jest pobierana przy starcie; powrót nie wymaga dopłaty.')
            if payload.get("mission") == "colonize":
                result["colonization_kind"] = "capture" if target["owner_type"] == "player" else "settle"
                result["colonization_warning"] = t(COLONIZATION_WARNING)
                if target["owner_type"] == "empty":
                    result["colony_start_level"] = self._colony_start_level(player_id, self._building_effects(p))
                    if result["colony_start_level"] > 1:
                        result["message"] += t(' Nowa kolonia: cztery budynki gospodarcze na poziomie {0}.').format(result['colony_start_level'])
                else:
                    result["message"] += " " + t('Przejęcie zachowa istniejące budynki i zapasy. Obce budynki rasowe pozostaną nieaktywne.')
                result["message"] += " " + result["colonization_warning"]
            elif payload.get("mission") == "attack" and self._known_planet(player_id, target) and target["owner_id"] == "khar":
                intel = self._public_swarm_intel(player_id, target)
                result["message"] += " " + t("Wyślij zwiad, aby poznać obronę i zapasy Roju.") if not intel.get("has_scout") else " " + t("Zapasy według ostatniego zwiadu: {0} Kryształów Roju.").format(intel["swarm_crystals_stock"])
                if intel.get("has_scout"):
                    result["scouted_at"] = intel["scouted_at"]
            return result

    def _colonization_block(self, owner, target):
        """Use live ownership and defenses both before dispatch and on arrival."""
        if target["owner_type"] == "empty":
            return ""
        if owner not in self.data["players"] or target["owner_type"] != "player":
            return t('Nie można kolonizować zajętej planety Roju Khar.')
        if target["owner_id"] == owner:
            return t('Ta planeta już należy do twojego imperium.')
        defender = self.data["players"].get(target["owner_id"])
        if defender is None:
            return t('Ta planeta nie jest dostępna do kolonizacji.')
        if defender["home_id"] == target["id"]:
            return t('Nie można przejąć planety macierzystej innego imperium.')
        if self._alliance_attack_block(owner, target["owner_id"]):
            return t('Nie można przejąć kolonii sojusznika ani byłego sojusznika w czasie rozejmu.')
        if defender.get("protected_until", 0) > self.now:
            return t('Ten gracz jest objęty ochroną startową.')
        if (any(n > 0 for n in target["ships"].values())
                or any(n > 0 for n in target.get("defenses", {}).values())
                or any(any(n > 0 for n in f["ships"].values())
                       for f in self._alliance_supports_at(target))
                or any(f["status"] == "returning" and f["owner_id"] == target["owner_id"]
                       and f["origin_id"] == target["id"] and f["arrives_at"] <= self.now
                       and any(n > 0 for n in f["ships"].values())
                       for f in self.data["fleets"].values())):
            return t('Kolonię można przejąć tylko przy braku floty, obrony planetarnej i wsparcia sojuszników.')
        return ""

    def _capture_colony(self, target, owner):
        """Transfer settled structures, never the former empire's active work."""
        previous = self._player(target["owner_id"])
        home = self.data["planets"][previous["home_id"]]
        tasks = list(target["queue"])
        target["queue"] = []
        orders = previous.get("planned_orders", [])
        removed_plans = any(order["planet_id"] == target["id"] for order in orders)
        previous["planned_orders"] = [order for order in orders if order["planet_id"] != target["id"]]
        mega = previous.get("megastructure", {})
        suspended_mega = mega.get("origin_id") == target["id"]
        if suspended_mega:
            if mega.get("queue"):
                tasks.append(mega["queue"])
            mega["queue"] = None
            mega["window"] = None
            if not mega.get("dyson_stage", 0):
                # As with ordinary megacancel, a refunded first foundation
                # leaves no completed structure anchoring the former empire.
                mega["origin_id"] = ""
                suspended_mega = False
        refunded = dict.fromkeys(RESOURCES, 0)
        for task in tasks:
            paid = task.get("paid_cost")
            # Refund only the historical, authoritative purchase price. Legacy
            # projects without a saved price cannot be recalculated or rewarded.
            if (not isinstance(paid, dict) or set(paid) != set(RESOURCES)
                    or any(type(v) is not int or v < 0 for v in paid.values())):
                continue
            for resource in RESOURCES:
                before = home["resources"][resource]
                home["resources"][resource] = min(MAX_RESOURCE, before + paid[resource])
                refunded[resource] += int(home["resources"][resource] - before)
        target["owner_id"] = owner
        target["owner_type"] = "player"
        self._ensure_race_buildings(target)
        # The dispossessed empire knows who captured this colony. Refresh only
        # its identity, not neighboring worlds or a later view of the garrison.
        self._remember_trait(previous["id"], target, "capture")
        record = previous.get("system_intel", {}).get(target["system_id"], {})
        if record:
            identity = self._planet_identity(target)
            record["planets"] = [identity if item["id"] == target["id"] else item
                                 for item in record.get("planets", [])]
        lost = t('Imperium {0} przejęło niebronioną kolonię {1}. Budynki i zapasy pozostały na planecie. Możesz ją odzyskać kolonizatorem, gdy pozostanie bez obrony.').format(self._player(owner)["name"], target["name"])
        if tasks or removed_plans:
            lost += " " + t('Anulowano niedokończone projekty i planowane zlecenia tej kolonii. Na planetę macierzystą zwrócono {0} metalu, {1} kryształów i {2} paliwa.').format(refunded["metal"], refunded["crystal"], refunded["fuel"])
        if suspended_mega:
            lost += " " + t('Megastruktura pozostaje nieaktywna do odzyskania kolonii. Otwarte połączenie tunelowe zamknięto; wysłane floty zachowują opłacony powrót.')
        self._report(previous["id"], t('Utracono kolonię'), lost)
        return previous["id"]

    def _colony_start_level(self, owner_id, effects):
        # Only new dispatches record this bonus. Legacy fuel-discount snapshots
        # never turn into free building levels, even if the nursery was upgraded.
        bonus = effects.get("colony_start_building_bonus", 0) if self._race_id(owner_id) == "symbionts" else 0
        return 1 + max(0, min(5, int(bonus)))

    @staticmethod
    def _regeneration_fraction(rules, *, defense_effects=None):
        # Only the attacked planet's current Grove can heal its stationed ships.
        # Travelling fleets retain innate/skill regeneration, never a Grove bonus.
        bonus = (defense_effects or {}).get("renewal_fraction", 0)
        return max(0.0, min(1.0, rules["regeneration_fraction"] + bonus))

    def _project_timing(self, player_id, planet, group, key, level):
        """Catalog, details and new orders use one duration and factor profile."""
        spec = self._specs(player_id, group)[key]
        effects = self._building_effects(planet)
        skill_bonus = self._bonuses(player_id).get(
            "research_speed" if group == "research" else "build_speed", 0)
        common_key = "research_speed" if group == "research" else "ship_build_speed" if group in ("ships", "defenses") else "build_speed"
        skill_bonus += self._technology_effects(player_id).get(common_key, 0)
        historical = self.now < self.data.get("economy85_from", 0)
        if historical and group == "buildings":
            # v84 Robotics was an additive +4%/level, not the v85 factor.
            skill_bonus += round(self._technology_effects(player_id).get("robotics_speed", 0) * .04, 6)
        reduction = (effects.get("building_time_reduction", 0) if group == "buildings" else
                     effects.get("ship_time_reduction", 0) if group in ("ships", "defenses") else 0)
        return ogame_economy.project_timing(group, ogame_economy.cost(group, key, spec[2], level, resource_cap=MAX_RESOURCE),
                   planet["buildings"], self.speed, skill_bonus, reduction,
                   local_speed=planet_traits.multiplier(planet, "research_speed") if group == "research" else 1,
                   research_levels=self._player(player_id)["research"],
                   target_level=level + 1 if group in ("buildings", "research") else None,
                   rules_version=84 if historical else 85)

    def _project_seconds(self, player_id, planet, group, key, level):
        return self._project_timing(player_id, planet, group, key, level)["seconds"]

    def _catalog_detail_preview(self, player_id, planet, group, item):
        """Read-only numeric UI preview; uses the same production/requirements as orders.

        Clone ONLY the local building levels. Never complete a project, grant a
        skill, alter a queue, or change a live planet while rendering the catalog.
        """
        key, level = item["key"], int(item["level"])
        maximum = int(item.get("max_level", 0))
        has_next = group in ("buildings", "research") and level < maximum
        result = {"schema": 2, "metrics": [], "notes": []}

        def metric(label, current, following=None, unit="number"):
            result["metrics"].append({"key": label, "current": round(float(current), 6),
                                      "next": round(float(following), 6) if has_next and following is not None else None,
                                      "unit": unit})

        if group == "buildings":
            future = dict(planet)
            future["buildings"] = dict(planet["buildings"])
            future["buildings"][key] = level + 1 if has_next else level
            energy, next_energy = self.energy(planet), self.energy(future)
            rates, next_rates = self.production(planet), self.production(future)
            if "production_resource" in item:
                resource = item["production_resource"]
                # Keep the mine contribution separate from total colony output,
                # which also includes passive production and storage limits.
                metric("mine_" + resource, level * item["production_per_level"] * energy["factor"],
                       (level + 1) * item["production_next_per_level"] * next_energy["factor"], "per_hour")
                metric("colony_" + resource, rates[resource], next_rates[resource], "per_hour")
                metric("energy_use", item["energy_use_current"], item["energy_use_next"])
                metric("energy_efficiency", 100 * energy["factor"], 100 * next_energy["factor"], "percent")
                result["notes"] = ["production_actual", "next_local_only"]
            elif key == "power_plant":
                metric("energy_supply", energy["supply"], next_energy["supply"])
                metric("energy_efficiency", 100 * energy["factor"], 100 * next_energy["factor"], "percent")
                for resource in RESOURCES:
                    metric("colony_" + resource, rates[resource], next_rates[resource], "per_hour")
                result["notes"] = ["next_local_only"]
            elif key in ("shipyard", "lab"):
                groups = ("ships", "defenses") if key == "shipyard" else ("research",)
                available_now, available_next, milestones = [], [], []
                for target_group in groups:
                    for target_key, spec in self._specs(player_id, target_group).items():
                        current_reqs = self._entry_requirements(player_id, planet, target_group, target_key)
                        next_reqs = self._entry_requirements(player_id, future, target_group, target_key)
                        if all(req["met"] for req in current_reqs):
                            available_now.append(spec[0])
                        if all(req["met"] for req in next_reqs):
                            available_next.append(spec[0])
                        for req in current_reqs:
                            if req["group"] == "buildings" and req["key"] == key:
                                milestones.append({"name": spec[0], "level": req["level"],
                                                   "other_requirements_met": all(r["met"] for r in current_reqs if r is not req)})
                metric("shipyard_projects" if key == "shipyard" else "research_projects", len(available_now), len(available_next))
                result["available_now"] = available_now
                result["unlocks_next"] = [name for name in available_next if name not in available_now] if has_next else []
                result["milestones"] = sorted(milestones, key=lambda row: (row["level"], str(row["name"])))
                timing_group = "ships" if key == "shipyard" else "research"
                now_timing = ogame_economy.facility_profile(planet["buildings"], timing_group)
                next_timing = ogame_economy.facility_profile(future["buildings"], timing_group)
                # Facility-only bonuses are separate from the final example times,
                # which include skills, racial facilities and the server tempo.
                metric("shipyard_speed_bonus" if key == "shipyard" else "lab_speed_bonus",
                       now_timing["speed_bonus_percent"], next_timing["speed_bonus_percent"], "percent")
                metric("facility_time_reduction", now_timing["time_reduction_percent"],
                       next_timing["time_reduction_percent"], "percent")
                result["notes"] = ["shipyard_speed_rule" if key == "shipyard" else "lab_speed_rule",
                                   "facility_time_scope"]
                samples = [("ships", "scout")] if key == "shipyard" else [("research", "propulsion")]
                if key == "shipyard":
                    samples += [("defenses", defense_key) for defense_key in self._specs(player_id, "defenses")]
                result["time_examples"] = []
                for sample_group, sample_key in samples:
                    sample_level = self._player(player_id)["research"].get(sample_key, 0) if sample_group == "research" else 0
                    if sample_group == "research" and sample_level >= 12:
                        continue  # No new order exists at the completed research cap.
                    spec = self._specs(player_id, sample_group)[sample_key]
                    now_ready = all(r["met"] for r in self._entry_requirements(player_id, planet, sample_group, sample_key))
                    next_ready = all(r["met"] for r in self._entry_requirements(player_id, future, sample_group, sample_key))
                    result["time_examples"].append({"key": sample_key, "group": sample_group, "name": spec[0],
                        "current_seconds": self._project_seconds(player_id, planet, sample_group, sample_key, sample_level) if now_ready else None,
                        "next_seconds": self._project_seconds(player_id, future, sample_group, sample_key, sample_level) if next_ready and has_next else None,
                        "has_next": has_next})
            elif item.get("unique"):
                # Current/next bonus strings are already derived from faction rules.
                # Production/energy structures also show the colony's real totals.
                effect = UNIQUE_BUILDINGS.get(self._race_id(player_id), {}).get(key, {}).get("effect", "")
                if key == economy85.VAULTS.get(self._race_id(player_id)):
                    metric("storage_capacity", self.storage(planet)["capacity"]["metal"],
                           self.storage(future)["capacity"]["metal"])
                    for resource in RESOURCES:
                        metric("colony_" + resource, rates[resource], next_rates[resource], "per_hour")
                    result["notes"] = ["storage_per_resource"]
                if effect in ("production_all", "production_metal", "mining_energy_reduction"):
                    for resource in RESOURCES:
                        metric("colony_" + resource, rates[resource], next_rates[resource], "per_hour")
                    metric("energy_efficiency", 100 * energy["factor"], 100 * next_energy["factor"], "percent")
                    result["notes"] = ["next_local_only"]
        elif group == "research" and key in ("propulsion", "weapons"):
            bonus_percent = 15 if key == "propulsion" else 100 * fleet_balance85.WEAPONS_PER_LEVEL
            metric("fleet_speed_bonus" if key == "propulsion" else "fleet_attack_bonus", bonus_percent * level, bonus_percent * (level + 1), "percent")
            result["notes"] = ["research_bonus_only"]
        return result

    def _catalog(self, player_id, p, project_only=None):
        player = self._player(player_id)
        result = {"buildings": [], "research": [], "ships": [], "defenses": []}
        race_id = self._race_id(player_id)
        rules = self._rules(player_id)
        effects = self._building_effects(p)
        busy = {production_timing.project_lane(task["kind"]) for task in p["queue"]}
        research_busy = any(task["kind"] == "research" for colony in self.data["planets"].values()
                            if colony["owner_id"] == player_id for task in colony["queue"])
        planning_context = self._planning_context(player_id, p)
        storage_capacity = (self.storage(p)["capacity"]
                            if self.now >= self.data.get("economy85_from", 0)
                            else dict.fromkeys(RESOURCES, MAX_RESOURCE))
        for group in ("buildings", "research", "ships", "defenses"):
            if project_only is not None and group != project_only[0]:
                continue
            for key, spec in self._specs(player_id, group).items():
                if project_only is not None and key != project_only[1]:
                    continue
                level = (p["buildings"] if group == "buildings" else player["research"] if group == "research" else p.get("defenses", {}) if group == "defenses" else p["ships"]).get(key, 0)
                unique = (UNIQUE_BUILDINGS if group == "buildings" else UNIQUE_RESEARCH).get(race_id, {}).get(key) if group in ("buildings", "research") else None
                max_level = max(level, int(planetary.fields(p)["total"])) if group == "buildings" else technology.RESEARCH[key]["max_level"] if group == "research" and key in technology.RESEARCH else unique.get("max_level", 12) if unique else 12
                requirements = self._entry_requirements(player_id, p, group, key)
                cost = ogame_economy.cost(group, key, spec[2], level if group not in ("ships", "defenses") else 0, resource_cap=MAX_RESOURCE)
                construction_timing = self._project_timing(player_id, p, group, key, level)
                seconds = construction_timing["seconds"]
                reason = ""
                lane = production_timing.project_lane(group)
                if lane in busy:
                    reason = {"build": t("Na tej planecie trwa już budowa."),
                              "ship": t("Stocznia produkuje już statki lub obronę."),
                              "research": t("Na tej planecie trwa już badanie.")}[lane]
                elif group == "research" and research_busy:
                    reason = t('Badanie trwa na innej planecie.')
                elif group == "buildings" and planetary.fields(p)["free"] < 1:
                    reason = t("Brak wolnych slotów budowlanych na tej planecie.")
                elif group not in ("ships", "defenses") and level >= max_level:
                    reason = t('Osiągnięto maksymalny poziom {0}.').format(max_level)
                elif group == "ships" and key in ("interceptor", "siege", "freighter", *fleet_expansion.CAPITAL_ROLES) and not race_id:
                    reason = t('Wybierz rasę imperium, aby odblokować zaawansowane okręty.')
                elif any(not requirement["met"] for requirement in requirements):
                    reason = t('Wymaga: ') + join_text(", ", (t("{0} (poziom {1})").format(requirement["name"], requirement["level"]) for requirement in requirements if not requirement['met'])) + "."
                elif not affordable(p, cost):
                    reason = (t('Rozbuduj skarbiec: pojemność magazynu jest za mała.')
                              if any(cost[resource] > storage_capacity[resource]
                                     and p["resources"][resource] < cost[resource] for resource in RESOURCES)
                              else t('Brakuje surowców.'))
                item = {"key": key, "name": spec[0], "description": spec[1], "level": level, "cost": cost, "seconds": seconds, "enabled": not reason, "reason": reason,
                        "requirements": requirements, "construction_timing": construction_timing}
                if group in ("ships", "research"):
                    brief = catalog_descriptions.brief_description(group, key, "swarm" if player_id == "khar" else race_id, spec[1])
                    item.update(description=brief, brief_description=brief)
                if group in production_timing.FACILITY_FOR_GROUP:
                    item["facility_timing"] = ogame_economy.facility_profile(p["buildings"], group)
                if group not in ("ships", "defenses"):
                    item["max_level"] = max_level
                role = "scout" if key == "propulsion" else "weapon" if key == "weapons" else key
                item["art_key"] = art_key(race_id, role)
                item["race_id"] = race_id
                if group == "ships" and key in fleet_expansion.CAPITAL_ROLES:
                    item["web_art_key"] = "fleet/" + race_id + "/" + key
                if group == "buildings":
                    item["building_fields"] = {**planetary.fields(p), "cost": 1}
                    if key == expeditions.KEY:
                        item["art_key"] = expeditions.ART
                        item["expedition"] = {"current": expeditions.profile(level), "next": expeditions.profile(level + 1)}
                        item["effect_current"] = t("Znaleziska +{0}%. Miejsca na ekspedycje: {1}.").format(expeditions.profile(level)["reward_bonus_percent"], expeditions.profile(level)["slots"])
                        item["effect_next"] = t("Znaleziska +{0}%. Miejsca na ekspedycje: {1}.").format(expeditions.profile(level + 1)["reward_bonus_percent"], expeditions.profile(level + 1)["slots"])
                    if key == "observatory":
                        item["art_key"] = art_key(race_id, "echo_observatory" if race_id == "zetans" else "lab")
                        item["observation"] = {"current": observation_ranges(level), "next": observation_ranges(level + 1)}
                if group == "research":
                    item["tree"] = technology.layout(key)
                    item["web_art_key"] = "research/" + key
                    item["requirements_met"] = all(requirement["met"] for requirement in requirements)
                    if key in technology.RESEARCH:
                        meta = technology.RESEARCH[key]
                        item["art_key"] = art_key(race_id, meta["art"])
                        item["effect_current"] = technology.effect_summary(key, level)
                        item["effect_next"] = technology.effect_summary(key, level + 1) if level < max_level else None
                if unique:
                    effect_text = unique_effect_text if group == "buildings" else research_effect_text
                    item.update(unique=True, max_level=max_level, requirements=requirements,
                                effect_current=effect_text(key, level),
                                effect_next=effect_text(key, level + 1) if level < max_level else t('Maksymalny poziom.'))
                    if group == "buildings":
                        item["building_effect"] = {
                            "key": unique["effect"],
                            "current": effects.get(unique["effect"], 0),
                            "next": (building_effect_value(unique, level + 1)
                                     if level < max_level and (unique["cap"] is None or level < 5) else None),
                        }
                if group in ("buildings", "ships", "defenses"):
                    item["construction_refund_rate"] = self._racial_research_level(player_id, "recycling") / 20
                if group == "ships":
                    traits = self._ship_traits(player_id).get(key, {})
                    siege_multiplier = SHIP_TRAITS.get(key, {}).get("swarm_attack_multiplier", 1.0)
                    item.update(capital=key in fleet_expansion.CAPITAL_ROLES,
                                signature=key == "flagship", endgame=key == "titan",
                                role_name=t(catalog_descriptions.SHIP_ROLES.get(key, "Okręt")),
                                special_traits=dict(traits),
                                requirements_met=all(r["met"] for r in requirements),
                                effective_first_volley_attack=spec[4] * fleet_balance85.weapons_multiplier(player["research"]["weapons"]) * rules["first_volley_multiplier"] * traits.get("first_volley", 1))
                    item.update(count=level, attack=spec[4], hull=spec[5], capacity=spec[6],
                                fuel=spec[7], speed=spec[8], role=key,
                                category="combat" if key in fleet_expansion.COMBAT_ROLES else "utility",
                                effective_fuel=round(spec[7] * (1 - effects.get("fleet_fuel_reduction", 0)), 6),
                                swarm_attack_multiplier=siege_multiplier,
                                effective_swarm_attack=spec[4] * fleet_balance85.weapons_multiplier(player["research"]["weapons"]) * siege_multiplier * (1 + self._bonuses(player_id).get("swarm_damage", 0)),
                                ship_time_reduction=effects.get("ship_time_reduction", 0),
                                effective_attack=spec[4] * fleet_balance85.weapons_multiplier(player["research"]["weapons"]),
                                effective_speed=spec[8] * (1 + player["research"]["propulsion"] * .15) * (1 + .2 * self._racial_research_level(player_id, "antigravity")),
                                production_multiplier=float(self._fleet_multiplier(player_id)),
                                first_volley_multiplier=rules["first_volley_multiplier"] * traits.get("first_volley", 1),
                                regeneration_fraction=max(self._regeneration_fraction(rules), traits.get("regeneration_fraction", 0)),
                                defense_regeneration_fraction=max(self._regeneration_fraction(rules, defense_effects=effects), traits.get("regeneration_fraction", 0)),
                                defense_regeneration_bonus=effects.get("renewal_fraction", 0),
                                damage_reduction=1 - (1 - rules["damage_reduction"]) * (1 - traits.get("damage_reduction", 0)),
                                batch_time_reduction_per_extra=effects.get("batch_time_reduction_per_extra", 0),
                                batch_time_reduction_cap=.30)
                elif group == "defenses":
                    traits = defenses.TRAITS[key]
                    item.update(count=level, stationary=True, role_name=t("Obrona planetarna"),
                                art_key=defenses.ART[key], attack=spec[4], hull=spec[5],
                                effective_attack=spec[4] * fleet_balance85.weapons_multiplier(player["research"]["weapons"]),
                                first_volley_multiplier=traits.get("first_volley", 1),
                                damage_reduction=traits.get("damage_reduction", 0),
                                regeneration_fraction=max(self._regeneration_fraction(rules, defense_effects=effects), traits.get("regeneration_fraction", 0)))
                elif group == "research":
                    item["crystal_refund"] = math.floor(round(cost["crystal"] * effects.get("research_crystal_refund", 0), 6))
                elif group == "buildings":
                    if key in rules["energy_use_per_level"]:
                        resource, rate = {"metal_mine": ("metal", 300),
                                          "crystal_mine": ("crystal", 200),
                                          "refinery": ("fuel", 100)}[key]
                        multiplier = (rules["production_multipliers"][resource] * (1 + effects.get("production_all", 0))
                                      * (1 + effects.get("production_" + resource, 0)) * (1 + self._technology_effects(player_id).get("production_all", 0)) * planetary.multipliers(p)[resource])
                        item.update(production_resource=resource,
                                    production_bonus_percent=round((multiplier - 1.0) * 100.0, 6),
                                    production_per_level=rate * (1.1 ** level) * multiplier * self.speed * ECONOMY_MULTIPLIER,
                                    production_next_per_level=rate * (1.1 ** (level + 1)) * multiplier * self.speed * ECONOMY_MULTIPLIER,
                                    base_production=(economy85.PASSIVE_PRODUCTION[resource] * self.speed
                                                     if self.now >= self.data.get("economy85_from", 0) else 0.0),
                                    energy_per_level=round(economy85.MINE_ENERGY[key] * 1.1 ** level
                                        * rules["energy_use_per_level"][key] / economy85.LEGACY_NEUTRAL_USE[key]
                                        * (1 - effects.get("mining_energy_reduction", 0))
                                        * (1 - self._technology_effects(player_id).get("mining_energy_reduction", 0)), 6))
                        energy_reduction = ((1 - effects.get("mining_energy_reduction", 0))
                                            * (1 - self._technology_effects(player_id).get("mining_energy_reduction", 0)))
                        item["energy_use_current"] = round(economy85.mine_use(key, level, rules, energy_reduction), 6)
                        item["energy_use_next"] = round(economy85.mine_use(key, level + 1, rules, energy_reduction), 6)
                    elif key == "power_plant":
                        power_bonus = planet_traits.multiplier(p, "power")
                        item["energy_supply_current"] = round(economy85.power_supply(level, rules, power_bonus), 6)
                        item["energy_supply_next"] = round(economy85.power_supply(level + 1, rules, power_bonus), 6)
                        item["energy_supply_per_level"] = 20.0 * 1.1 ** level * rules["energy_supply_per_level"] / 100.0 * power_bonus
                        item["description"] = t('Produkcja energii rośnie wykładniczo z poziomem elektrowni. Uwzględnia rasę, badania i umiejętności. Energia zasila wydobycie.')
                    elif key == economy85.VAULTS.get(race_id):
                        item["storage_capacity_current"] = economy85.vault_capacity(level, key, spec[2], MAX_RESOURCE)
                        item["storage_capacity_next"] = economy85.vault_capacity(level + 1, key, spec[2], MAX_RESOURCE)
                if group == "research" and planet_traits.multiplier(p, "research_speed") > 1:
                    item["planet_trait"] = planet_traits.public(p)
                item["details"] = self._catalog_detail_preview(player_id, p, group, item)
                item["planning_reason"] = self._planning_permission(player_id, p, group, item, planning_context)
                item["planning_enabled"] = not item["planning_reason"]
                # A free player can choose an eligible waiting project and then
                # review the offer. This does not grant planning permissions.
                item["planning_eligibility_reason"] = self._planning_permission(
                    player_id, p, group, item, planning_context, check_entitlement=False)
                item["planning_eligible"] = not item["planning_eligibility_reason"]
                result[group].append(item)
        if project_only is not None:
            return result
        research_by_key = {entry["key"]: entry for entry in result["research"]}
        for entry in result["research"]:
            entry["unlocks"] = []
            if entry["key"] in ("propulsion", "weapons"):
                label = t("Prędkość floty") if entry["key"] == "propulsion" else t("Atak floty")
                bonus_percent = 15 if entry["key"] == "propulsion" else int(100 * fleet_balance85.WEAPONS_PER_LEVEL)
                entry["effect_current"] = t("{0} +{1}%").format(label, bonus_percent * entry["level"])
                entry["effect_next"] = t("{0} +{1}%").format(label, bonus_percent * (entry["level"] + 1)) if entry["level"] < entry["max_level"] else None
            elif entry["key"] == "titan_core":
                entry["effect_current"] = t("Tytany i pojemność kondensatora ×8 odblokowane.") if entry["level"] else t("Tytany zablokowane. Standardowa pojemność kondensatora.")
                entry["effect_next"] = t("Odblokowanie tytanów; pojemność kondensatora ×8. Bez darmowej energii.") if not entry["level"] else None
            elif entry["level"] >= entry["max_level"]:
                entry["effect_next"] = None
        targets = [(group, entry) for group in ("research", "ships") for entry in result[group]]
        targets += [("megastructures", entry) for entry in self._mega_state(player_id, p)["projects"]]
        for group, entry in targets:
            for req in entry["requirements"]:
                parent = research_by_key.get(req["key"]) if req["group"] == "research" else None
                if parent is not None:
                    parent["unlocks"].append({"group": group, "key": entry["key"], "name": entry["name"],
                        "level": req["level"], "met": req["met"],
                        "other_requirements_met": all(r["met"] for r in entry["requirements"] if r is not req)})
        result["research"].sort(key=lambda item: (item["tree"]["row"], item["tree"]["column"], item["key"]))
        result["ships"].sort(key=lambda item: fleet_expansion.SHIP_ORDER.index(item["key"]) if item["key"] in fleet_expansion.SHIP_ORDER else 99)
        return result

    @atomic_mutation
    def action(self, player_id, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise GameError(t('Nieprawidłowe polecenie.'))
            p = self._owned(player_id, payload.get("planet_id"))
            player = self._player(player_id)
            request_id = payload.get("request_id")
            if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 100):
                raise GameError(t('Nieprawidłowy identyfikator polecenia.'))
            try:
                fingerprint = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                raise GameError(t('Polecenie zawiera nieprawidłowe wartości.'))
            if request_id in player["requests"]:
                prior = player["requests"][request_id]
                if prior["fingerprint"] != fingerprint:
                    raise GameError(t('Ten identyfikator został użyty dla innego polecenia.'), 409)
                return {"ok": True, "state": self.state(player_id, p["id"]), "message": render_text(prior.get("message_i18n", prior["message"]))}
            kind = payload.get("type")
            if kind == "choose_race":
                race_id = payload.get("race_id")
                if not isinstance(race_id, str) or race_id not in RACES:
                    raise GameError(t('Wybierz jedną z trzech dostępnych ras.'))
                reason = self._race_choice_reason(player_id)
                if reason:
                    raise GameError(reason, 409)
                player["race_id"] = race_id
                onboarding.record(player, "race_chosen")
                self._ensure_racial_research(player)
                player["skill_nodes"] = skill_tree.unlocked_for(race_id, [])
                player.setdefault("swarm_crystals", 0)
                player.setdefault("scout_intel", {})
                for owned in self.data["planets"].values():
                    if owned["owner_id"] == player_id:
                        self._ensure_race_buildings(owned)
                message = t('Wybrano rasę: {0}. To stały wybór tego imperium.').format(t(RACES[race_id]['name']))
                self._report(player_id, t('Narodziny cywilizacji'), message + " " + t(RACES[race_id]["trait"]) + " " + t(RACES[race_id]["tradeoff"]))
            elif kind in ("skip_onboarding", "resume_onboarding"):
                onboarding.set_skipped(player, kind == "skip_onboarding")
                message = t("Samouczek pominięty.") if kind == "skip_onboarding" else t("Samouczek wznowiony.")
            elif kind == "review_prompt":
                try:
                    review_invite.acknowledge(player, payload.get("choice"))
                except (ValueError, TypeError):
                    raise GameError(t('Nieprawidłowy wybór oceny.'), 409) from None
                message = t('Zapisano preferencję prośby o ocenę.')
            elif kind == "subscription_prompt":
                try:
                    if payload.get("choice") != "show":
                        raise ValueError("Unknown subscription invitation choice")
                    subscription_invite.claim(
                        player, request_id, now=self.now,
                        active=self._queue_entitlement(player)["queue_planning_active"])
                except (ValueError, TypeError):
                    raise GameError(t('Oferta jest niedostępna.'), 409) from None
                # The modal itself explains the offer; its automatic display
                # reservation should not create an additional notification.
                message = ""
            elif kind == "unlock_skill":
                try:
                    quote = skill_tree.quote_unlock(self._race_id(player_id), player.get("skill_nodes", []),
                                                    payload.get("node_id"), player.get("swarm_crystals", 0))
                except (ValueError, TypeError) as exc:
                    raise GameError(str(exc), 409) from None
                player["skill_nodes"] = quote["unlocks"]
                player["swarm_crystals"] = quote["balance_after"]
                if quote["cost"] > 0:
                    onboarding.record(player, "first_skill")
                node = next(node for node in skill_tree.graph()["nodes"] if node["id"] == quote["node_id"])
                message = t('Rozwinięto umiejętność: {0}. Wydano {1} Kryształów Roju.').format(node['name'], quote['cost'])
                self._report(player_id, t('Nowa umiejętność'), message, node.get("art_key", ""))
            elif kind in ("megabuild", "megacancel", "tunnel_open", "tunnel_close"):
                message = self._mega_action(player_id, p, payload)
            elif kind == "recall_expedition":
                fleet = self.data["fleets"].get(payload.get("fleet_id")) if isinstance(payload.get("fleet_id"), str) else None
                if not fleet or fleet["owner_id"] != player_id or fleet["mission"] != "expedition":
                    raise GameError(t("Nie możesz odwołać tej ekspedycji."), 403)
                self._expedition_return(fleet, recalled=True)
                message = t("Ekspedycja wraca bez znalezisk. Paliwo pozostaje zużyte.")
            elif kind == "fleet":
                p, target, ships, cargo, cost, seconds, fuel, _ = self._fleet_quote(player_id, payload)
                expedition_data = self._prepare_expedition(player_id, p, payload, seconds) if payload.get("mission") == "expedition" else None
                tunnel = None
                if payload.get("travel_mode") == "tunnel":
                    tunnel = self._tunnel_quote(player_id, p, target, ships, cargo)
                    player["megastructure"]["energy"] -= tunnel["energy_cost"]
                spend(p, cost)
                for key, n in ships.items():
                    p["ships"][key] = p["ships"].get(key, 0) - n
                mission = payload["mission"]
                if mission in ("attack", "colonize") and target["owner_type"] == "player":
                    self._end_beginner_protection(player_id)
                fleet = {"id": ident("f"), "owner_id": player_id, "race_id": self._race_id(player_id), "origin_id": p["id"], "target_id": target["id"], "mission": mission, "status": "outbound", "ships": ships, "cargo": cargo, "swarm_crystals": 0, "started_at": self.now, "seconds": seconds, "arrives_at": self.now + seconds}
                if mission == "scout":
                    fleet.update(scout_scope=payload.get("scout_scope", "planet"), target_system_id=target["system_id"])
                if mission == "transport":
                    fleet["recipient_owner_id"] = target["owner_id"]
                fleet["route"] = self._route_details(p, target)
                if expedition_data is not None:
                    fleet["expedition"] = expedition_data
                if tunnel:
                    fleet["tunnel"] = tunnel
                    fleet["route"]["travel_mode"] = "tunnel"
                fleet["fuel_paid"] = fuel
                fleet["building_effects"] = self._building_effects(p)
                fleet["building_effects"].pop("renewal_fraction", None)
                self.data["fleets"][fleet["id"]] = fleet
                if mission == "attack" and target["owner_type"] == "player":
                    self._report(target["owner_id"], t('Nadciąga wroga flota'), t('Imperium {0} wysłało atak z {1} na {2}. Do celu: {3} s.').format(player['name'], p['name'], target['name'], seconds))
                elif mission == "colonize" and target["owner_type"] == "player":
                    self._report(target["owner_id"], t('Nadciąga próba przejęcia kolonii'), t('Imperium {0} wysłało kolonizator z {1} na {2}. Do celu: {3} s. Stacjonująca flota, obrona planetarna lub wsparcie sojuszników uniemożliwią przejęcie.').format(player['name'], p['name'], target['name'], seconds))
                message = t('Flota wyruszyła: {0} s, koszt {1} paliwa za podróż w obie strony.').format(seconds, fuel)
                if tunnel:
                    message = t("Flota weszła do tunelu. Transfer: {0} s. Energia i powrót zostały opłacone.").format(seconds)
                if mission == "colonize":
                    message += " " + t(COLONIZATION_WARNING)
            elif kind == "cancel_project":
                queue_id = payload.get("queue_id")
                if not isinstance(queue_id, str) or not queue_id or not p["queue"]:
                    raise GameError(t('Ten projekt nie jest już aktywny.'), 409)
                task = next((task for task in p["queue"] if task.get("id") == queue_id), None)
                if task is None or task.get("kind") not in ("build", "research", "ship", "defense"):
                    raise GameError(t('Ten projekt nie jest już aktywny.'), 409)
                if task["ends_at"] <= self.now:
                    raise GameError(t('Projekt został już ukończony. Odśwież widok.'), 409)
                # Never trust a client-supplied cost or recalculate with current discounts.
                paid = task.get("paid_cost")
                if paid is not None and (not isinstance(paid, dict) or set(paid) != set(RESOURCES)
                        or any(type(v) is not int or v < 0 for v in paid.values())):
                    raise GameError(t('Nie można zweryfikować kosztu projektu.'), 409)
                refunded = {}
                for resource in RESOURCES:
                    amount = 0 if paid is None else paid[resource]
                    before = p["resources"][resource]
                    p["resources"][resource] = min(MAX_RESOURCE, before + amount)
                    refunded[resource] = int(p["resources"][resource] - before)
                p["queue"].remove(task)
                # No completion, recycling, growth or research-refund effects fire.
                message = (t('Anulowano projekt. Zwrot: {0} metalu, {1} kryształów, {2} paliwa.').format(
                    refunded["metal"], refunded["crystal"], refunded["fuel"]) if paid is not None
                    else t('Anulowano starszy projekt bez zapisanego kosztu. Bez zwrotu.'))
            elif kind in ("plan_project", "remove_planned_project", "reorder_planned_project"):
                message = self._planned_action(player_id, p, payload)
            elif kind in ("build", "research", "ship", "defense"):
                group = {"build": "buildings", "research": "research", "ship": "ships", "defense": "defenses"}[kind]
                key = payload.get("key")
                entry = next((x for x in self._catalog(player_id, p)[group] if x["key"] == key), None)
                if entry is None:
                    raise GameError(t('Nieznany projekt.'))
                if not entry["enabled"]:
                    raise GameError(entry["reason"], 409)
                amount = integer(payload.get("amount", 1), t('Liczba statków'), 1, 20) if kind in ("ship", "defense") else 1
                self._start_project(p, kind, key, amount, entry)
                message = t('Rozpoczęto projekt.')
            else:
                raise GameError(t('Nieznane polecenie.'))
            if request_id:
                player["requests"][request_id] = {"fingerprint": fingerprint, "message": render_text(store_text(message), "pl"), "message_i18n": store_text(message)}
                while len(player["requests"]) > 128:
                    del player["requests"][next(iter(player["requests"]))]
            # A new successful command is actual play. Replayed commands return
            # above, so an automatic retry cannot keep an abandoned account alive.
            if kind != "subscription_prompt":
                self._touch_player_activity(player_id)
            self._save()
            return {"ok": True, "state": self.state(player_id, p["id"]), "message": message}

    def _return(self, f):
        if sum(f["ships"].values()) == 0:
            self.data["fleets"].pop(f["id"], None)
            return
        f["status"] = "returning"
        origin = self.data["planets"][f["origin_id"]]
        if origin["owner_id"] != f["owner_id"]:
            homes = [p for p in self.data["planets"].values() if p["owner_id"] == f["owner_id"]]
            if not homes:
                self.data["fleets"].pop(f["id"], None)
                return
            target = self.data["planets"][f["target_id"]]
            origin = min(homes, key=lambda p: self._distance(target, p))
            f["origin_id"] = origin["id"]
            f["seconds"], _ = self._flight_numbers(origin, target, f["ships"])
            f["route"] = self._route_details(origin, target)
        f["arrives_at"] = self.now + f["seconds"]
        f["started_at"] = self.now

    def _land(self, p, f):
        # Settled flights cannot be credited twice, including stale event references.
        if f["id"] not in self.data["fleets"]:
            return False
        # An eradicated outpost cannot hand its returning Swarm ships to a player.
        if p["owner_id"] != f["owner_id"]:
            self._return(f)
            return False
        for key, n in f["ships"].items():
            p["ships"][key] = p["ships"].get(key, 0) + n
        for k, v in f["cargo"].items():
            p["resources"][k] = min(MAX_RESOURCE, p["resources"][k] + v)
        crystals = int(f.get("swarm_crystals", 0))
        player = self.data["players"].get(f["owner_id"])
        if player and crystals:
            player["swarm_crystals"] = player.get("swarm_crystals", 0) + crystals
            if crystals > 0 and f["status"] == "returning":
                onboarding.record(player, "swarm_crystals")
        self.data["fleets"].pop(f["id"], None)
        return True

    def _complete_fleet(self, f):
        if f["id"] not in self.data["fleets"]:
            return
        if self._complete_expedition(f):
            return
        if self._alliance_complete_fleet(f):
            return
        target = self.data["planets"][f["target_id"]]
        owner = f["owner_id"]
        if f["status"] == "returning":
            p = self.data["planets"][f["origin_id"]]
            crystals = int(f.get("swarm_crystals", 0))
            if self._land(p, f):
                reward = t(' Przywieziono {0} Kryształów Roju — możesz wydać je w kole umiejętności.').format(crystals) if crystals else ""
                self._report(owner, t('Flota wróciła'), t('Statki wróciły na {0}. Ładunek został rozładowany.').format(p['name']) + reward,
                             "swarm/crystal" if crystals else "", crystals)
            return
        mission = f["mission"]
        if mission == "scout":
            if f.get("scout_scope") == "system":
                self._complete_system_scout(f, target)
                self._return(f)
                return
            self._capture_planetary_intel(owner, target)
            owner_name = t('Wolna planeta') if target["owner_type"] == "empty" else t(self.data["alien"]["name"]) if target["owner_type"] == "alien" else self._player(target["owner_id"])["name"]
            stocks = join_text(", ", (t('{0}: {1}').format(name, int(target['resources'][key])) for key, name in zip(RESOURCES, (t('metal'), t('kryształy'), t('paliwo')))))
            target_specs = self._specs(target["owner_id"], "ships")
            ships = join_text(", ", (t('{0} ×{1}').format(target_specs[k][0], n) for k, n in target['ships'].items() if n)) or t('brak statków')
            static_specs = self._specs(target["owner_id"], "defenses")
            static_text = join_text(", ", (t("{0} ×{1}").format(static_specs[k][0], n)
                                           for k, n in target.get("defenses", {}).items() if n and k in static_specs)) or t("brak")
            snapshot = self._capture_swarm_intel(owner, target)
            if snapshot:
                onboarding.record(self._player(owner), "swarm_scout")
                summary = t("{0} — {1}.").format(target["name"], t("Rój Khar"))
            else:
                summary = t('{0} — {1}. Zapasy: {2}. Flota: {3}.').format(target['name'], owner_name, stocks, ships)
                summary += " " + t("Obrona planetarna: {0}.").format(static_text)
            self._report(owner, t('Raport zwiadu'), summary,
                         "swarm/colony" if snapshot else "")
            if snapshot:
                self._player(owner)["reports"][0]["intel_snapshot"] = copy.deepcopy(snapshot)
            self._player(owner)["reports"][0]["planet_snapshot"] = copy.deepcopy(self._player(owner)["planet_intel"][target["id"]])
            self._return(f)
        elif mission == "transport":
            recipient = f.get("recipient_owner_id", owner)
            if target["owner_id"] == recipient and (recipient == owner or self._allied(owner, recipient)):
                for k, v in f["cargo"].items():
                    target["resources"][k] = min(MAX_RESOURCE, target["resources"][k] + v)
                f["cargo"] = dict.fromkeys(RESOURCES, 0)
                self._report(owner, t('Dostarczono transport'), t('Zapasy dotarły na {0}. Statki wracają.').format(target['name']))
            else:
                self._report(owner, t('Transport zawrócił'), t('Odbiorca transportu nie jest już właścicielem planety albo członkiem twojego sojuszu.'))
            self._return(f)
        elif mission == "colonize":
            count = sum(p["owner_id"] == owner for p in self.data["planets"].values())
            limit = swarm.MAX_COLONIES if owner == "khar" else MAX_COLONIES
            local_swarm_count = sum(p["owner_id"] == "khar" and self._galaxy_id(p) == self._galaxy_id(target)
                                    for p in self.data["planets"].values()) if owner == "khar" else 0
            blocked = self._colonization_block(owner, target)
            if (not blocked and count < limit and f["ships"].get("colonizer", 0) > 0
                    and (owner != "khar" or local_swarm_count < swarm.MAX_COLONIES_PER_GALAXY)):
                captured = target["owner_type"] == "player"
                starting_level = 0
                if captured:
                    self._capture_colony(target, owner)
                    # A target settled during the flight is also a hostile capture.
                    self._end_beginner_protection(owner)
                else:
                    target["owner_type"] = "alien" if owner == "khar" else "player"
                    target["owner_id"] = owner
                    target["buildings"] = dict.fromkeys(BUILDINGS, 0)
                    self._ensure_race_buildings(target)
                    starting_level = self._colony_start_level(owner, f.get("building_effects", {}))
                    for k in ("metal_mine", "crystal_mine", "refinery", "power_plant"):
                        target["buildings"][k] = starting_level
                    target["resources"] = {"metal": 500.0, "crystal": 500.0, "fuel": 0.0}
                    if owner == "khar":
                        # The seed hull pays for the nest. Its escort consists of real ships
                        # removed from the origin, and never appears for free on arrival.
                        swarm.seed(target, self.now, hive=False)
                f["ships"]["colonizer"] -= 1
                self._land(target, f)
                if owner in self.data["players"]:
                    self._ensure_swarm_activation()
                if owner in self.data["players"] and count >= 1:
                    onboarding.record(self._player(owner), "second_colony")
                nursery_text = t(' Zarodnia Pionierów: cztery budynki gospodarcze zaczynają na poziomie {0}.').format(starting_level) if starting_level > 1 else ""
                warning = " " + t(COLONIZATION_WARNING) if owner in self.data["players"] else ""
                if captured:
                    self._report(owner, t('Przejęto kolonię'), t('Przejęto kolonię {0}. Budynki i zapasy pozostały na planecie. Kolonizator zużyto; pozostałe statki i ładunek wylądowały.').format(target['name'])
                                 + " " + t('Budynki rasowe obcej cywilizacji są nieaktywne. Odzyskają działanie, gdy planetą ponownie będzie władać ich rasa.') + warning)
                else:
                    self._report(owner, t('Nowa kolonia'), t('Założono kolonię {0}. Kolonizator rozebrano na bazę; pozostałe statki i zapasy zostały na miejscu.').format(target['name']) + nursery_text + warning)
            else:
                self._report(owner, t('Kolonizacja przerwana'), t('{0} nie jest już dostępna lub osiągnięto limit kolonii. Flota wraca.').format(target['name']) + (" " + blocked if blocked else ""))
                self._return(f)
        else:
            if target["owner_type"] == "empty" or target["owner_id"] == owner or self._alliance_attack_block(owner, target["owner_id"]) or (target["owner_type"] == "player" and self._player(target["owner_id"])["protected_until"] > self.now) or (owner == "khar" and not f.get("swarm_raid", False) and target["owner_type"] == "player" and any(q["owner_type"] == "empty" for q in self.data["planets"].values())):
                self._report(owner, t('Atak odwołany'), t('Cel nie może zostać zaatakowany. Flota wraca.'))
                self._return(f)
            else:
                if self._alliance_has_support(target):
                    self._alliance_battle([f], target)
                else:
                    self._battle(f, target)

    def _power(self, fleet, weapons, specs=None, multiplier=1.0, *, type_multipliers=None, owner_id=None):
        specs = SHIPS if specs is None else specs
        factors = type_multipliers or {}
        weapons_factor = fleet_balance85.weapons_multiplier(weapons,
            is_swarm=owner_id == "khar" or specs is swarm.SHIPS)
        if self.now < self.data.get("economy85_from", 0):
            weapons_factor = 1.0 + .15 * weapons
        return sum(specs[k][4] * n * factors.get(k, 1.0) for k, n in fleet.items() if n) * weapons_factor * multiplier

    @staticmethod
    def _damage(fleet, damage, wounds, specs=None, damage_reduction=0.0, type_reductions=None, *, events=None):
        # Small ships absorb damage first; surviving wounds persist between rounds.
        specs = SHIPS if specs is None else specs
        damage *= 1.0 - damage_reduction
        for key in sorted(specs, key=lambda k: (specs[k][5], k)):
            if fleet.get(key, 0) <= 0:
                continue
            count_before, wounds_before = fleet[key], wounds.get(key, 0)
            hull = specs[key][5]
            remaining = fleet[key] * hull - wounds.get(key, 0)
            resistance = min(.95, max(0.0, (type_reductions or {}).get(key, 0.0)))
            absorbed = min(damage, remaining / (1.0 - resistance))
            hit = absorbed * (1.0 - resistance)
            total = wounds.get(key, 0) + hit
            killed = min(fleet[key], int(total // hull))
            fleet[key] -= killed
            wounds[key] = total - killed * hull if fleet[key] else 0
            damage -= absorbed
            if events is not None and hit > 0:
                raw = absorbed / (1.0 - damage_reduction) if damage_reduction < 1.0 else absorbed
                events.append({"key": key, "before": {"count": count_before, "wounds": wounds_before},
                               "after": {"count": fleet[key], "wounds": wounds[key]},
                               "damage": hit, "blocked": max(0.0, raw - hit), "destroyed": killed})
            if damage <= 0:
                break

    @staticmethod
    def _regenerate(fleet, wounds, fraction, type_fractions=None, *, events=None):
        # Heal only the partially wounded surviving ship, never resurrect losses.
        for key in wounds:
            before = wounds[key]
            wounds[key] = wounds[key] * (1.0 - min(1.0, max(fraction, (type_fractions or {}).get(key, 0)))) if fleet[key] > 0 else 0
            if events is not None and fleet[key] > 0 and before > wounds[key]:
                events.append({"key": key, "healed": before - wounds[key],
                               "before": {"count": fleet[key], "wounds": before},
                               "after": {"count": fleet[key], "wounds": wounds[key]}})

    def _eradicate_swarm_nest(self, target, observers=()):
        """Liberate an outpost while retaining each galaxy's permanent main hive."""
        if target["owner_id"] != swarm.OWNER_ID or swarm.kind(target) == "hive":
            return False
        empty = self._planet(target["id"], target["name"], target["system_id"], target["slot"])
        for key in ("galaxy_id", "environment", "rare_trait"):
            if key in target:
                empty[key] = copy.deepcopy(target[key])
        # Clearing the whole occupation also cancels paid rebuilding queues and
        # legacy racial state. The one-time world reset marker is untouched.
        target.clear()
        target.update(empty)
        for player_id in set(observers):
            if player_id not in self.data["players"]:
                continue
            player = self._player(player_id)
            self._remember_trait(player_id, target, "battle")
            identity = self._planet_identity(target)
            record = player.setdefault("system_intel", {}).setdefault(
                target["system_id"], {"scouted_at": self.now, "planets": []})
            # A battle reveals this planet, not fresh intelligence about its
            # neighbours. Preserve their records and original scouting date.
            record["planets"] = [identity if item["id"] == target["id"] else item
                                 for item in record["planets"]]
            if not any(item["id"] == target["id"] for item in record["planets"]):
                record["planets"].append(identity)
            player.setdefault("planet_intel", {})[target["id"]] = {
                "scouted_at": self.now,
                "identity": self._planet_identity(target, trait_known=True),
                **{key: copy.deepcopy(target[key])
                   for key in ("buildings", "resources", "ships", "defenses")}}
            player.get("scout_intel", {}).pop(target["id"], None)
        # Already launched fleets retain their missions. Returning Swarm fleets
        # use _return/_land to find another nest without donating to a new owner.
        return True

    def _battle(self, f, target):
        attacking_before = dict(f["ships"])
        defending = {**target["ships"], **target.get("defenses", {})}
        defending_before = dict(defending)
        attacker = f["owner_id"]
        defender = target["owner_id"]
        rare_loot_eligible = (defender == "khar"
                              and (defending_before.get("frigate", 0) + defending_before.get("cruiser", 0) + sum(target.get("defenses", {}).values())) > 0
                              and (not target.get("swarm_loot_sealed", False) or self._swarm_ready(target)))
        aw = int(f.get("swarm_weapon_level", 0)) if attacker == "khar" else self._player(attacker)["research"]["weapons"]
        dw = self._swarm_weapon_level(target) if defender == "khar" else self._player(defender)["research"]["weapons"]
        specs_a, specs_d = self._specs(attacker, "ships"), self._specs(defender, "ships")
        static_specs = self._specs(defender, "defenses")
        specs_d = {**specs_d, **static_specs}
        rules_a, rules_d = self._rules(attacker), self._rules(defender)
        # An older already travelling fleet has no retroactive building bonus.
        effects_a = f.get("building_effects", {})
        effects_d = self._building_effects(target)
        # Ignore renewal_fraction even if a legacy fleet saved it at departure.
        regeneration_a = self._regeneration_fraction(rules_a)
        regeneration_d = self._regeneration_fraction(rules_d, defense_effects=effects_d)
        wounds_a, wounds_d = {}, {}
        anti_swarm_a = 1.0 + (self._bonuses(attacker).get("swarm_damage", 0) if defender == "khar" else 0)
        anti_swarm_d = 1.0 + (self._bonuses(defender).get("swarm_damage", 0) if attacker == "khar" else 0)
        siege_factors = {key: meta.get("swarm_attack_multiplier", 1.0) for key, meta in SHIP_TRAITS.items()} if defender == "khar" else {}
        traits_a, traits_d = self._ship_traits(attacker), self._ship_traits(defender)
        reductions_a = {k: v.get("damage_reduction", 0) for k, v in traits_a.items()}
        reductions_d = {k: v.get("damage_reduction", 0) for k, v in {**traits_d, **defenses.TRAITS}.items()}
        heals_a = {k: v.get("regeneration_fraction", 0) for k, v in traits_a.items()}
        heals_d = {k: v.get("regeneration_fraction", 0) for k, v in {**traits_d, **defenses.TRAITS}.items()}
        replay = battle_replay.start(self, attacker, defender, f["ships"], defending,
                                     specs_a, specs_d, static_specs, target)
        def positions():
            return {"attacker": battle_replay.snapshot(f["ships"], wounds_a, replay["attacker"]["initial"]),
                    "defender": battle_replay.snapshot(defending, wounds_d, replay["defender"]["initial"])}
        rounds = 0
        for _ in range(6):
            if not sum(f["ships"].values()) or not sum(defending.values()):
                break
            rounds += 1
            recorded = {"number": rounds, "before": positions(),
                        "hits": {"attacker": [], "defender": []},
                        "heals": {"attacker": [], "defender": []}}
            attack = self._power(f["ships"], aw, specs_a, (rules_a["first_volley_multiplier"] if rounds == 1 else 1.0) * anti_swarm_a, type_multipliers={**siege_factors, **self._ship_round_factors(attacker, rounds)}, owner_id=attacker)
            defense = self._power(defending, dw, specs_d, (rules_d["first_volley_multiplier"] * (1 + effects_d.get("defense_first_volley", 0)) if rounds == 1 else 1.0) * anti_swarm_d, type_multipliers={**defenses.round_factors(rounds), **self._ship_round_factors(defender, rounds)}, owner_id=defender)
            recorded["salvos"] = {"attacker": attack, "defender": defense}
            self._damage(defending, attack, wounds_d, specs_d, rules_d["damage_reduction"],
                         reductions_d, events=recorded["hits"]["defender"])
            self._damage(f["ships"], defense, wounds_a, specs_a, rules_a["damage_reduction"], reductions_a, events=recorded["hits"]["attacker"])
            recorded["after_damage"] = positions()
            self._regenerate(f["ships"], wounds_a, regeneration_a, heals_a, events=recorded["heals"]["attacker"])
            self._regenerate(defending, wounds_d, regeneration_d,
                             heals_d, events=recorded["heals"]["defender"])
            recorded["after"] = positions()
            replay["rounds"].append(recorded)
        target["ships"] = {k: defending.get(k, 0) for k in self._specs(defender, "ships")}
        target["defenses"] = {k: defending.get(k, 0) for k in static_specs}
        victory = sum(defending.values()) == 0 and sum(f["ships"].values()) > 0
        capacity = fleet_capacity(specs_a, f["ships"])
        f["cargo"] = dict.fromkeys(RESOURCES, 0)
        f["swarm_crystals"] = 0
        f["swarm_destruction_bonus"] = 0
        recovered_metal = 0
        eradicated = False
        if victory:
            if defender == "khar" and attacker in self.data["players"]:
                stage = swarm.kind(target)
                quota = math.floor(swarm.RAID_CRYSTALS[stage] * (1.0 + self._bonuses(attacker).get("swarm_loot", 0)))
                crystals = min(int(target.get("swarm_crystals", 0)), quota, capacity) if rare_loot_eligible else 0
                target["swarm_crystals"] = max(0.0, target.get("swarm_crystals", 0) - crystals)
                f["swarm_crystals"] = crystals
                capacity -= crystals
                # A main hive survives and must rebuild a real garrison before
                # its remaining rare stock can be raided again.
                target["swarm_loot_sealed"] = True
                target["swarm_suppressed_until"] = 0
                if stage == "outpost":
                    bonus = min(swarm.DESTRUCTION_CRYSTALS, capacity)
                    f["swarm_destruction_bonus"] = bonus
                    f["swarm_crystals"] += bonus
                    capacity -= bonus
            destroyed_metal = sum(self._unit_construction_cost(defender, key, specs_d[key], stationary=key in static_specs)["metal"]
                                  * (count - defending.get(key, 0)) for key, count in defending_before.items() if count)
            recovered_metal = min(capacity, math.floor(round(destroyed_metal * effects_a.get("wreck_recovery_fraction", 0), 6)))
            f["cargo"]["metal"] = recovered_metal
            capacity -= recovered_metal
            available = self._lootable_resources(target)
            total = sum(available.values())
            if total:
                for k, v in available.items():
                    n = min(v, math.floor(capacity * v / total)) if total > capacity else v
                    f["cargo"][k] += n
                    target["resources"][k] -= n
        if victory and defender == swarm.OWNER_ID and attacker in self.data["players"]:
            # Resolve real stock, capacity and wreck recovery before clearing it.
            eradicated = self._eradicate_swarm_nest(target, (attacker,))
        lost_a = join_text(", ", (t('{0} ×{1}').format(specs_a[k][0], n - f['ships'][k]) for k, n in attacking_before.items() if n > f['ships'][k])) or t('brak')
        lost_d = join_text(", ", (t('{0} ×{1}').format(specs_d[k][0], n - defending[k]) for k, n in defending_before.items() if n > defending[k])) or t('brak')
        outcome = t('Zwycięstwo') if victory else t('Klęska') if sum(f["ships"].values()) == 0 else t('Nierozstrzygnięta bitwa — odwrót')
        summary = t('{0}: {1}. Rundy: {2}. Straty atakującego: {3}. Straty obrońcy: {4}. Zdobycz: metal {5}, kryształy {6}, paliwo {7}. ').format(target['name'], outcome, rounds, lost_a, lost_d, f['cargo']['metal'], f['cargo']['crystal'], f['cargo']['fuel'])
        if recovered_metal:
            summary += t(' Recykler Wraków odzyskał {0} metalu; jest w ładowni i zostanie rozładowany po powrocie.').format(recovered_metal)
        if effects_d.get("defense_first_volley", 0):
            summary += t(' Cytadela Magnetyczna: pierwsza salwa obrońcy +{0}%.').format(round(effects_d['defense_first_volley'] * 100))
        if effects_d.get("renewal_fraction", 0):
            summary += t(' Gaj Odnowy — regeneracja obrony planety +{0} pkt proc.').format(round(effects_d['renewal_fraction'] * 100))
        if defender == "khar":
            if attacking_before.get("siege", 0):
                summary += t(' Okręty oblężnicze: atak przeciw obronie Roju +50%.')
            summary += t(' Kryształy Roju: {0} w ładowni; trafią do koła po powrocie floty.').format(f['swarm_crystals'])
            if eradicated:
                summary += t(' Gniazdo Roju zostało zniszczone. Planeta jest wolna i można ją skolonizować.')
                if f["swarm_destruction_bonus"]:
                    summary += t(' Premia za zniszczenie gniazda: {0} Kryształów Roju (wliczona w ładunek).').format(f["swarm_destruction_bonus"])
            elif victory:
                summary += t(' Główny ul przetrwał. Zachowuje budynki i odbudowuje flotę z własnych zasobów; planety nie można skolonizować.')
        else:
            summary += t(' Budynki i własność planety pozostają bez zmian.')
        for label, owner_id, regeneration in ((t('Atakujący'), attacker, regeneration_a), (t('Obrońca'), defender, regeneration_d)):
            race_id = self._race_id(owner_id)
            if race_id:
                rules = self._rules(owner_id)
                effects = []
                if rules["first_volley_multiplier"] > 1:
                    effects.append(t('pierwsza salwa +{0}%').format(round((rules['first_volley_multiplier'] - 1) * 100)))
                if regeneration:
                    effects.append(t('regeneracja {0}% ran po rundzie').format(round(regeneration * 100)))
                if rules["damage_reduction"]:
                    effects.append(t('redukcja obrażeń {0}%').format(round(rules['damage_reduction'] * 100)))
                summary += t(' {0} — {1}: {2}; {3}.').format(label, t(RACES[race_id]['name']), t(RACES[race_id]['weapon_name']), join_text(", ", effects))
        replay["final"] = positions()
        replay["outcome"] = "attacker_wins" if victory else "attacker_destroyed" if not sum(f["ships"].values()) else "retreat"
        replay["cargo"] = dict(f["cargo"])
        replay["swarm_crystals"] = f["swarm_crystals"]
        replay["swarm_eradicated"] = eradicated
        replay["swarm_destruction_bonus"] = f["swarm_destruction_bonus"]
        replay["attacker"]["losses"] = {k: n - f["ships"].get(k, 0) for k, n in attacking_before.items() if n}
        replay["defender"]["losses"] = {k: n - defending.get(k, 0) for k, n in defending_before.items() if n}
        self._report(attacker, t('Raport bitwy'), summary, "swarm/weapon" if defender == "khar" else "", f["swarm_crystals"], replay=replay)
        self._report(defender, t('Twoja kolonia została zaatakowana'), summary, "swarm/weapon" if attacker == "khar" else "", replay=replay)
        self._return(f)

    def battle_report(self, player_id, report_id):
        with self.lock:
            player = self._player(player_id)
            report = next((r for r in player["reports"] if r.get("id") == report_id), None)
            if not report or not report.get("battle_replay"):
                raise GameError(t('Odtworzenie tej bitwy jest niedostępne.'), 404)
            return {"ok": True, "replay": battle_replay.public(report["battle_replay"])}

    def _state_planet_selection(self, player_id, planet_id=None):
        """Validate read selection while recovering from a captured colony."""
        player = self._player(player_id)
        lost_selection = None
        selected = self.data["planets"].get(planet_id) if isinstance(planet_id, str) else None
        if (selected is not None and selected["owner_id"] != player_id
                and self._known_planet(player_id, selected)):
            # A read after capture must still refresh the game. Mutating
            # actions retain _owned's strict check before idempotency lookup.
            lost_selection = {"planet_id": planet_id, "name": selected["name"],
                              "message": t('Wybrana planeta nie należy już do ciebie. Przełączono na planetę macierzystą.')}
            planet_id = player["home_id"]
        return self._owned(player_id, planet_id), lost_selection

    def state(self, player_id, planet_id=None):
        with self.lock:
            player = self._player(player_id)
            p, lost_selection = self._state_planet_selection(player_id, planet_id)
            galaxy, own = self._public_observation_map(player_id)
            for owned in own:
                owned["storage"] = self.storage(self.data["planets"][owned["id"]])
            known = {q["id"]: q for system in galaxy for q in system["planets"]}
            fleets = []
            alien_fleets = []
            incoming_attacks = []
            for f in self.data["fleets"].values():
                target = self.data["planets"][f["target_id"]]
                if (f["owner_id"] != player_id and f["status"] == "outbound"
                        and f["mission"] in ("attack", "alliance_attack", "colonize") and target["owner_id"] == player_id):
                    incoming_attacks.append({
                        "id": f["id"], "attacker_name": t(self.data["alien"]["name"]) if f["owner_id"] == "khar" else self._player(f["owner_id"])["name"],
                        "origin_name": self.data["planets"][f["origin_id"]]["name"], "target_name": target["name"],
                        "origin_id": f["origin_id"], "target_id": f["target_id"],
                        "mission": f["mission"],
                        "arrives_at": f["arrives_at"], "seconds": f.get("seconds", 0),
                        "started_at": f.get("started_at", f["arrives_at"] - f.get("seconds", 0)),
                    })
                if f["owner_id"] != player_id:
                    if not (f["owner_id"] == "khar" and f["status"] == "outbound" and f["mission"] == "attack" and target["owner_id"] == player_id):
                        continue
                view = {k: copy.deepcopy(f[k]) for k in ("id", "origin_id", "target_id", "mission", "status", "ships", "arrives_at")}
                # Public system coordinates only. Never expose enemy fleet telemetry.
                view["started_at"] = f.get("started_at", f["arrives_at"] - f.get("seconds", 0))
                view["origin_system_id"] = self.data["planets"][f["origin_id"]]["system_id"]
                view["target_system_id"] = target["system_id"]
                view["origin_galaxy_id"] = self._galaxy_id(self.data["planets"][f["origin_id"]])
                view["target_galaxy_id"] = self._galaxy_id(target)
                for key in ("operation_id", "hold_until", "hold_hours", "natural_seconds", "scout_scope", "target_system_id", "map_return_fraction"):
                    if key in f:
                        view[key] = copy.deepcopy(f[key])
                view["origin_name"] = self.data["planets"][f["origin_id"]]["name"]
                view["target_name"] = known.get(f["target_id"], {}).get("name", t("Nieznany cel zwiadu")) if f["owner_id"] == player_id else target["name"]
                if f["owner_id"] == player_id and f["mission"] == "expedition":
                    self._public_expedition_fleet(f, view)
                if f["owner_id"] == player_id and f["mission"] in ("alliance_attack", "alliance_defense"):
                    view["target_name"] = f.get("target_name", view["target_name"])
                if isinstance(f.get("route"), dict):
                    # The dispatched route and its paid timing survive topology
                    # migration; a new map must not redraw an old flight's path.
                    view["route"] = copy.deepcopy(f["route"])
                else:
                    view["route"] = self._route_details(self.data["planets"][f["origin_id"]], target)
                    for key in ("navigation_schema", "system_ids", "segments", "local_distance"):
                        view["route"].pop(key, None)
                if f.get("tunnel") and f["owner_id"] == player_id:
                    view["route"]["travel_mode"] = "tunnel"
                    view["tunnel"] = copy.deepcopy(f["tunnel"])
                race_id = self._race_id(f["owner_id"])
                view.update(race_id=race_id, race_name=t(RACES[race_id]["name"]) if race_id else "",
                            seconds=f.get("seconds", 0), cargo=copy.deepcopy(f.get("cargo", {})),
                            swarm_crystals=int(f.get("swarm_crystals", 0)))
                if f["owner_id"] == "khar":
                    role = "colonizer" if f["mission"] == "colonize" else "frigate"
                    view.update(race_id="swarm", race_name=t('Rój Khar'), art_key="swarm/" + role)
                    for private_key in ("ships", "cargo", "swarm_crystals"):
                        view.pop(private_key, None)
                (fleets if f["owner_id"] == player_id else alien_fleets).append(view)
            result = {"version": VERSION, "web_build": VERSION, "server_time": self.now, "speed": self.speed, "player": {k: player[k] for k in ("id", "name", "protected_until")}, "home_id": player["home_id"], "planet_id": p["id"], "planet_name": p["name"], "resources": {k: int(v) for k, v in p["resources"].items()}, "production": self.production(p), "energy": self.energy(p), "buildings": dict(p["buildings"]), "research": dict(player["research"]), "ships": dict(p["ships"]), "defenses": dict(p.get("defenses", {})), "queue": copy.deepcopy(p["queue"]), "catalog": self._catalog(player_id, p), "own_planets": own, "galaxy": galaxy, "fleets": fleets, "reports": [self._public_intel_report(report) for report in player["reports"]], "alien": {"name": t(self.data["alien"]["name"]), "colonies_count": sum(q.get("owner_id") == "khar" for q in known.values()), "fleets": alien_fleets}, "limits": {"colonies": MAX_COLONIES}}
            race_id = self._race_id(player_id)
            result["colonization_capture"] = {"enabled": True}
            if lost_selection:
                result["selected_planet_lost"] = lost_selection
            result["inactive_racial_buildings"] = [
                {"key": key, "name": t(meta["spec"][0]), "level": p["buildings"][key],
                 "race_id": other_race, "race_name": t(RACES[other_race]["name"])}
                for other_race, entries in UNIQUE_BUILDINGS.items() if other_race != race_id
                for key, meta in entries.items() if p["buildings"].get(key, 0) > 0]
            result["galaxies"] = self._public_galaxies(p, player_id, galaxy)
            result["environment"] = planetary.public_environment(p)
            result["fields"] = planetary.fields(p)
            result["storage"] = self.storage(p)
            result["observation"] = self._observation_state(player_id, p)
            result["technology_tree"] = {"schema": 2, "columns": 3, "rows": 10}
            result["megastructures"] = self._mega_state(player_id, p)
            result["planet_galaxy_id"] = self._galaxy_id(p)
            result["economy_multiplier"] = ECONOMY_MULTIPLIER
            result["production_status"] = self._production_status(player_id)
            result["limits"]["resource_cap"] = MAX_RESOURCE
            result["incoming_attacks"] = sorted(incoming_attacks, key=lambda item: (item["arrives_at"], item["id"]))
            protected = self._building_effects(p).get("protected_resources", 0)
            result["protected_resources"] = {key: int(min(protected, p["resources"][key])) for key in RESOURCES}
            result["account"] = self.account_status(player_id)
            result["premium"] = {**self.billing_verifier.public_entitlement(player), **self._queue_entitlement(player)}
            result["premium"]["configured"] = result["premium"]["provider_ready"]
            result["premium"]["obfuscated_account_id"] = result["premium"]["billing_account_id"]
            result["planned_orders"] = self._public_planned_orders(player_id)
            result["limits"]["queue_waiting"] = self.QUEUE_WAITING_LIMIT
            result["communications"] = self.chat_summary(player_id)
            result["alliance"] = self.alliance_summary(player_id)
            empty_start = bool(self._available_start_planets())
            result["sector"] = {"max_players": self.max_players, "players": len(self.data["players"]),
                                "registration_open": empty_start and (not self.max_players or len(self.data["players"]) < self.max_players)}
            result["player"].update(race_id=race_id, race_name=t(RACES[race_id]["name"]) if race_id else "",
                                    swarm_crystals=int(player.get("swarm_crystals", 0)))
            result["expeditions"] = self._expedition_state(player_id, p)
            result["ranking_reward"] = rankings.reward_state(self, player_id)
            result["skill_tree"] = skill_tree.public_state(race_id, player.get("skill_nodes", []), player.get("swarm_crystals", 0))
            result["review_prompt"] = review_invite.public(player)
            result["subscription_prompt"] = subscription_invite.public(
                player, active=result["premium"]["queue_planning_active"])
            weak = [q for q in known.values() if q.get("owner_id") == "khar"]
            recommended = min(weak, key=lambda q: (self._galaxy_id(q) != self._galaxy_id(p),
                                                   self._distance(p, q), q["id"])) if weak else None
            result["alien"].update(name=t(self.data["alien"]["name"]), portrait_art="swarm/portrait", colony_art="swarm/colony", weapon_art="swarm/weapon",
                                   crystal_art="swarm/crystal", description=t(swarm.DESCRIPTION),
                                   max_colonies=swarm.MAX_COLONIES,
                                   recommended_target_id=recommended["id"] if recommended else "")
            result["races"] = [public_race(key) for key in RACES]
            result["race"] = public_race(race_id) if race_id else {}
            result["race_choice_reason"] = self._race_choice_reason(player_id)
            result["race_choice_allowed"] = not result["race_choice_reason"]
            result["colony_art"] = result["environment"].get("colony_art", art_key(race_id, "colony"))
            safe_data = dict(self.data)
            safe_data["planets"] = {pid: self.data["planets"][pid] if item.get("owner_id") == player_id else item for pid, item in known.items()}
            # Research remains visible/manageable while visiting another colony.
            result["research_queue"] = next(({**copy.deepcopy(task), "planet_id": colony["id"],
                                               "planet_name": colony["name"]}
                                              for colony in self.data["planets"].values()
                                              if colony["owner_id"] == player_id for task in colony["queue"]
                                              if task["kind"] == "research"), None)
            result["onboarding"] = onboarding.public_state(safe_data, player, recommended_target_id=recommended["id"] if recommended else "", planet_id=p["id"])
            self._observation_onboarding(result["onboarding"], galaxy, p)
            return result


class GameHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, world, trust_proxy_header=None, update_policy=None):
        if trust_proxy_header not in (None, "X-Real-IP"):
            raise ValueError("Only an explicit X-Real-IP proxy header is supported")
        self.world = world
        self.trust_proxy_header = trust_proxy_header
        if update_policy is not None and not isinstance(update_policy, UpdatePolicy):
            raise ValueError("update_policy must be an UpdatePolicy")
        self.update_policy = UpdatePolicy() if update_policy is None else update_policy
        self.rate_lock = threading.Lock()
        self.attempts = defaultdict(deque)
        self.billing_refresh_lock = threading.Lock()
        self.billing_refresh_slots = threading.BoundedSemaphore(4)
        self.billing_refresh_in_flight = set()
        self.billing_refresh_last_attempt = {}
        self.google_signin = GoogleSignInService(world)
        self.email_signin = EmailSignInService(world)
        super().__init__(address, Handler)

    def schedule_billing_refresh(self, player_id):
        """Poll verified receipts in bounded workers, never under the game lock."""
        world = self.world
        with world.lock:
            player = world.data["players"].get(player_id)
            if player is None or not world.billing_verifier.is_refresh_due(player):
                return
            purchase_token = player.get("subscription", {}).get("_play_token")
        now = time.monotonic()
        with self.billing_refresh_lock:
            if player_id in self.billing_refresh_in_flight or now - self.billing_refresh_last_attempt.get(player_id, -300) < 300:
                return
            if not self.billing_refresh_slots.acquire(blocking=False):
                return
            self.billing_refresh_in_flight.add(player_id)
            self.billing_refresh_last_attempt[player_id] = now

        def refresh():
            try:
                checked_started = float(world.billing_verifier.clock())
                try:
                    verified = world.billing_verifier.check_purchase(player_id, purchase_token)
                except BillingError as error:
                    if error.code in {"purchase_not_found", "wrong_account", "wrong_product", "wrong_package"}:
                        with world.lock:
                            player = world.data["players"].get(player_id)
                            if player and player.get("subscription", {}).get("_play_token") == purchase_token:
                                world.advance()
                                with world._atomic():
                                    world.billing_verifier.invalidate_player(player, checked_started=checked_started)
                                    world.advance()
                                    world._save()
                    return
                with world.lock:
                    player = world.data["players"].get(player_id)
                    if not player or player.get("subscription", {}).get("_play_token") != purchase_token:
                        return  # A concurrent replacement or account deletion wins.
                    world.advance()  # Settle the cached paid interval first.
                    with world._atomic():
                        world.billing_verifier.apply_purchase(player, verified, world.data["players"])
                        world.advance()
                        world._save()
            except Exception as error:
                # Never log tokens, credentials, provider bodies, or saved data.
                print("Subscription refresh: " + type(error).__name__, flush=True)
            finally:
                with self.billing_refresh_lock:
                    self.billing_refresh_in_flight.discard(player_id)
                self.billing_refresh_slots.release()

        threading.Thread(target=refresh, name="play-billing-refresh", daemon=True).start()

    def schedule_due_billing_refreshes(self):
        """Renewals and refunds must be checked even while all players are offline."""
        with self.world.lock:
            player_ids = [player_id for player_id, player in self.world.data["players"].items()
                          if player.get("subscription", {}).get("_play_token")
                          and self.world.billing_verifier.is_refresh_due(player)]
        for player_id in player_ids:
            self.schedule_billing_refresh(player_id)

    def rate_limit(self, identity, auth=False):
        now = time.monotonic()
        key = (identity, auth)
        with self.rate_lock:
            if len(self.attempts) > 5000:
                self.attempts = defaultdict(deque, {k: v for k, v in self.attempts.items() if v and v[-1] > now - 60})
            attempts = self.attempts[key]
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= (12 if auth else 180):
                raise GameError(t('Zbyt wiele prób. Spróbuj ponownie za minutę.'), 429)
            attempts.append(now)


class Handler(BaseHTTPRequestHandler):
    server_version = "Pogranicze/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # Do not log Authorization, credentials, bodies or full query strings.
        pass

    def _html(self, status, document):
        raw = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "public, max-age=900")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Accept-Language")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        if getattr(self, "_google_start_cookie", None):
            self.send_header("Set-Cookie", self._google_start_cookie)
        if getattr(self, "_email_start_cookie", None):
            self.send_header("Set-Cookie", self._email_start_cookie)
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise GameError(t('Niedozwolony sposób przesyłania danych.'), 400)
        raw_length = self.headers.get("Content-Length", "0")
        if not re.fullmatch(r"[0-9]{1,8}", raw_length):
            raise GameError(t('Nieprawidłowy rozmiar żądania.'))
        length = int(raw_length)
        if length > MAX_BODY:
            raise GameError(t('Żądanie jest zbyt duże.'), 413)
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            raise GameError(t('Wymagane dane JSON.'), 415)
        try:
            def reject_constant(value):
                raise ValueError(value)
            data = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            # JSON's numeric exponent syntax can overflow a float without using
            # the non-standard NaN/Infinity tokens handled above.
            json.dumps(data, allow_nan=False)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise GameError(t('Nieprawidłowe dane JSON.'))
        if not isinstance(data, dict):
            raise GameError(t('Żądanie musi być obiektem JSON.'))
        return data

    def _client_ip(self):
        # Enable only behind Railway's HTTP ingress. A header is not itself proof
        # of proxy identity: the origin must not also accept untrusted direct
        # traffic. Standalone servers ignore all forwarded headers by default.
        header = self.server.trust_proxy_header
        if header is not None:
            values = self.headers.get_all(header, [])
            if len(values) == 1:
                value = values[0].strip()
                if len(value) <= 45 and "%" not in value:
                    try:
                        return str(ipaddress.ip_address(value))
                    except ValueError:
                        pass
        return self.client_address[0]

    def _billing(self, token, body, *, refresh=False):
        """Two-phase purchase verification: Google I/O cannot stall gameplay."""
        world = self.server.world
        with world.lock:
            world.advance()
            player_id = world.authenticate(token)
            player = world._player(player_id)
            planet_id = world._owned(player_id, body.get("planet_id"))["id"]
            purchase_token = player.get("subscription", {}).get("_play_token") if refresh else body.get("purchase_token")
            if refresh and not purchase_token:
                return {"ok": True, "state": world.state(player_id, planet_id), "message": t("Brak subskrypcji do przywrócenia.")}
        checked_started = float(world.billing_verifier.clock())
        try:
            verified = world.billing_verifier.check_purchase(player_id, purchase_token)
        except BillingError as error:
            if refresh and error.code in {"purchase_not_found", "wrong_account", "wrong_product", "wrong_package"}:
                with world.lock:
                    if world.authenticate(token) == player_id:
                        player = world._player(player_id)
                        if player.get("subscription", {}).get("_play_token") == purchase_token:
                            world.advance()
                            with world._atomic():
                                world.billing_verifier.invalidate_player(player, checked_started=checked_started)
                                world.advance()
                                world._save()
            raise
        with world.lock:
            world.advance()
            if world.authenticate(token) != player_id:
                raise GameError(t("Zaloguj się ponownie."), 401)
            player = world._player(player_id)
            if refresh and player.get("subscription", {}).get("_play_token") != purchase_token:
                raise GameError(t("Subskrypcja została zmieniona. Odśwież jej stan."), 409)
            with world._atomic():
                world.billing_verifier.apply_purchase(player, verified, world.data["players"])
                world.advance()
                world._save()
            selected = world.data["planets"].get(planet_id)
            if not selected or selected["owner_type"] != "player" or selected["owner_id"] != player_id:
                planet_id = None
            return {"ok": True, "state": world.state(player_id, planet_id), "message": t("Odświeżono stan subskrypcji.")}

    def _handle(self):
        path = urlsplit(self.path)
        world = self.server.world
        if self.command == "GET" and path.path == "/health":
            if not world.write_healthy:
                raise GameError(t('Zapis gry jest chwilowo niedostępny.'), 503)
            return {"ok": True, "version": VERSION,
                    "world_epoch": world.data.get("launch_reset_id", "")}
        if self.command == "GET" and path.path == "/api/notifications/config":
            return {"ok": True, **push_notifications.configuration()}
        if self.command == "GET" and path.path == "/api/client-version":
            return self.server.update_policy.manifest()
        if self.command == "GET" and path.path == "/api/public/announcement":
            # Public, read-only, no login or Android update required.
            return announcements.public(world)
        if path.path in ("/api/admin/announcement", "/api/admin/stats", "/api/admin/unused-accounts"):
            if not announcements.enabled():
                raise GameError(t('Panel ogłoszeń nie został skonfigurowany.'), 503)
            self.server.rate_limit(("admin-announcement", self._client_ip()), auth=True)
            if not announcements.authorized(self.headers.get("X-AC-Announcement-Key", "")):
                raise GameError(t('Brak uprawnień administratora.'), 403)
            if path.path == "/api/admin/unused-accounts":
                if self.command == "GET":
                    return world.unused_accounts_preview()
                if self.command == "POST":
                    return world.unused_accounts_delete(self._body())
                raise GameError(t('Niedozwolona metoda.'), 405)
            if path.path == "/api/admin/stats":
                if self.command != "GET":
                    raise GameError(t('Niedozwolona metoda.'), 405)
                return announcements.activity_stats(world)
            if self.command == "GET":
                return announcements.editor(world)
            if self.command != "POST":
                raise GameError(t('Niedozwolona metoda.'), 405)
            body = self._body()
            try:
                return announcements.update(world, body)
            except RuntimeError as error:
                raise GameError(str(error), 409) from None
            except (ValueError, TypeError):
                raise GameError(t('Nieprawidłowy komunikat.'), 400) from None
        client_identity = ("ip", self._client_ip())
        if path.path.startswith("/api/") and not is_web_client(self.headers):
            # Android versionCode is independent of the hosted web release.
            # Missing, duplicate and malformed native versions mean an old APK.
            # Authentication remains mandatory for both clients.
            values = self.headers.get_all("X-PGR-Client-Version", [])
            version = 0
            if len(values) == 1 and re.fullmatch(r"[0-9]{1,10}", values[0]):
                candidate = int(values[0])
                if candidate <= MAX_VERSION_CODE:
                    version = candidate
            if version < self.server.update_policy.min_version_code:
                self.server.rate_limit(client_identity)
                # Stop before credentials, request bodies or game state are read.
                raise UpdateRequired(self.server.update_policy)
        if self.command not in ("GET", "POST"):
            self.server.rate_limit(client_identity)
            raise GameError(t('Niedozwolona metoda.'), 405)
        if path.path.startswith("/api/auth/email/"):
            return handle_email_api(self, path.path)
        if path.path.startswith("/api/auth/google/"):
            service = self.server.google_signin
            if self.command == "GET" and path.path == "/api/auth/google/config":
                self.server.rate_limit(client_identity)
                return service.config()
            if self.command == "POST" and path.path in (
                    "/api/auth/google/start", "/api/auth/google/status", "/api/auth/google/complete",
                    "/api/auth/google/native/start", "/api/auth/google/native/verify"):
                self.server.rate_limit(("google-api", client_identity), auth=not path.path.endswith("/status"))
                native = path.path.startswith("/api/auth/google/native/")
                if native:
                    platforms = self.headers.get_all("X-PGR-Client-Platform", [])
                    versions = self.headers.get_all("X-PGR-Client-Version", [])
                    if (len(platforms) != 1 or platforms[0].strip().lower() != "android"
                            or len(versions) != 1 or not re.fullmatch(r"[0-9]{1,10}", versions[0])
                            or not 1 <= int(versions[0]) <= MAX_VERSION_CODE):
                        raise GameError(t("Nieprawidłowy klient logowania Google."), 400)
                body = self._body()
                if native and path.path.endswith("/verify"):
                    return service.native_verify(body.get("flow_id"), body.get("poll_secret"), body.get("id_token"))
                if path.path.endswith("/start"):
                    mode = body.get("mode", "login")
                    player_id = session_hash = None
                    if mode == "link":
                        auth = self.headers.get("Authorization", "")
                        token = auth[7:] if auth.startswith("Bearer ") else ""
                        with world.lock:
                            world.advance()
                            player_id = world._reauth_account(token, body.get("password"))
                            session_hash = hashlib.sha256(token.encode()).hexdigest()
                    client = body.get("client", "android" if native else "web")
                    browser_cookie = secrets.token_urlsafe(32) if client == "web" else None
                    result = service.start(mode, player_id=player_id, session_hash=session_hash,
                                           client=client, browser_cookie=browser_cookie,
                                           handoff=body.get("handoff"), native=native)
                    if browser_cookie:
                        self._google_start_cookie = "__Host-alien_google_flow=" + browser_cookie + "; Path=/; Max-Age=600; Secure; HttpOnly; SameSite=Lax"
                    return result
                if path.path.endswith("/status"):
                    return service.status(body.get("flow_id"), body.get("poll_secret"),
                                          handoff_ticket=body.get("handoff_ticket"))
                return service.complete(body.get("flow_id"), body.get("poll_secret"), body.get("name"))
            raise GameError(t('Nie znaleziono adresu API.'), 404)
        auth_path = self.command == "POST" and path.path in ("/api/login", "/api/register", "/api/recover")
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if auth_path:
            self.server.rate_limit(client_identity, auth=True)
        else:
            try:
                player_id = world.authenticate(token)
            except GameError:
                self.server.rate_limit(client_identity)
                raise
            # Verified accounts have separate quotas even when sharing a mobile
            # carrier NAT, household router, or Railway proxy address. Additional
            # session tokens cannot multiply an account's quota.
            self.server.rate_limit(("player", player_id))
            if self.command == "POST" and path.path.startswith("/api/account/"):
                self.server.rate_limit(("sensitive-account", player_id), auth=True)
        body = self._body() if self.command == "POST" else None
        if self.command == "POST" and (path.path in ("/api/billing/verify", "/api/billing/refresh")
                or path.path == "/api/action" and body.get("type") in ("verify_subscription", "refresh_subscription")):
            self.server.rate_limit(("billing", player_id), auth=True)
            return self._billing(token, body, refresh=path.path == "/api/billing/refresh" or body.get("type") == "refresh_subscription")
        if self.command == "GET" and path.path == "/api/state":
            self.server.schedule_billing_refresh(player_id)
        with world.lock:
            world.advance()
            if self.command == "POST" and path.path == "/api/register":
                return world.register(body.get("name"), body.get("password"), body.get("invite", ""))
            if self.command == "POST" and path.path == "/api/login":
                return world.login(body.get("name"), body.get("password"))
            if self.command == "POST" and path.path == "/api/recover":
                return world.recover_account(body.get("name"), body.get("recovery_code"), body.get("new_password"))
            # Recheck after advancing time and reading the body: the session may
            # have expired or been revoked by another request in the meantime.
            player_id = world.authenticate(token)
            if self.command == "GET" and path.path == "/api/ranking":
                query = parse_qs(path.query, keep_blank_values=True)
                if (any(len(values) != 1 for values in query.values())
                        or set(query) - {"category", "page", "around_me"}
                        or not re.fullmatch(r"[1-9][0-9]{0,5}", query.get("page", ["1"])[0])
                        or query.get("around_me", ["0"])[0] not in ("0", "1")):
                    raise GameError(t('Nieprawidłowe parametry rankingu.'), 400)
                return rankings.view(world, player_id, query.get("category", ["total"])[0],
                                     int(query.get("page", ["1"])[0]), query.get("around_me", ["0"])[0] == "1")
            if self.command == "GET" and path.path == "/api/state":
                planet_id = parse_qs(path.query).get("planet_id", [None])[0]
                # Settle all offline time BEFORE a real foreground return. A
                # timer poll, observer or invalid planet never resumes production.
                world._state_planet_selection(player_id, planet_id)
                if world._explicit_activity_header(self.headers.get_all(ACTIVITY_HEADER, [])):
                    world.mark_player_activity(player_id)
                response_state = world.state(player_id, planet_id)
                world._state_poll_presence[player_id] = time.monotonic()
                return {"ok": True, "state": response_state, "message": ""}
            if self.command == "GET" and path.path == "/api/battle-replay":
                report_id = parse_qs(path.query).get("report_id", [""])[0]
                return world.battle_report(player_id, report_id)
            if self.command == "GET" and path.path == "/api/alliance":
                return world.alliance_view(player_id, parse_qs(path.query).get("search", [""])[0])
            if self.command == "POST" and path.path == "/api/alliance":
                return world.alliance_action(player_id, body)
            if self.command == "GET" and path.path == "/api/alliance/operations":
                return world.alliance_operations_view(player_id)
            if self.command == "POST" and path.path == "/api/alliance/operation":
                return world.alliance_operation(player_id, body)
            if self.command == "POST" and path.path == "/api/alliance/operation/preview":
                return world.alliance_operation_preview(player_id, body)
            if self.command == "GET" and path.path == "/api/chat/inbox":
                return world.chat_inbox(player_id)
            if self.command == "GET" and path.path == "/api/chat":
                query = parse_qs(path.query)
                try:
                    before = int(query.get("before", ["0"])[0])
                    after = int(query.get("after", ["0"])[0])
                except (ValueError, TypeError):
                    raise GameError(t('Nieprawidłowy numer wiadomości.'), 400)
                return world.chat_feed(player_id, query.get("peer_id", [""])[0], before, after)
            chat_actions = {"/api/chat/send": world.chat_send, "/api/chat/read": world.chat_read,
                            "/api/chat/block": world.chat_block, "/api/chat/report": world.chat_report}
            if self.command == "POST" and path.path in chat_actions:
                return chat_actions[path.path](player_id, body)
            if self.command == "POST" and path.path == "/api/notifications/register":
                return push_notifications.register(world, player_id, token, body)
            if self.command == "POST" and path.path == "/api/notifications/unregister":
                return push_notifications.unregister(world, player_id, token)
            if self.command == "POST" and path.path == "/api/action":
                return world.action(player_id, body)
            if self.command == "POST" and path.path == "/api/preview":
                return world.preview(player_id, body)
            if self.command == "POST" and path.path == "/api/logout":
                state = world.state(player_id)
                world.logout(token)
                return {"ok": True, "state": state, "message": t('Wylogowano.')}
            if self.command == "POST" and path.path == "/api/account/recovery-code":
                return world.account_recovery_code(token, body.get("password"))
            if self.command == "POST" and path.path == "/api/account/rename":
                return world.account_rename(token, body.get("name"), body.get("planet_id"))
            if self.command == "POST" and path.path == "/api/account/password":
                return world.account_password(token, body.get("password"), body.get("new_password"))
            if self.command == "POST" and path.path == "/api/account/logout-others":
                return world.account_logout_others(token, body.get("password"))
            if self.command == "POST" and path.path == "/api/account/delete":
                return world.account_delete(token, body.get("password"), body.get("confirmation"))
            raise GameError(t('Nie znaleziono adresu API.'), 404)

    def _serve(self):
        with language_scope(self.headers.get("Accept-Language", "en")):
            self._serve_localized()

    def _serve_localized(self):
        public_path = urlsplit(self.path).path
        if self.command == "GET" and public_path in ("/admin/announcement", "/admin/announcement/"):
            self._html(200, announcements.EDITOR_HTML)
            return
        if self.command == "GET" and public_path in ("/privacy", "/privacy/"):
            self._html(200, PRIVACY_HTML)
            return
        if self.command == "GET" and public_path in ("/delete-account", "/delete-account/"):
            self._html(200, ACCOUNT_DELETION_HTML)
            return
        try:
            if serve_email_browser(self):
                return
            if serve_google_browser(self):
                return
            self._json(200, self._handle())
        except UpdateRequired as exc:
            self._json(426, {"ok": False, "code": "update_required", "error": exc.message,
                             "update": exc.update})
        except BillingError as exc:
            self._json(exc.status, {"ok": False, "code": exc.code, "error": t(exc.message)})
        except GoogleSignInError as exc:
            self._json(exc.status, {"ok": False, "error": exc.message})
        except EmailSignInError as exc:
            self._json(exc.status, {"ok": False, "error": exc.message})
        except GameError as exc:
            self._json(exc.status, {"ok": False, "error": exc.message})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception as exc:
            # Type only; never print a request, credentials, token or world snapshot.
            print(t('Błąd obsługi żądania: {0}').format(type(exc).__name__), flush=True)
            self._json(500, {"ok": False, "error": t('Błąd serwera. Spróbuj ponownie.')})

    do_GET = _serve
    do_POST = _serve
    do_PUT = _serve
    do_DELETE = _serve


def build_server(world, host="127.0.0.1", port=8765, trust_proxy_header=None, update_policy=None):
    return GameHTTPServer((host, port), world, trust_proxy_header=trust_proxy_header,
                          update_policy=update_policy)


def main(argv=None, trust_proxy_header=None):
    parser = argparse.ArgumentParser(description="Pogranicze Galaktyki — serwer testu multiplayer")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="galaxy.sqlite3")
    parser.add_argument("--speed", type=float, default=1)
    parser.add_argument("--max-players", type=int, default=0,
                        help=t('Opcjonalny limit kont; 0 (domyślnie) wyłącza limit. Nadal potrzebne są wolne planety.'))
    args = parser.parse_args(argv)
    if args.max_players < 0:
        parser.error(t('--max-players musi być nieujemną liczbą całkowitą'))
    update_policy = load_update_policy()
    # This release resets NPCs only. Never opt into the historical player reset.
    world = World(args.db, args.speed, max_players=args.max_players, apply_balance_reset=False)
    server = build_server(world, args.host, args.port, trust_proxy_header=trust_proxy_header,
                          update_policy=update_policy)
    stop = threading.Event()

    def tick():
        next_billing_sweep = 0.0
        while not stop.wait(1):
            try:
                world.advance()
                if time.monotonic() >= next_billing_sweep:
                    server.schedule_due_billing_refreshes()
                    next_billing_sweep = time.monotonic() + 30
            except Exception as exc:
                print(t('Błąd aktualizacji świata: {0}').format(type(exc).__name__), flush=True)

    worker = threading.Thread(target=tick, name="galaxy-tick", daemon=True)
    worker.start()
    push_worker = threading.Thread(target=push_notifications.run_sender, args=(world, stop), name="android-push", daemon=True)
    push_worker.start()

    def shutdown(signum, frame):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print(f"Pogranicze {VERSION}: http://{args.host}:{args.port}, tempo ×{args.speed:g}", flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        stop.set()
        worker.join(timeout=3)
        push_worker.join(timeout=12)
        server.server_close()
        world.close()


if __name__ == "__main__":
    main()





