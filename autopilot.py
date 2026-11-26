#!/usr/bin/env python3
"""Affiliate autopilot.

Every run (GitHub Actions runs it every 30 minutes):
  1. checks Telegram for your Publish / Redo / Skip taps
  2. if it's time and nothing is waiting, writes a new draft and sends it to you on Telegram
Nothing is published until you tap Publish.
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import cover
import llm
import sitegen
import telegram_io as tg

ROOT = Path(__file__).resolve().parent

DEFAULT_STATE = {
    "telegram_offset": 0,
    "pending": None,
    "used_topics": [],
    "extra_topics": [],
    "day_log": {"date": "", "drafted": 0, "published": 0},
}


def p(*parts):
    return ROOT.joinpath(*parts)


def load_json(path, default=None):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state():
    state = json.loads(json.dumps(DEFAULT_STATE))
    state.update(load_json(p("data", "state.json"), {}) or {})
    return state


def local_now(cfg, now=None):
    tz = ZoneInfo(cfg.get("timezone", "Asia/Kolkata"))
    return (now or datetime.now(tz)).astimezone(tz)


def check_config(cfg, demo):
    problems = []
    if "YOUR" in cfg["base_url"].upper():
        problems.append("config.json: set base_url to your real site address")
    if "YOUR" in cfg["amazon_tag"].upper():
        problems.append("config.json: set amazon_tag to your Amazon Associates store ID (ends with -21)")
    elif not cfg["amazon_tag"].endswith("-21"):
        print("Warning: Amazon India store IDs normally end with -21. Check amazon_tag.", file=sys.stderr)
    if problems and not demo:
        raise SystemExit("Fix this first:\n- " + "\n- ".join(problems))


# ---------------------------------------------------------------- topics
def pick_topic(cfg, state):
    used = {t.lower() for t in state["used_topics"]}
    topics = [
        line.strip()
        for line in p("topics.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ] + state.get("extra_topics", [])
    for t in topics:
        if t.lower() not in used:
            return t
    state["extra_topics"].extend(llm.suggest_topics(cfg, used))
    for t in state["extra_topics"]:
        if t.lower() not in used:
            return t
    raise RuntimeError("No topics left and the AI returned none.")


# ---------------------------------------------------------------- drafts
def draft_files(draft_id):
    return p("data", "drafts", f"{draft_id}.json"), p("data", "drafts", f"{draft_id}.jpg")


def discard_draft(draft_id):
    for f in draft_files(draft_id):
        if f.exists():
            f.unlink()


def preview_text(post):
    lines = ["READ IT, THEN TAP PUBLISH", "", post["title"], "", post["intro"], ""]
    for i, idea in enumerate(post["ideas"], 1):
        lines += [f"{i}. {idea['heading']}", idea["why_it_works"], f"(shop link: {idea['shop_query']})", ""]
    lines.append(post["closing"])
    return "\n".join(lines)[:3900]


def new_pending(cfg, state, topic, now, chat_id, redo_count=0):
    post = llm.generate_post(cfg, topic)
    post["topic"] = topic
    draft_id = now.strftime("%Y%m%d-%H%M%S")
    json_path, img_path = draft_files(draft_id)
    save_json(json_path, post)
    cover.make_cover(post["image_headline"], post["image_subline"], cfg["site_name"], topic, img_path)
    state["day_log"]["drafted"] += 1
    pending = {
        "id": draft_id,
        "topic": topic,
        "created_at": now.isoformat(),
        "redo_count": redo_count,
        "button_message_id": None,
    }
    if chat_id:
        tg.send_photo(chat_id, img_path, f"New draft: {post['title']}")
        msg = tg.send_message(
            chat_id,
            preview_text(post),
            buttons=[[("✅ Publish", f"approve:{draft_id}"), ("🔁 Redo", f"redo:{draft_id}"), ("⏭ Skip", f"skip:{draft_id}")]],
        )
        pending["button_message_id"] = msg["message_id"]
    state["pending"] = pending
    return pending


def publish(cfg, draft_id, now):
    json_path, img_path = draft_files(draft_id)
    post = load_json(json_path)
    slug = sitegen.unique_slug(ROOT, post["title"])
    post["slug"] = slug
    post["date_iso"] = now.isoformat(timespec="seconds")
    save_json(p("data", "posts", f"{slug}.json"), post)
    (p("docs", "images")).mkdir(parents=True, exist_ok=True)
    shutil.copy(img_path, p("docs", "images", f"{slug}.jpg"))
    sitegen.rebuild(cfg, ROOT)
    discard_draft(draft_id)
    return f"{cfg['base_url'].rstrip('/')}/posts/{slug}.html"


# ---------------------------------------------------------------- telegram taps
def handle_callback(cfg, state, chat_id, cq, now):
    if str(cq["from"]["id"]) != str(chat_id):
        tg.answer_callback(cq["id"], "Not allowed")
        return
    action, _, draft_id = (cq.get("data") or "").partition(":")
    pending = state.get("pending")
    if not pending or pending["id"] != draft_id:
        tg.answer_callback(cq["id"], "This draft is no longer active.")
        tg.clear_buttons(chat_id, (cq.get("message") or {}).get("message_id"))
        return

    if action == "redo" and pending["redo_count"] >= 2:
        tg.answer_callback(cq["id"], "Redo limit reached")
        tg.send_message(chat_id, "Redo limit reached for this topic. Tap Publish or Skip.")
        return

    tg.answer_callback(cq["id"], "Got it")
    tg.clear_buttons(chat_id, pending.get("button_message_id"))

    if action == "approve":
        url = publish(cfg, draft_id, now)
        state["pending"] = None
        state["day_log"]["published"] += 1
        tg.send_message(chat_id, f"Published. It goes live in about a minute:\n{url}")
    elif action == "skip":
        discard_draft(draft_id)
        state["pending"] = None
        tg.send_message(chat_id, "Skipped. A different topic will be drafted on a later run.")
    elif action == "redo":
        discard_draft(draft_id)
        state["pending"] = None
        tg.send_message(chat_id, "Rewriting this one...")
        new_pending(cfg, state, pending["topic"], now, chat_id, pending["redo_count"] + 1)


def process_updates(cfg, state, chat_id, now):
    for u in tg.get_updates(state["telegram_offset"]):
        state["telegram_offset"] = max(state["telegram_offset"], u["update_id"] + 1)
        if "callback_query" in u:
            handle_callback(cfg, state, chat_id, u["callback_query"], now)
        elif "message" in u:
            m = u["message"]
            if str(m.get("chat", {}).get("id")) == str(chat_id) and (m.get("text") or "").startswith("/start"):
                tg.send_message(chat_id, "Autopilot is connected. Each day I'll send a draft here. Read it, then tap Publish.")


# ---------------------------------------------------------------- main loop
def maybe_create_draft(cfg, state, chat_id, now, force=False):
    pending = state.get("pending")
    if pending:
        age = now - datetime.fromisoformat(pending["created_at"])
        if age <= timedelta(hours=cfg.get("pending_expiry_hours", 48)):
            return None
        if chat_id:
            tg.clear_buttons(chat_id, pending.get("button_message_id"))
            tg.send_message(chat_id, "The last draft expired without an answer, so I dropped it.")
        discard_draft(pending["id"])
        state["pending"] = None
    d = state["day_log"]
    if not force:
        if now.hour < cfg.get("start_hour", 8):
            return None
        if d["published"] >= cfg.get("posts_per_day", 1):
            return None
        if d["drafted"] >= cfg.get("max_drafts_per_day", 3):
            return None
    topic = pick_topic(cfg, state)
    state["used_topics"].append(topic)
    return new_pending(cfg, state, topic, now, chat_id)


def run_once(cfg, state, demo=False, force=False, now=None):
    now = local_now(cfg, now)
    today = now.date().isoformat()
    if state["day_log"].get("date") != today:
        state["day_log"] = {"date": today, "drafted": 0, "published": 0}
    chat_id = None
    if not demo:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not (os.environ.get("TELEGRAM_BOT_TOKEN") and chat_id):
            raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set (see README step 5).")
        process_updates(cfg, state, chat_id, now)
    created = maybe_create_draft(cfg, state, chat_id, now, force=force)
    if demo and created:
        url = publish(cfg, created["id"], now)
        state["pending"] = None
        state["day_log"]["published"] += 1
        print("Demo post published locally:", url)
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="offline test: fake AI, no Telegram, publishes locally")
    ap.add_argument("--force", action="store_true", help="draft now even outside the daily schedule")
    ap.add_argument("--rebuild", action="store_true", help="regenerate the website from saved posts")
    args = ap.parse_args()

    cfg = load_json(p("config.json"))
    if args.demo:
        os.environ["LLM_PROVIDER"] = "mock"
    check_config(cfg, args.demo)

    if args.rebuild:
        print("Rebuilt", sitegen.rebuild(cfg, ROOT), "posts")
        return

    if not args.demo:
        sitegen.rebuild(cfg, ROOT)  # config changes (tag, name, Pinterest code) show up on the site automatically

    state = load_state()
    try:
        run_once(cfg, state, demo=args.demo, force=args.force or args.demo)
    finally:
        save_json(p("data", "state.json"), state)


if __name__ == "__main__":
    main()
