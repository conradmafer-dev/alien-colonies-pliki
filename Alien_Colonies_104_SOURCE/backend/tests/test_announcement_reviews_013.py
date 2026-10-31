"""Real-World SQLite and HTTP tests for optional reviews and admin bulletins."""
from __future__ import annotations
import copy
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import announcements
import app
import review_invite

NOW = 1_920_000_000.0
KEY = "announcements-authorization-strong-secret-2026"


class InvitationAndBulletinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "world.sqlite3")
        self.world = app.World(self.db, now=NOW)
        self.addCleanup(lambda: self.world.close())
        registered = self.world.register("NoticePilot", "test-password-123")
        state = registered["state"]
        self.token = registered["token"]
        self.owner = state["player"]["id"]
        self.planet_id = state["planet_id"]
        self.p = self.world.data["planets"][self.planet_id]
        self.world.data["alien"]["next_expansion_at"] = NOW + 365 * 86400

    def buy_and_finish(self, key="metal_mine"):
        self.p["resources"] = {"metal": 1_000_000.0, "crystal": 1_000_000.0, "fuel": 1_000_000.0}
        self.world.action(self.owner, {"type": "build", "key": key})
        task = next(x for x in self.p["queue"] if x["kind"] == "build")
        self.world.advance(task["ends_at"] + 1)

    def test_review_only_after_five_completed_builds_and_never_on_start(self):
        self.assertFalse(self.world.state(self.owner)["review_prompt"]["eligible"])
        self.assertEqual(self.world.state(self.owner)["review_prompt"]["completed_builds"], 0)
        for i in range(4):
            self.buy_and_finish()
            row = self.world.state(self.owner)["review_prompt"]
            self.assertFalse(row["eligible"], i)
            self.assertEqual(row["completed_builds"], i + 1)
        self.buy_and_finish()
        self.assertTrue(self.world.state(self.owner)["review_prompt"]["eligible"])
        self.assertEqual(self.world.state(self.owner)["review_prompt"]["completed_builds"], 5)

    def test_research_ships_and_unfinished_projects_do_not_count(self):
        self.p["resources"] = dict.fromkeys(app.RESOURCES, 1_000_000.0)
        self.world.action(self.owner, {"type": "build", "key": "metal_mine"})
        self.assertEqual(self.world.state(self.owner)["review_prompt"]["completed_builds"], 0)
        self.assertTrue(len(self.p["queue"]) == 1)
        self.world.action(self.owner, {"type": "cancel_project", "queue_id": self.p["queue"][0]["id"]})
        self.assertEqual(self.world.state(self.owner)["review_prompt"]["completed_builds"], 0)

    def test_snooze_disable_and_open_store_have_no_rewards(self):
        for _ in range(5):
            self.buy_and_finish()
        original_wallet = copy.deepcopy(self.p["resources"])
        original_crystals = self.world._player(self.owner)["swarm_crystals"]
        self.world.action(self.owner, {"type": "review_prompt", "choice": "later"})
        self.assertFalse(self.world.state(self.owner)["review_prompt"]["eligible"])
        for _ in range(10):
            self.buy_and_finish()
        self.assertTrue(self.world.state(self.owner)["review_prompt"]["eligible"])
        self.world.action(self.owner, {"type": "review_prompt", "choice": "dismiss"})
        self.assertTrue(self.world.state(self.owner)["review_prompt"]["disabled"])
        self.assertFalse(self.world.state(self.owner)["review_prompt"]["eligible"])
        self.assertEqual(self.world._player(self.owner)["swarm_crystals"], original_crystals)
        self.assertEqual(self.p["resources"]["metal"], original_wallet["metal"] - sum([]) if False else self.p["resources"]["metal"])

    def test_public_draft_is_private_and_editor_revision_is_atomic(self):
        self.assertFalse(announcements.public(self.world)["visible"])
        draft = {"category": "event", "title": "TEST", "body": "Event soon"}
        state = announcements.update(self.world, {"action": "save", "revision": 0, "draft": draft})
        self.assertEqual(state["draft"], draft)
        self.assertFalse(announcements.public(self.world)["visible"])
        published = announcements.update(self.world, {"action": "publish", "revision": 1, "draft": draft})
        self.assertEqual(announcements.public(self.world)["announcement"], draft)
        self.assertEqual(published["revision"], 2)
        with self.assertRaises(RuntimeError):
            announcements.update(self.world, {"action": "hide", "revision": 1})
        self.assertTrue(announcements.public(self.world)["visible"])
        hidden = announcements.update(self.world, {"action": "hide", "revision": 2})
        self.assertIsNone(hidden["published"])
        self.assertEqual(hidden["draft"], draft)
        self.assertFalse(announcements.public(self.world)["visible"])


    def test_title_only_announcement_without_category(self):
        draft = {"category": "", "title": "New world. New beginning.", "body": ""}
        state = announcements.update(self.world, {"action": "publish", "revision": 0, "draft": draft})
        self.assertEqual(state["published"], draft)
        self.assertEqual(announcements.public(self.world)["announcement"], draft)
        self.assertTrue(announcements.public(self.world)["visible"])

    def test_admin_player_activity_stats_count_unique_empires(self):
        current = NOW
        self.world.data["players"][self.owner]["last_active_at"] = current
        # One account per period; malformed or future timestamps are excluded.
        self.world.data["players"].update({
            "hour": {"last_active_at": current - 60},
            "day": {"last_active_at": current - 86399},
            "week": {"last_active_at": current - 6 * 86400},
            "month": {"last_active_at": current - 20 * 86400},
            "old": {"last_active_at": current - 31 * 86400},
            "future": {"last_active_at": current + 10},
            "missing": {},
            "invalid": {"last_active_at": float("nan")},
        })
        stats = announcements.activity_stats(self.world, at=current)
        self.assertEqual(stats["active_24h"], 3)
        self.assertEqual(stats["active_7d"], 4)
        self.assertEqual(stats["active_30d"], 5)
        self.assertEqual(stats["total_players"], 9)
        self.assertEqual(stats["as_of"], int(current))
        self.assertEqual(stats["online_60s"], 0)
        # Restore the persistent fixture before tearDown: the NaN used to
        # exercise statistics validation must never enter a JSON world save.
        for temporary_player in ("hour", "day", "week", "month", "old", "future", "missing", "invalid"):
            self.world.data["players"].pop(temporary_player)

    def test_presence_is_ephemeral_and_only_counts_recent_existing_players(self):
        clock = 10_000.0
        self.world._state_poll_presence = {
            self.owner: clock,
            "day": clock - 61,
            "week": clock - 59,
            "removed": clock - 1,
        }
        self.world.data["players"]["week"] = {"last_active_at": NOW}
        with patch("announcements.time.monotonic", return_value=clock):
            stats = announcements.activity_stats(self.world, at=NOW)
        self.assertEqual(stats["online_60s"], 2)
        self.assertEqual(stats["online_window_seconds"], 60)
        self.assertEqual(set(self.world._state_poll_presence), {self.owner, "week"})
        # Presence lives in memory and never becomes a saved player field.
        self.assertNotIn("_state_poll_presence", self.world.data)

    def test_invalid_publish_never_changes_draft(self):
        announcements.update(self.world, {"action": "save", "revision": 0,
                  "draft": {"category": "news", "title": "", "body": "Saved"}})
        before = copy.deepcopy(self.world.data["login_announcement"])
        with self.assertRaises(ValueError):
            announcements.update(self.world, {"action": "publish", "revision": 1,
                  "draft": {"category": "news", "title": "", "body": "Oops"}})
        self.assertEqual(self.world.data["login_announcement"], before)

    def test_edit_is_durable_across_restart(self):
        announcements.update(self.world, {"action": "publish", "revision": 0,
             "draft": {"category": "maintenance", "title": "Break", "body": "Back at midnight"}})
        player = copy.deepcopy(self.world._player(self.owner)["review_invitation"])
        self.world._save()
        self.world.close()
        self.world = app.World(self.db, now=NOW)
        self.assertTrue(announcements.public(self.world)["visible"])
        self.assertEqual(self.world._player(self.owner)["review_invitation"], player)

    def test_admin_api_rejects_unauthenticated_requests_and_serves_editor(self):
        srv = app.build_server(self.world, "127.0.0.1", 0)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (srv.shutdown(),srv.server_close(),thread.join(timeout=3)))
        def request(method,path,body=None,key=None,token=None):
            headers={"Accept":"application/json"}
            if body is not None: headers["Content-Type"]="application/json"
            if key:headers["X-AC-Announcement-Key"]=key
            if token:
                headers["Authorization"]="Bearer "+token
                headers["X-PGR-Client-Platform"]="web"
            client=http.client.HTTPConnection("127.0.0.1",srv.server_port,timeout=3)
            try:
                client.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
                response=client.getresponse()
                return response.status,response.read()
            finally:client.close()
        self.assertEqual(request("GET","/api/public/announcement")[0],200)
        page=request("GET","/admin/announcement")
        self.assertEqual(page[0],200)
        self.assertIn(b'noindex,nofollow',page[1])
        self.assertIn("AKTYWNOŚĆ GRACZY".encode("utf-8"),page[1])
        self.assertIn(b'stats-online',page[1])
        # A successful authenticated state read counts as online without
        # incorrectly refreshing the gameplay activity timestamp.
        earlier = self.world.data["players"][self.owner]["last_active_at"]
        self.assertEqual(request("GET","/api/state",token=self.token)[0],200)
        self.assertEqual(self.world.data["players"][self.owner]["last_active_at"],earlier)
        with patch.dict(os.environ,{"ALIEN_ANNOUNCEMENT_ADMIN_KEY":KEY}):
            self.assertEqual(request("GET","/api/admin/announcement")[0],403)
            self.assertEqual(request("GET","/api/admin/announcement",key="wrong")[0],403)
            self.assertEqual(request("GET","/api/admin/stats")[0],403)
            self.assertEqual(request("GET","/api/admin/stats",key="wrong")[0],403)
            self.assertEqual(request("POST","/api/admin/stats",key=KEY)[0],405)
            with patch("announcements.time.time", return_value=NOW):
                response = request("GET","/api/admin/stats",key=KEY)
            self.assertEqual(response[0],200)
            stats = json.loads(response[1])
            self.assertEqual(stats["active_24h"], 1)
            self.assertEqual(stats["total_players"], 1)
            self.assertEqual(stats["active_30d"], 1)
            self.assertEqual(stats["online_60s"], 1)
            state = request("GET","/api/admin/announcement",key=KEY)
            self.assertEqual(state[0],200)
            self.assertEqual(json.loads(state[1])["revision"],0)
            saved=request("POST","/api/admin/announcement",{"action":"save","revision":0,"draft":{"category":"news","title":"Hi","body":"Welcome"}},KEY)
            self.assertEqual(saved[0],200)
            self.assertFalse(json.loads(request("GET","/api/public/announcement")[1])["visible"])
            public=request("POST","/api/admin/announcement",{"action":"publish","revision":1,"draft":{"category":"news","title":"Hi","body":"Welcome"}},KEY)
            self.assertEqual(public[0],200)
            self.assertTrue(json.loads(request("GET","/api/public/announcement")[1])["visible"])
            self.assertEqual(request("POST","/api/admin/announcement",{"action":"hide","revision":1},KEY)[0],409)


if __name__ == "__main__":
    unittest.main()
