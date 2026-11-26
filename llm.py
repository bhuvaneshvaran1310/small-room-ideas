"""Talks to the AI (Gemini or Claude) and checks what comes back before anything is published."""
import json
import os
import re
import time

import requests

SYSTEM = (
    "You write practical, honest home and interior design guides for readers in India, in plain English. "
    "You think like a trained architect or interior designer: explain WHY an idea works "
    "(light, circulation, proportion, storage, materials, ergonomics) instead of hyping products. "
    "Reply with ONLY one valid JSON object. No markdown, no commentary."
)

SCHEMA = """{
  "title": "SEO-friendly title, max 70 characters",
  "meta_description": "max 150 characters",
  "intro": "60-90 words. Plain, specific, no hype.",
  "ideas": [
    {
      "heading": "Short idea name, max 8 words",
      "why_it_works": "40-70 words of real design reasoning. Specific to Indian homes where relevant.",
      "shop_query": "2-5 word generic product TYPE to search on Amazon, lowercase, no brand names (e.g. foldable study table)",
      "shop_label": "Button text like: Browse foldable study tables on Amazon"
    }
  ],
  "closing": "30-50 words, practical next step",
  "pin_title": "Pinterest title, max 90 characters",
  "pin_description": "Pinterest description, max 280 characters, 2-3 natural keywords",
  "image_headline": "Cover image headline, max 8 words",
  "image_subline": "Cover image subline, max 6 words"
}"""

RULES = """Rules (all of them are mandatory):
- Write exactly 6 ideas. Each idea is a product TYPE a reader can shop for. Never name brands or models.
- NO prices, NO currency symbols, NO discounts, NO words like deal, sale, cheap, bestseller, top-rated, guarantee.
- Never say or imply that you tested, owned, used or reviewed anything. No first-person experience claims.
- Do not invent statistics, studies, certifications or product specifications. Share only general, well-known design logic.
- Avoid structural, electrical, fire-safety or medical claims. If something needs it, say to check with a qualified professional.
- Do not make promises about results. No exaggeration.
- Keep the tone calm, specific and useful."""

# Amazon's rules are strict about prices and promises, so these are rejected automatically.
BANNED = re.compile(
    r"(₹|\brs\.?\s?\d|\binr\b|\bprices?\b|\bpriced\b|discount|\bdeals?\b|%\s?off|\bcheap|\bsales?\b|"
    r"lowest|coupon|limited[- ]time|best[- ]?seller|top[- ]rated|guarantee)",
    re.I,
)
EXPERIENCE = re.compile(
    r"\b(i|we)\s+(tried|tested|used|bought|reviewed|own|love|loved|recommend)\b|\bin my experience\b|\bpersonally\b",
    re.I,
)


def _post_json(url, headers, payload, tries=3):
    last = ""
    for i in range(tries):
        r = requests.post(url, headers=headers, json=payload, timeout=180)
        if r.status_code in (429, 500, 502, 503, 529) and i < tries - 1:
            time.sleep(15 * (i + 1))
            continue
        if r.status_code >= 400:
            last = f"LLM API error {r.status_code}: {r.text[:400]}"
            raise RuntimeError(last)
        return r.json()
    raise RuntimeError(last or "LLM API failed")


def _anthropic(system, prompt, max_tokens):
    model = os.environ.get("LLM_MODEL") or "claude-haiku-5-5"
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "x-api-key": os.environ["LLM_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")


def _gemini(system, prompt, max_tokens):
    model = os.environ.get("LLM_MODEL") or "gemini-2.5-flash"
    data = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"x-goog-api-key": os.environ["LLM_API_KEY"], "content-type": "application/json"},
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max(max_tokens, 8000),
                "responseMimeType": "application/json",
                "temperature": 0.8,
            },
        },
    )
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def call_llm(system, prompt, max_tokens=4000):
    provider = (os.environ.get("LLM_PROVIDER") or "gemini").strip().lower()
    if provider == "mock":
        return _mock(prompt)
    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("LLM_API_KEY is not set. Add it as a secret (see README).")
    if provider in ("anthropic", "claude"):
        return _anthropic(system, prompt, max_tokens)
    if provider == "gemini":
        return _gemini(system, prompt, max_tokens)
    raise SystemExit(f"Unknown LLM_PROVIDER '{provider}'. Use gemini or anthropic.")


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    arr_start, arr_end = text.find("["), text.rfind("]")
    if start == -1 and arr_start != -1:
        return json.loads(text[arr_start : arr_end + 1])
    if start != -1 and (arr_start == -1 or start < arr_start):
        return json.loads(text[start : end + 1])
    return json.loads(text[arr_start : arr_end + 1])


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _clip(text, n):
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut


def normalize(post):
    post["title"] = _clip(post.get("title", ""), 80)
    post["meta_description"] = _clip(post.get("meta_description", ""), 155)
    post["pin_title"] = _clip(post.get("pin_title", "") or post["title"], 95)
    post["pin_description"] = _clip(post.get("pin_description", ""), 290)
    post["image_headline"] = _clip(post.get("image_headline", "") or post["title"], 60)
    post["image_subline"] = _clip(post.get("image_subline", ""), 40)
    for k in ("intro", "closing"):
        post[k] = " ".join(str(post.get(k, "")).split())
    for idea in post.get("ideas", []):
        for k in ("heading", "why_it_works", "shop_query", "shop_label"):
            idea[k] = " ".join(str(idea.get(k, "")).split())
        idea["shop_query"] = idea["shop_query"].lower()
        idea["heading"] = _clip(idea["heading"], 70)
    return post


def validate(post):
    problems = []
    for k in ("title", "meta_description", "intro", "closing", "pin_title", "pin_description",
              "image_headline"):
        if not post.get(k):
            problems.append(f"missing {k}")
    ideas = post.get("ideas")
    if not isinstance(ideas, list) or not 5 <= len(ideas) <= 8:
        problems.append("need 5-8 ideas")
        return problems
    wc = lambda s: len(s.split())
    if not 35 <= wc(post["intro"]) <= 130:
        problems.append("intro should be about 60-90 words")
    for i, idea in enumerate(ideas, 1):
        for k in ("heading", "why_it_works", "shop_query", "shop_label"):
            if not idea.get(k):
                problems.append(f"idea {i} missing {k}")
        if idea.get("why_it_works") and not 20 <= wc(idea["why_it_works"]) <= 120:
            problems.append(f"idea {i} text should be about 40-70 words")
        if idea.get("shop_query") and not 1 <= wc(idea["shop_query"]) <= 6:
            problems.append(f"idea {i} shop_query should be 2-5 words")
    blob = "\n".join(_strings(post))
    m = BANNED.search(blob)
    if m:
        problems.append(f"contains banned wording: '{m.group(0)}'")
    m = EXPERIENCE.search(blob)
    if m:
        problems.append(f"claims personal experience: '{m.group(0)}'")
    return problems


def generate_post(cfg, topic, attempts=3):
    notes = ""
    last_problems = []
    for _ in range(attempts):
        prompt = (
            f"Site niche: {cfg['niche']}.\nTopic: {topic}\n\n"
            f"Write one guide as JSON matching this shape:\n{SCHEMA}\n\n{RULES}\n{notes}"
        )
        raw = call_llm(SYSTEM, prompt)
        try:
            post = normalize(extract_json(raw))
        except Exception as exc:  # bad JSON -> try again
            last_problems = [f"invalid JSON ({exc})"]
            notes = "\nYour previous answer was not valid JSON. Reply with one JSON object only."
            continue
        last_problems = validate(post)
        if not last_problems:
            return post
        notes = "\nYour previous answer was rejected: " + "; ".join(last_problems) + ". Fix these."
    raise RuntimeError("Could not get a clean draft from the AI: " + "; ".join(last_problems))


def suggest_topics(cfg, used):
    prompt = (
        f"Site niche: {cfg['niche']}.\n"
        "Suggest 30 new guide topics a reader might search for. Each topic is one plain sentence fragment, "
        "specific, practical, India-relevant, and not a duplicate of these used topics:\n"
        + "\n".join(f"- {u}" for u in list(used)[-80:])
        + "\n\nReply with ONLY a JSON array of strings."
    )
    raw = call_llm(SYSTEM, prompt, max_tokens=3000)
    items = extract_json(raw)
    return [" ".join(str(t).split()) for t in items if str(t).strip()][:30]


# ---------- offline mock used by --demo and the tests ----------
_MOCK_TYPES = [
    ("foldable study table", "Browse foldable study tables on Amazon"),
    ("wall mounted shelf", "Browse wall mounted shelves on Amazon"),
    ("under bed storage box", "Browse under bed storage boxes on Amazon"),
    ("storage ottoman", "Browse storage ottomans on Amazon"),
    ("clip on desk lamp", "Browse clip on desk lamps on Amazon"),
    ("over door hooks", "Browse over door hooks on Amazon"),
]
_FILL = (
    "Think about how you move through the room before you add anything to it, because clear walking space "
    "and a few well placed vertical surfaces usually matter more than the number of items you own. "
    "Pick pieces that fold, stack or tuck away so the floor stays open for daily use."
)


def _mock(prompt):
    if "Reply with ONLY a JSON array" in prompt:
        return json.dumps([f"Mock topic number {i}" for i in range(1, 6)])
    topic = re.search(r"Topic: (.*)", prompt).group(1).strip()
    ideas = [
        {
            "heading": f"Idea {i}: {q.title()}",
            "why_it_works": _FILL,
            "shop_query": q,
            "shop_label": lab,
        }
        for i, (q, lab) in enumerate(_MOCK_TYPES, 1)
    ]
    return json.dumps(
        {
            "title": topic[:70],
            "meta_description": f"Six practical ideas: {topic}.",
            "intro": (_FILL + " " + "This guide walks through six ideas and the reasoning behind each one."),
            "ideas": ideas,
            "closing": "Start with one change, live with it for a week, and only then add the next piece. "
            "Small steps keep a compact home calm.",
            "pin_title": topic[:90],
            "pin_description": f"{topic}. Six practical ideas with the design reasoning behind each.",
            "image_headline": topic[:60],
            "image_subline": "Six practical ideas",
        }
    )
