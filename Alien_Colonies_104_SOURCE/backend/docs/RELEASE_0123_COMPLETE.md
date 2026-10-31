# Alien Colonies 0.12.3 — complete server integration

This release combines the previously pending 0.12.1 galaxy, inactivity and
reconnaissance update with the live weekly subscription, 50% galaxy signup
threshold and colony capture updates. The production base is
`c3925e5d54781c5e65c7854af0b898167359b721`.

## Player-visible behavior

- Every galaxy has 60 systems: the existing 30-system outer ring and two
  inner rings with 20 and 10 systems. Five bidirectional bridges connect
  each adjacent pair of rings. Server-calculated routes and browser/Android
  maps use the same topology.
- Player resource production stops after 604800 seconds without activity.
  Existing stock remains, and paid queues and flights continue. Returning
  resumes production prospectively; no resources accrue for the stopped
  period. Passive polling and other players' actions do not renew activity.
- Existing accounts receive one persisted seven-day transition period,
  because the previous server did not record reliable activity dates.
  Restarts do not extend that period. The Khar Swarm is excluded.
- Whole-system scouting can be repeated in an already known system. The
  mission has its own dated report showing planet ownership at arrival.
  Detailed resources and defenses still require individual planet scouting.
  Earlier Android clients could already refresh system ownership through
  the legacy scouting path; this release adds explicit mission/report support.
- The browser uses the same new icon already embedded in Android build 68.
- New empires use the first galaxy below 50% occupied planets, now calculated
  against the expanded world's actual planet count.
- Homeworld protection, undefended colony capture, preserved racial buildings,
  weekly subscription support and existing monthly entitlements remain active.

## Save compatibility

The migration adds systems without replacing existing system or planet IDs.
It preserves player accounts, colony ownership, buildings, resources, queued
work, and paid flights with their original deadlines. No launch, balance or
Swarm reset marker is changed. The migration verifies a durable SQLite backup
before changing an existing save and refuses to proceed if that backup fails.

## Clients and publication

Android 0.12.1 / code 68 already supports the new rings, activity signals and
system scouting. Android 0.12.2 / code 69 adds weekly subscription presentation.
Android 0.12.3 / code 70 also adds colony capture presentation. The latest
delivered AAB 70 is compatible with this server integration and needs no
rebuild solely for these server changes. Signing and Google Play publication
remain separate from deploying the server. Minimum Android version is unchanged.

Deployments are considered complete only after Railway reports SUCCESS and
the public health endpoint and released web assets have been verified.
