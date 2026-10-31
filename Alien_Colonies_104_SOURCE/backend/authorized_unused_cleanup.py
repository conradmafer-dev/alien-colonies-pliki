"""Explicit, one-use operator launcher for the confirmed 2026-10-25 cleanup.

Normal start_web.py never imports or invokes this module. The operator selects
this launcher for one deployment, then restores the normal start command.
No administrator secret or player credentials are read, printed or changed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import accounts
import app
import run


AUTHORIZED_AT = 0.0  # Disabled: the owner cancelled this maintenance operation.
OPERATION_ID = "unused-48h-cancelled-20261025T154619Z"
EXPECTED_EPOCH = "new-beginning-20261019"
EXPECTED_SERVICE = "afef85ed-1983-464b-9e57-767540be5997"
LOG_PREFIX = "AC_UNUSED_48H "


def perform(world, *, as_of=AUTHORIZED_AT, operation_id=OPERATION_ID, clock=None):
    """Use the reviewed preview/delete path and never widen its time cohort."""
    clock = time.time() if clock is None else clock
    if world.data.get("launch_reset_id") != EXPECTED_EPOCH:
        raise RuntimeError("Unexpected world epoch; no account cleanup attempted")
    audit = world.data.get("unused_account_cleanups", [])
    done = next((item for item in audit if item.get("at") == as_of), None)
    if done is not None:
        return {"operation_id": operation_id, "status": "already_completed",
                "deleted": done["count"], "backup": done.get("backup"),
                "remaining_players": len(world.data["players"])}
    if not 0 <= clock - as_of <= 3600:
        raise RuntimeError("One-use cleanup authorization window expired")
    before = len(world.data["players"])
    preview = world.unused_accounts_preview(at=as_of)
    print(LOG_PREFIX + json.dumps({"operation_id": operation_id, "status": "preview",
          "as_of": as_of, "idle_seconds": accounts.UNUSED_IDLE_SECONDS,
          "candidates": preview["count"], "total_players": before}), flush=True)
    result = world.unused_accounts_delete({"preview_id": preview["preview_id"],
        "count": preview["count"], "confirmation": accounts.UNUSED_CONFIRMATION}, at=as_of)
    if result["deleted"] == 0:
        # The existing delete method does not persist an empty selection. Record
        # its completion so a restart still cannot create a later deletion job.
        with world.lock, world._atomic():
            audit = world.data.setdefault("unused_account_cleanups", [])
            audit.append({"at": as_of, "count": 0, "backup": None})
            del audit[:-32]
    remaining = len(world.data["players"])
    sql_accounts = world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if remaining != before - result["deleted"] or sql_accounts != remaining:
        raise RuntimeError("Cleanup account count verification failed")
    return {"operation_id": operation_id, "status": "completed", "as_of": as_of,
            "deleted": result["deleted"], "backup": result["backup"],
            "remaining_players": remaining, "previous_players": before}


def execute_hosted():
    if os.environ.get("RAILWAY_SERVICE_ID") != EXPECTED_SERVICE:
        raise RuntimeError("This one-use job belongs to a different service")
    directory, argv, _ = run.configuration(None, None, dict(os.environ))
    database = Path(argv[argv.index("--db") + 1])
    if not database.is_file():
        raise RuntimeError("Existing production database is missing; refusing to create one")
    guard = run.WorldFileLock(directory)
    world = None
    try:
        # Check the existing committed epoch BEFORE any World migration/simulation.
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as reader:
            row = reader.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
            if not row or json.loads(row[0]).get("launch_reset_id") != EXPECTED_EPOCH:
                raise RuntimeError("Unexpected committed world; cleanup refused")
        world = app.World(database, speed=float(os.environ.get("PGR_SPEED", "1")),
                          max_players=int(os.environ.get("PGR_MAX_PLAYERS", "0")),
                          apply_balance_reset=False)
        result = perform(world)
        print(LOG_PREFIX + json.dumps(result, sort_keys=True), flush=True)
    finally:
        if world is not None:
            world.close()
        guard.close()


if __name__ == "__main__":
    try:
        execute_hosted()
    except Exception as error:
        # A failed cleanup must not prevent the regular game from starting.
        print(LOG_PREFIX + json.dumps({"operation_id": OPERATION_ID,
              "status": "failed", "error_type": type(error).__name__,
              "error": str(error)}), flush=True)
    os.execv(sys.executable, [sys.executable, str(Path(__file__).with_name("start_web.py"))])
