# Alien Colonies 0.3.0 — shared contract

The Godot 4 client is portrait, Polish UI. Python standard-library HTTP server is authoritative, persists to SQLite and processes time while clients are disconnected. Open-registration prototype; the Railway package adds durable hosting and client version policy.

## Transport

JSON UTF-8. Bearer token in Authorization on authenticated routes. Every success returns `{ "ok": true, "state": State, "message": "..." }`; auth also returns `token`. Errors return `{ "ok": false, "error": "Polish explanation" }` with appropriate HTTP status.

- GET `/health` returns `{ "ok": true, "version": "0.3.0" }`.
- POST `/api/register` `{name,password}` creates player and session. No invitation is required. Legacy invite fields are ignored. The optional max_players cap is disabled by default (0); a new account still needs a free planet. Name 3–20 characters; password at least 8. New account has a home planet and starter fleet.
- POST `/api/login` `{name,password}` returns session.
- GET `/api/state?planet_id=ID` selects owned planet; omission selects home.
- POST `/api/action` body `{"type":TYPE,"planet_id":ID,...}`. Returns state for selected planet. Types:
  - `build`: `key` in metal_mine, crystal_mine, refinery, power_plant, shipyard, lab.
  - `research`: `key` in propulsion, weapons.
  - `ship`: `key` in scout, cargo, colonizer, frigate, cruiser; `amount` integer 1–20.
  - `fleet`: `mission` scout, transport, colonize, attack; `target_id`; `ships` object counts by ship key; optional `cargo` resource object. Returning survivors and loot handled by server. Transport only to owned planets in MVP; attacks only alien colonies or unprotected players. Scout reports selected planet. Colonize consumes one colonizer, lands survivors at colony; colonization limit three planets per player. Origin resources and ships removed immediately.
- POST `/api/logout` revokes token (client may simply forget token if unavailable).

## State

```
{
  version: "0.3.2", server_time: 1234567890, speed: 1,
  player: {id: "...", name: "...", protected_until: 1234567890},
  home_id: "...", planet_id: "...", planet_name: "...",
  resources: {metal: 2000, crystal: 1500, fuel: 750},
  production: {metal: 600, crystal: 400, fuel: 200}, // actual resources/hour, includes speed
  energy: {supply: 100, used: 70, factor: 1.0},
  buildings: {metal_mine:1, crystal_mine:1, refinery:1, power_plant:1, shipyard:1, lab:1},
  research: {propulsion:0,weapons:0},
  ships: {scout:2,cargo:1,colonizer:1,frigate:3,cruiser:0},
  queue: [{id:"...",kind:"build",key:"metal_mine",amount:1,level:2,ends_at:1234567890}],
  catalog: {
    buildings: [{key,name,description,level,cost:{metal,crystal,fuel},seconds,enabled,reason}],
    research: [{key,name,description,level,cost:{metal,crystal,fuel},seconds,enabled,reason}],
    ships: [{key,name,description,count,cost:{metal,crystal,fuel},seconds,enabled,reason,attack,hull,capacity}]
  },
  own_planets: [{id,name,system_id}],
  galaxy: [{id:"s1",name:"Helios",x:0.0,y:0.0,planets:[{id,name,system_id,slot,owner_type:"empty|player|alien",owner_id:"...",owner_name:"..."}]}],
  fleets: [{id,origin_id,target_id,origin_name,target_name,mission,status:"outbound|returning",ships,arrives_at}],
  reports: [{id,at,title,text}],
  alien: {name:"Rój Khar",colonies_count:3,next_expansion_at:1234567890},
  limits: {colonies:3}
}
```

Production already reflects speed and energy. Times are real UNIX seconds. Queue is one construction/ship/research task per planet. Catalog enabled/reason must reflect queue busy, affordability and unlock requirements. Polling every 3 seconds; do not poll while another HTTP request is active. Client may locally interpolate display time but only server decides outcomes. Every fleet response must show readable fuel cost/duration via deterministic preview or a server quote; simplest optional endpoint POST `/api/preview` with fleet action payload returns `{ok:true, fuel_cost, seconds, error?}` and no mutation.

Client may tolerate optional fields. Server and client must preserve exact keys above; communicate contract changes to root. Project paths are relative to the folder containing project.godot.

## Client update policy (0.1.5)

Clients send `X-PGR-Client-Version: 6` on gameplay API calls. Missing, malformed or duplicate headers represent legacy code 0. This is a compatibility signal, not authentication.

GET `/api/client-version` is public and returns `Cache-Control: no-store`:

```json
{"ok":true,"latest_version_code":6,"latest_version":"0.1.5","min_version_code":0,"download_url":"","message":"","apk_sha256":"","apk_size_bytes":0}
```

Codes are integers from 0 to 2100000000 and `latest_version_code >= min_version_code`. Download links are ASCII URLs with lowercase https:// and a public DNS hostname (optional path/query; no literal IPs, credentials or fragments), at most 2048 characters. Raw whitespace, controls, backslashes, encoded controls/backslash and local/reserved suffixes are rejected. A nonzero minimum requires a valid link in server configuration. Name max 40 characters, message max 300; no control characters.

If the client code is lower than the minimum, gameplay API routes return HTTP 426 before reading the body or advancing/mutating the world:

```json
{"ok":false,"code":"update_required","error":"Zaktualizuj grę, aby kontynuować.","update":{"ok":true,"latest_version_code":7,"latest_version":"0.1.6","min_version_code":7,"download_url":"https://downloads.studio.pl/game.apk","message":"","apk_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","apk_size_bytes":12000000}}
```

The example URL, hash and size are illustrative, not a published release. `/health` and `/api/client-version` remain accessible. Default minimum 0 permits old clients; default empty URL announces no download.

The client compares numeric codes, validates received metadata, handles optional dismissal per origin/release during the run, and pauses game requests for required updates. A 426 forces the update screen even if its metadata is malformed. A failed update check cannot clear a known required update. A successful compatible policy can release the block. Older servers returning 404 on an initial version check remain usable. No token is sent to version checks or to the external download page.

## In-app APK downloads (0.1.5)

The manifest and embedded HTTP 426 update include `apk_sha256` (64 lowercase hexadecimal characters) and `apk_size_bytes` (1..268435456), or empty string/0 when unconfigured. Both fields are optional for parsing legacy manifests. Complete file metadata requires a public HTTPS download URL; the server rejects partial/invalid pairs before opening the world. Legacy URL-only configuration still starts.

A client may offer in-app downloading only with valid URL/hash/size. It streams into a private partial file without API credentials, follows at most 5 explicitly validated HTTPS redirects, verifies exact size/SHA256/APK manifest before renaming, then exposes an explicit install action. Encoded spaces are allowed in URL paths/queries for CDN redirects; raw whitespace and encoded control/backslash remain rejected.

Installed client 0.1.5 uses code 6. New installations must keep the package and signing identity, and increase code. Android PackageManager checks downloaded archive package/code before requesting installation. OS.shell_open performs the final system handoff; real-device verification remains required. No direct download or installation is triggered automatically.


## Rasy — rozszerzenie 0.1.12

`State.player.race_id` jest pusty do jednorazowego wyboru. `State.races` opisuje trzy rasy (id, name, description, trait, tradeoff, weapon_name, portrait_art, colony_art, weapon_art, rules). `race_choice_allowed` i `race_choice_reason` sterują dostępnością wyboru. `race` opisuje wybraną rasę.

`POST /api/action`: `{type: "choose_race", race_id: "zetans" | "symbionts" | "automatons", planet_id, request_id}`. Akcja wymaga zwykłego uwierzytelnienia. Nieznana rasa daje400; dokonany już wybór albo trwające projekty/loty dają409. Powtórzenie identycznego request_id zwraca wynik bez drugiej zmiany.

Katalog podaje `art_key`, `race_id` i rzeczywiste rasowe nazwy/ceny/czasy. Statki dodatkowo mają `effective_attack`, `effective_speed`, `fuel`, `first_volley_multiplier`, `regeneration_fraction` oraz `damage_reduction`. Budynki wydobywcze podają `production_resource`, `production_per_level`, `base_production` i `energy_per_level`; elektrownia `energy_supply_per_level`. Produkcja wpisana w katalogu zakłada pełne zasilanie i uwzględnia tempo świata. Pola ekonomii w State pokazują aktualne warunki.


## Skill wheel and Swarm (0.2.0)

The client sends Android version code **14**. Server health reports **0.2.0**.
The default update manifest remains unannounced until the administrator supplies actual APK metadata.

`POST /api/action` adds `{"type":"unlock_skill","node_id":"zetans_0_0","request_id":"unique-id"}`.
The usual optional owned `planet_id` selects the returned colony state. The server validates the chosen race, existing unlocked neighbors, positive integer wallet, price and duplication before updating both unlocks and wallet. Existing request-id replay rules apply. No client-provided price, effects or balance are trusted.

Additional state:

- `player.swarm_crystals`: integer rare-currency balance shared by the empire; distinct from `resources.crystal`.
- `skill_tree`: `nodes`, `edges`, `roots`, `sectors`, `empty_radius`, `balance`, `unlocked`, `bonuses`.
- Every node: `id`, `race_id`, `kind`, `name`, `description`, `x`, `y`, `size` (world-space radius), `cost`, `effects`, `icon`, `unlocked`, `available`, `affordable`. `available` is topological access, not permission to spend an insufficient balance. Mini-icons are rendered by the client's vector icon catalog. Root portraits also have normal artwork keys.
- The chosen race's root is automatically unlocked once. Foreign roots are purchased through connected paths. Bonuses are additive fractions with caps defined in `server/skill_tree.py`; speed bonuses divide duration by `1 + bonus`, and fuel efficiency reduces fuel cost by its fraction. Racial signature combat traits come from roots exactly once.
- Swarm planets expose `race_id: "swarm"`, `race_name`, `colony_art`, `planet_art`, `swarm_kind`, `swarm_kind_name`, `swarm_threat`, `swarm_crystals_hint`, `swarm_buildings`. Hints and building silhouettes are public; exact crystal stock appears in a scout report.
- `alien` includes artwork keys, a description, colony limit and `recommended_target_id` for finding a beginner hunt.
- Returning player fleets can carry `swarm_crystals`; these enter the wallet only when the fleet lands. Reports can add `art_key` and `swarm_crystals` for visual reward presentation.

Rare crystals are synthesized only on Swarm-owned worlds, up to local stock caps. A victorious player raid deducts actual stock, subject to raid quota, bonuses and surviving cargo capacity. A defeated fleet cannot grant a reward. Ordinary player production, PvP, empty targets and transport do not mint rare crystals. Winning against an outpost removes it; winning against a hive damages its hatchery and temporarily suppresses expansion. New Swarm colonies are established by budgeted fleets and reserve target slots against duplicate seeding.


## Unikalne budynki ras (0.2.1)

`catalog.buildings` ma dla wybranej rasy trzy dodatkowe wpisy przed sześcioma podstawowymi. Nowe pola: `unique: true`, `max_level: 5`, `effect_current`, `effect_next`, `requirements: [{key, name, level, met}]`. `art_key` wskazuje osobny obraz budynku rasy. Poziom w `state.buildings` zaczyna się od 0. Do budowy służy dotychczasowe `/api/action` z `type: build` i kluczem własnej struktury.

Wpis statku ma `batch_time_reduction_per_extra` i `batch_time_reduction_cap`. Czas zamówienia `amount` sztuk: `max(1, ceil(seconds * amount * (1 - min(cap, per_extra * (amount - 1)))))`. Koszt surowców pozostaje kosztem pojedynczej sztuki razy `amount`. Kolejka zwraca już docelowy czas i nie jest skracana przez późniejsze ukończenie innego budynku.

Wpis badania ma `crystal_refund`: liczbę zwykłych kryształów zwracanych po zakończeniu. Rozkaz zapisuje tę wartość w kolejce; ponowienie tego samego zlecenia nie powiela zwrotu.

Preview floty zawiera już lokalny rabat czasu zwiadu lub paliwa kolonizacji. Premie bojowe i odzysku wraków są zapisywane w `building_effects` floty przez serwer. Klient nie może nadać flocie własnych premii przez payload.


## Badania rasowe (0.2.2)

Klient ma kod Androida **16**, serwer `/health` podaje **0.2.2**. Polityka aktualizacji pozostaje osobną konfiguracją rzeczywistego opublikowanego APK.

`catalog.research` zawiera badanie własnej rasy przed dwoma podstawowymi. Klucze: `antigravity` (Zetanie), `multiplication` (Symbionci), `recycling` (Automatony). Akcja wykorzystuje zwykłe `{type: "research", key, planet_id, request_id}`. Serwer wymaga laboratorium 3 i odpowiednio `echo_observatory`, `renewal_grove` lub `wreck_recycler` na poziomie 2 w kolonii rozpoczynającej badanie. Własny poziom w `state.research` zaczyna się od 0; maksimum wynosi 5, a zdobycie obcego korzenia w kole nie udostępnia obcego badania.

Karta badania ma `unique: true`, `max_level`, `requirements: [{key, name, level, met}]`, `effect_current`, `effect_next`, `art_key` i standardowe koszt/czas/enabled/reason. Klient wyświetla osobną sekcję badań rasowych tylko wtedy, gdy serwer dostarcza takie wpisy. `enabled` obejmuje również lokalną kolejkę i koszt. Poziom jest wspólny dla imperium; ukończenie tego samego poziomu w innej kolonii nie przyznaje go ponownie.

Budynki i statki mają `construction_refund_rate` (0–0,25). Przewidywany zwrot materiału to `floor(cost[resource] * amount * rate)`, gdzie dla budynku amount=1. Serwer wylicza zwrot dokładnymi liczbami całkowitymi od faktycznej płatności i zapisuje `construction_refund` w zadaniu. Pełny koszt jest potrzebny przed startem; refundacja następuje przy zakończeniu, do zwykłego limitu zasobów. Klient nie określa należnego zwrotu.

Wpisy statków mają `production_multiplier` (1–2). Wyświetlana liczba to mnożnik nowej hodowli; zaokrąglenie pojedynczego zamówienia zależy od trwałej reszty danego typu statku. Serwer przechowuje reszty jako pary liczb całkowitych, stosuje je przy rzeczywistym ukończeniu produkcji i raportuje otrzymane jednostki. Ukończenie Namnażania powiększa aktualne własne statki w koloniach oraz flotach w obie strony proporcją nowy/stary mnożnik; nie powiela misji, ładunków, walut ani terminów. Zniszczone statki nie wracają.

`effective_speed` statków oraz wynik `/api/preview` uwzględniają `1 + 0.2 * antigravity_level`, łącznie z napędem i kołem. Nowy lot zapisuje wyliczony czas, więc późniejsze badanie nie przyspiesza misji już wysłanej. Recykling i Antygrawitacja nie zmieniają wcześniejszych snapshotów. Wszystkie wartości pochodzą z autorytatywnego serwera.


## Publiczna beta (0.3.0 / Android 17)

Nowe pola opcjonalne w `State`:

- `onboarding`: `{version:1,completed_count,total:5,finished,steps,current}`. Każdy krok `{id,title,description,done,action,target_id}`; current jest pierwszym nieukończonym lub null. Actions: building/scout/hunt/skills/colonize. `target_id` dla building jest kluczem budynku, dla misji planetą. Pusty cel misji oznacza oczekiwanie; klient nie uruchamia misji. Wskaźniki nie przyznają zasobów ani nie są zapisywane poleceniem klienta.
- `incoming_attacks`: posortowane po ETA `{id,attacker_name,origin_name,target_name,origin_id,target_id,arrives_at,started_at,seconds}`. Wyłącznie wrogie outbound attack na własne planety, także Rój. Nie ujawnia statków ani cargo. Obserwator i atakujący nie otrzymują listy zagrożeń obrońcy. Stare `alien.fleets` pozostaje listą publicznych tras NPC bez cargo/liczb statków.
- `account`: `{recovery_code_enabled:bool}`. Brak kodu i jego skrótu w stanie świata.
- `sector`: `{max_players,players,registration_open}`. Rejestracja wymaga limitu oraz wolnej planety; 0 w max_players oznacza brak dodatkowego limitu kont, nie nieograniczoną planszę.

Zarządzanie kontem używa POST JSON:

| Endpoint | Payload | Sukces |
| --- | --- | --- |
| `/api/account/recovery-code` | password | ok, recovery_code, message |
| `/api/recover` | name, recovery_code, new_password | ok, token, state, message |
| `/api/account/password` | password, new_password | ok, token, state, message |
| `/api/account/logout-others` | password | ok, message |
| `/api/account/delete` | password, confirmation: "USUŃ KONTO" | ok, deleted:true, message |

Publiczne odzyskiwanie współdzieli limit uwierzytelniania 12/minutę/IP z login i register. Pozostałe operacje wymagają Bearer, aktualnego hasła i dodatkowego limitu 12/minutę/konto. Błędne obecne hasło daje403; nieprawidłowy/wygasły Bearer401. Recovery-code jest jednorazowo pokazywany po rotacji. Zmiana/reset hasła usuwa wszystkie stare sesje oraz kod i zwraca nowy token. Operacji konta klient nie ponawia automatycznie po niepewnym wyniku sieciowym.

Operacje mutujące i rozliczanie upływu czasu zapisują RAM+SQLite atomowo. Błąd zapisu cofa świat, czas i identyfikatory ponowienia oraz powoduje503. `/health` zwraca wtedy503, a po udanym zapisie znowu200 i standardowe `{ok:true,version:"0.3.0"}`. Błąd backupu nie oznacza automatycznie uszkodzenia aktywnego zapisu i nie cofa zatwierdzonej akcji.

## Doprecyzowanie 0.3.1

Domyślne `state.speed` wynosi 1. Jawne ustawienie tempa operatora nadal jest zwracane zgodnie ze stanem świata. `catalog.buildings` zwraca najpierw budynki podstawowe, następnie rasowe. Kolejność badań nie ulega zmianie.

Podgląd kolonizacji (`POST /api/preview`, `mission: "colonize"`) zawiera `colony_start_level`: poziom startowy czterech budynków gospodarczych nowej kolonii, domyślnie 1. Dla Symbiontów jest równy 1 + ukończony poziom `pioneer_nursery` w kolonii wysyłającej. Pole `message` objaśnia aktywny bonus. Wysłanie zapisuje `colony_start_building_bonus` w serwerowym `building_effects` floty; klient nie może podać ani zmienić tej premii.

Efekt Korzenia to `building_time_reduction` i dotyczy wszystkich pozycji katalogu budynków niezależnie od docelowego poziomu. Czas zostaje utrwalony w kolejce przy zamówieniu. Dawny warunek `young_building_time_reduction` oraz paliwowy bonus nowych misji Zarodni są usunięte.

`catalog.ships[].regeneration_fraction` pokazuje sumę premii regeneracji gracza i lokalnego Gaju, ograniczoną do zakresu 0–1. Dotychczasowy zapis `renewal_fraction` floty jest odczytywany jako dodatek do tego samego procentu regeneracji; nie uruchamia drugiego leczenia kadłuba.

## Zmiany0.3.2

`catalog.ships[].regeneration_fraction` od0.3.2 oznacza własną regenerację floty z rasy/umiejętności. `defense_regeneration_fraction` pokazuje łączną regenerację podczas obrony bieżącej planety, a `defense_regeneration_bonus` lokalną premię Gaju. Gaj nie jest zapisywany do nowych atakujących flot, a stary `building_effects.renewal_fraction` nie wpływa na atak. Tylko obrona planety z Gajem dostaje dodatkową regenerację. Pozostałe premie budynków nie zmieniają zakresu działania.
