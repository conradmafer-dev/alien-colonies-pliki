# Alien Colonies — OGame 1x economy (branch preview)

Status: isolated, NOT deployed to Railway. Preserve Android 78 / 0.12.11.

## Included
- New accounts: 500 metal, 500 crystal, 0 fuel; zero completed standard buildings at signup.
- New colonies: 500 / 500 / 0 (legacy colony starting-level bonuses preserved).
- Authentic OGame base costs and growth for metal mine, crystal mine, fuel refinery / deuterium equivalent, power plant, shipyard and laboratory.
- OGame-equivalent ship/defense prices by functional hull analogue; combat stats and faction graphics unaffected.
- Other facilities and research: double price per completed level.
- Build and ship time from (metal + crystal) / (2500 × facility level multiplier) hours.
- Research time from (metal + crystal) / (1000 × (1 + laboratory level)) hours.
- Existing skill and other time bonuses retained.
- Standard, racial and unique buildings: NO hardcoded level ceiling; the catalogue derives a per-planet upper bound from the planet's available total fields. Every upgrade consumes one field. Research one-off/capped technologies keep their separate progression rules.
- High resource cap below 2^53 for JSON compatibility.
- Only new player project costs and deadlines change. Already-paid queues keep stored paid_cost and ends_at. Swarm AI timing and existing fleets are unchanged.

## Checks
- Source files mirrored in railway/ and server/.
- New regression tests: railway/tests/test_ogame_economy.py and server/tests/test_ogame_economy.py.
- Isolated cost calculator tests passed locally; a full integration suite against Railway is still required before merge.

## Important
This branch does NOT modify the production formula, Khar AI economics or megastructure queues.
Check progression balance and server-client compatibility before merging. It must not be
described as a complete production-ready release until integration checks pass.
