#!/usr/bin/env python3
"""Offline, isolated budget/expansion simulation; never opens a production DB.

This advances World time in fixed steps, not real wall-clock days. At most one
AI decision runs per step, so it is a sampled scenario, not a forecast of PvP.
Rare traits are disabled by default for comparable unbuffed planets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import swarm


def snapshot(world: app.World, start: float) -> dict:
    colonies = [p for p in world.data['planets'].values() if p['owner_id'] == swarm.OWNER_ID]
    return {
        'day': round((world.now - start) / 86400, 8),
        'colonies': len(colonies),
        'by_galaxy': dict(sorted(Counter(p['galaxy_id'] for p in colonies).items())),
        'stationed_ships_only': {k: sum(p['ships'].get(k, 0) for p in colonies) for k in swarm.SHIPS},
        'outbound_colonizations': len(world._swarm_pending_colonies()),
        'metal_mine_level_distribution': dict(sorted(Counter(p['buildings']['metal_mine'] for p in colonies).items())),
        'total_regular_resources': {r: sum(p['resources'][r] for p in colonies) for r in app.RESOURCES},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--step-seconds', type=int, default=1800)
    parser.add_argument('--output', type=Path, default=Path('simulation.json'))
    parser.add_argument('--natural-traits', action='store_true', help='Keep normal rare planet traits instead of unbuffed comparison')
    args = parser.parse_args()
    if not 1 <= args.days <= 90:
        parser.error('--days must be between 1 and 90')
    if not 10 <= args.step_seconds <= 86400:
        parser.error('--step-seconds must be between 10 and 86400')
    world = app.World(':memory:', speed=1.0, now=1_000_000)
    try:
        if not args.natural_traits:
            for p in world.data['planets'].values():
                p['rare_trait'] = ''
        start = world.now
        wall_start = time.monotonic()
        targets = sorted({d * 86400 for d in (1, 3, 7, 14, args.days) if d <= args.days})
        observations = [snapshot(world, start)]
        for step in range(1, math.ceil(args.days * 86400 / args.step_seconds) + 1):
            world.advance(start + min(args.days * 86400, step * args.step_seconds))
            if targets and world.now - start >= targets[0]:
                observations.append(snapshot(world, start))
                while targets and world.now - start >= targets[0]:
                    targets.pop(0)
                s = observations[-1]
                print(f"day {s['day']:g}: {s['colonies']} colonies; {s['by_galaxy']}", flush=True)
        result = {
            'version': app.VERSION,
            'scenario': 'isolated sampled simulation, not live PvP',
            'database': ':memory:',
            'players': 0,
            'production_speed': 1.0,
            'step_seconds': args.step_seconds,
            'natural_traits': args.natural_traits,
            'simulated_days': args.days,
            'wall_seconds': time.monotonic() - wall_start,
            'external_resource_grants': 0,
            'external_ship_grants': 0,
            'observations': observations,
            'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ('app.py', 'swarm.py', 'swarm_ai.py', 'swarm_reset.py',
                                           'defenses.py', 'production_timing.py', 'planetary.py')},
            'limitations': [
                'No player combat, destruction or colonization pressure.',
                'Only one AI turn per sampled World.advance call.',
                'Real player competition, planet traits and server speed change the outcome.',
                'Stationed ship totals exclude ships already in flight.',
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Result: {args.output}', flush=True)
    finally:
        world.close()


if __name__ == '__main__':
    main()
