"""Offline test of the approval flow with a fake Telegram and a fake AI.  Run:  python tests/test_flow.py"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC))

tmp = Path(tempfile.mkdtemp())
for name in ("config.json", "topics.txt"):
    shutil.copy(SRC / name, tmp / name)
for d in ("data/drafts", "data/posts", "docs/images", "docs/posts"):
    (tmp / d).mkdir(parents=True)

os.environ.update(LLM_PROVIDER="mock", TELEGRAM_BOT_TOKEN="x", TELEGRAM_CHAT_ID="42")

import autopilot as ap  # noqa: E402
import telegram_io as tg  # noqa: E402

ap.ROOT = tmp
IST = ZoneInfo("Asia/Kolkata")


class Fake:
    def __init__(self):
        self.sent, self.queue, self.cleared, self.uid = [], [], [], 0

    def send_photo(self, chat, path, caption=""):
        self.sent.append(("photo", caption)); return {"message_id": self._id()}

    def send_message(self, chat, text, buttons=None):
        self.sent.append(("msg", text, buttons)); return {"message_id": self._id()}

    def _id(self):
        self.uid += 1; return 100 + self.uid

    def get_updates(self, offset):
        out = [u for u in self.queue if u["update_id"] >= offset]; return out

    def answer_callback(self, *a, **k): pass

    def clear_buttons(self, chat, mid): self.cleared.append(mid)

    def tap(self, action, draft_id, user=42):
        n = len(self.queue) + 1
        self.queue.append({"update_id": n, "callback_query": {"id": f"cb{n}", "from": {"id": user}, "data": f"{action}:{draft_id}", "message": {"message_id": 1}}})


fake = Fake()
for fn in ("send_photo", "send_message", "get_updates", "answer_callback", "clear_buttons"):
    setattr(tg, fn, getattr(fake, fn))

cfg = ap.load_json(tmp / "config.json")
state = ap.load_state()
at = lambda day, hh, mm=0: datetime(2026, 11, day, hh, mm, tzinfo=IST)
n_posts = lambda: len(list((tmp / "data" / "posts").glob("*.json")))
ok = lambda cond, msg: (print(("PASS " if cond else "FAIL ") + msg), cond or sys.exit(1))

# 1. before 8am nothing happens
ap.run_once(cfg, state, now=at(27, 7)); ok(state["pending"] is None, "no draft before start hour")
# 2. morning: draft is created and sent with 3 buttons
ap.run_once(cfg, state, now=at(27, 9)); pid = state["pending"]["id"]
ok(state["pending"] and fake.sent[-1][2][0][0][1].startswith("approve:"), "draft sent with Publish/Redo/Skip buttons")
# 3. no second draft while one is waiting
before = len(fake.sent); ap.run_once(cfg, state, now=at(27, 9, 30)); ok(len(fake.sent) == before, "no new draft while waiting")
# 4. stranger tapping is ignored
fake.tap("approve", pid, user=999); ap.run_once(cfg, state, now=at(27, 10)); ok(state["pending"] and n_posts() == 0, "other users cannot publish")
# 5. owner approves -> published
fake.tap("approve", pid); ap.run_once(cfg, state, now=at(27, 10, 30))
ok(state["pending"] is None and n_posts() == 1 and (tmp / "docs" / "feed.xml").exists(), "approve publishes post and rebuilds site")
# 6. daily limit
before = len(fake.sent); ap.run_once(cfg, state, now=at(27, 15)); ok(len(fake.sent) == before, "daily post limit respected")
# 7. next day, redo twice then limit
ap.run_once(cfg, state, now=at(28, 9)); first = state["pending"]["id"]
fake.tap("redo", first); ap.run_once(cfg, state, now=at(28, 9, 30)); second = state["pending"]["id"]
ok(second != first and state["pending"]["redo_count"] == 1 and not ap.draft_files(first)[0].exists(), "redo replaces the draft")
fake.tap("redo", second); ap.run_once(cfg, state, now=at(28, 10)); third = state["pending"]["id"]
fake.tap("redo", third); ap.run_once(cfg, state, now=at(28, 10, 30))
ok(state["pending"]["id"] == third and "Redo limit" in fake.sent[-1][1], "third redo is refused, buttons stay")
# 8. stale tap ignored
fake.tap("approve", first); ap.run_once(cfg, state, now=at(28, 11)); ok(state["pending"]["id"] == third and n_posts() == 1, "stale buttons do nothing")
# 9. skip -> later run drafts a different topic
fake.tap("skip", third); ap.run_once(cfg, state, now=at(28, 11, 30))
ok(state["day_log"]["drafted"] == 4 or state["pending"] is None, "skip clears pending")
ap.run_once(cfg, state, now=at(29, 9)); ok(state["pending"] is not None, "new day drafts again")
topics = state["used_topics"]; ok(len(topics) == len(set(topics)), "topics are never repeated")
# 10. expiry
ap.run_once(cfg, state, now=at(29, 9) + timedelta(hours=60)); ok(state["pending"] is not None and "expired" in " ".join(s[1] for s in fake.sent if s[0] == "msg"), "unanswered draft expires, new one created")
print("ALL TESTS PASSED")
