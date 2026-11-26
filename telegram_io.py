"""Tiny Telegram Bot API wrapper. Only what the autopilot needs."""
import json
import os

import requests


def _url(method):
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"


def _check(r):
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")
    return data["result"]


def _markup(buttons):
    if not buttons:
        return None
    return json.dumps(
        {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
    )


def send_message(chat_id, text, buttons=None):
    payload = {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}
    mk = _markup(buttons)
    if mk:
        payload["reply_markup"] = mk
    return _check(requests.post(_url("sendMessage"), data=payload, timeout=60))


def send_photo(chat_id, path, caption=""):
    with open(path, "rb") as fh:
        r = requests.post(
            _url("sendPhoto"),
            data={"chat_id": chat_id, "caption": caption[:1000]},
            files={"photo": fh},
            timeout=120,
        )
    return _check(r)


def get_updates(offset):
    r = requests.post(
        _url("getUpdates"),
        data={"offset": offset, "timeout": 0, "allowed_updates": json.dumps(["callback_query", "message"])},
        timeout=60,
    )
    return _check(r)


def answer_callback(callback_id, text=""):
    try:
        requests.post(_url("answerCallbackQuery"), data={"callback_query_id": callback_id, "text": text}, timeout=30)
    except Exception:
        pass


def clear_buttons(chat_id, message_id):
    """Best effort: remove the buttons from an old message."""
    if not message_id:
        return
    try:
        requests.post(
            _url("editMessageReplyMarkup"),
            data={"chat_id": chat_id, "message_id": message_id, "reply_markup": json.dumps({"inline_keyboard": []})},
            timeout=30,
        )
    except Exception:
        pass
