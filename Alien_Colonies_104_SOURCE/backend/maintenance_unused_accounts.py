"""Explicit, one-time offline cleanup; ordinary server startup never invokes it.

Requires the same exclusive world lock as run.py. Defaults to a read-only
preview; --apply and a durable operation ID are required to delete anything.
With --serve, release the lock and exec the normal website launcher afterwards.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import app
from accounts import UNUSED_CONFIRMATION, UNUSED_IDLE_SECONDS
from run import WorldFileLock, configuration


def cleanup(world, *, idle_seconds, operation_id=None, apply=False, at=None):
    if apply and not operation_id:
        raise ValueError("Applying cleanup requires a unique operation ID.")
    previous = world.data.get("unused_account_operations", {}).get(operation_id)
    if apply and previous is not None:
        return {**previous, "operation_id": operation_id, "already_completed": True,
                "accounts_after": len(world.data["players"])}
    at = time.time() if at is None else at
    preview = world.unused_accounts_preview(at=at, idle_seconds=idle_seconds)
    before = len(world.data["players"])
    print("UNUSED_ACCOUNT_CLEANUP_PREVIEW " + json.dumps({
        "operation_id": operation_id, "idle_seconds": idle_seconds,
        "as_of": at, "last_active_at_or_before": at - idle_seconds,
        "accounts_before": before, "eligible": preview["count"],
    }, sort_keys=True), flush=True)
    if not apply:
        return {"ok": True, "dry_run": True, "eligible": preview["count"],
                "accounts_before": before, "idle_seconds": idle_seconds}
    result = world.unused_accounts_delete({
        "confirmation": UNUSED_CONFIRMATION,
        "preview_id": preview["preview_id"], "count": preview["count"],
    }, at=at, operation_id=operation_id)
    after = len(world.data["players"])
    if before - after != result["deleted"]:
        raise RuntimeError("Cleanup account count verification failed.")
    if world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] != after:
        raise RuntimeError("Cleanup account/world verification failed.")
    if world.db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Cleanup foreign key verification failed.")
    if world.unused_accounts_preview(at=at, idle_seconds=idle_seconds)["count"]:
        raise RuntimeError("Cleanup left eligible unused accounts.")
    return {**result, "operation_id": operation_id,
            "accounts_before": before, "accounts_after": after, "verified": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-data", type=Path)
    parser.add_argument("--idle-hours", type=int, default=72)
    parser.add_argument("--operation-id")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args(argv)
    if args.idle_hours * 3600 < UNUSED_IDLE_SECONDS:
        parser.error("--idle-hours must be at least 48")
    if args.apply and not args.operation_id:
        parser.error("--apply requires --operation-id")
    if args.serve and args.local_data is not None:
        parser.error("--serve uses the hosted launcher only")
    directory, _, _ = configuration(args.local_data, None, dict(os.environ))
    database = directory / "private_test.sqlite3"
    if not database.is_file():
        raise RuntimeError("Existing world database required; refusing to create a world.")
    world_lock = WorldFileLock(directory)
    world = None
    try:
        # Refuse a different committed world before World can run any legacy
        # migration or historical launch reset.
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as reader:
            row = reader.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
            if not row or json.loads(row[0]).get("launch_reset_id") != app.LAUNCH_RESET_ID:
                raise RuntimeError("Unexpected committed world epoch; cleanup refused.")
        world = app.World(str(database), speed=float(os.environ.get("PGR_SPEED", "1")),
                          max_players=int(os.environ.get("PGR_MAX_PLAYERS", "0")),
                          apply_balance_reset=False)
        result = cleanup(world, idle_seconds=args.idle_hours * 3600,
                         operation_id=args.operation_id, apply=args.apply)
        world.close()
        world = None
        if args.apply:
            # Read the committed result through a fresh SQLite connection,
            # before releasing the exclusive world lock and starting the game.
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as verified:
                count = verified.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
                snapshot = json.loads(verified.execute("SELECT body FROM snapshot WHERE id=1").fetchone()[0])
                saved = snapshot.get("unused_account_operations", {}).get(args.operation_id)
                if (count != result["accounts_after"] or count != len(snapshot["players"])
                        or not saved or saved["deleted"] != result["deleted"]
                        or saved["backup"] != result["backup"]
                        or verified.execute("PRAGMA foreign_key_check").fetchall()
                        or verified.execute("PRAGMA quick_check").fetchall() != [("ok",)]):
                    raise RuntimeError("Cleanup committed-state verification failed.")
            result["persisted"] = True
        print("UNUSED_ACCOUNT_CLEANUP_RESULT " + json.dumps(result, sort_keys=True), flush=True)
    finally:
        if world is not None:
            world.close()
        world_lock.close()
    if args.serve:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).with_name("start_web.py"))])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

