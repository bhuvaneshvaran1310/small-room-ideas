# Affiliate Autopilot

Every day it writes one home-and-interiors guide, sends it to your **Telegram** with three buttons
(**Publish / Redo / Skip**), and when you tap Publish it puts the guide on your free website.
Pinterest then turns each new guide into a pin automatically. Your job: read it, tap once.

Runs free on GitHub, so your laptop can stay off.

```
AI writes draft -> Telegram: you tap Publish -> website updates -> Pinterest auto-pins from the feed
```

## Read this first (honest limits)

- **No one can promise sales.** Pins usually take weeks to get traction. Judge it after 2-3 months, and judge it by
  **clicks** in Associates Reports, not money (commission is paid about 60 days after the month ends).
- **You are the quality check.** Amazon can close accounts for wrong claims. The script blocks prices, "deal" wording
  and fake "I tested it" wording automatically, but it cannot catch a factual mistake. Read before you tap Publish.
- **Links go to Amazon.in search results** for a product type (e.g. "foldable study table"), not to one product.
  That needs zero upkeep and shows no prices (Amazon's rules on prices are strict). The official product-data API
  needs **10 qualifying sales in the last 30 days**, so it's off the table until you get there.
- I tested the logic offline with a fake AI and fake Telegram. I could not test against the live Gemini, Claude,
  Telegram or GitHub servers, so **your first manual run (step 7) is the real test**.

## One-time setup (about 1 hour)

1. **Accounts:** GitHub (free), Telegram, a Pinterest *Business* account, and an AI key:
   Gemini (aistudio.google.com) or Claude (console.anthropic.com). Check each one's current free limits and pricing.
2. **Create a public GitHub repo** (e.g. `small-room-ideas`) and upload everything in this folder
   (Add file > Upload files). If `.github/workflows/autopilot.yml` is missing afterwards, use Add file > Create new
   file, type that path, and paste the contents.
3. **Turn on the website:** repo Settings > Pages > Source: *Deploy from a branch* > Branch `main`, folder `/docs` > Save.
   Your address is `https://YOURNAME.github.io/REPONAME`.
4. **Edit `config.json`** (pencil icon on GitHub): set `base_url` (no trailing slash), `amazon_tag` (your store ID,
   ends in `-21`), and `site_name` if you like.
5. **Telegram bot:** in Telegram open **@BotFather**, send `/newbot`, follow the steps, copy the token.
   Send any message to your new bot. Then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser;
   your chat id is the number after `"chat":{"id":`.
6. **Secrets:** repo Settings > Secrets and variables > Actions > New repository secret. Add:
   `LLM_PROVIDER` (`gemini` or `anthropic`), `LLM_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
   Optional: `LLM_MODEL` if the default model name is retired (see the AI provider's model list).
7. **First run:** Actions tab > *autopilot* > Run workflow. Within a minute you should get a draft on Telegram.
   Tap Publish, wait 1-2 minutes, open your site. If the run fails, open the run log and send it to me.
8. **Amazon:** in your Associates account, add the site address to your list of sites/channels. Click one shop button
   and confirm the address contains `tag=` and your ID. Next day, check that the click shows in Reports.
9. **Pinterest:** Business account > claim your website (Pinterest gives you a meta-tag code; paste only the
   `content` value into `pinterest_verify_code` in `config.json`, commit, and wait for the next run).
   Then, on desktop, Settings > Bulk create Pins > Auto-publish > paste `https://YOURNAME.github.io/REPONAME/feed.xml`
   and pick a board. New pins show up within about 24 hours. If Pinterest won't claim a github.io address,
   buy a cheap custom domain and point GitHub Pages at it.

## Daily life

A Telegram message arrives after 8 am IST. Read it. Tap **Publish**, **Redo** (rewrites it, max 2 times) or **Skip**.
Ignore it for 48 hours and it quietly expires. Nothing is ever published without your tap.

## Settings (`config.json`)

`posts_per_day`, `start_hour`, `max_drafts_per_day`, `niche`, `ai_disclosure` (the "drafted with AI assistance"
line in the footer). Topics come from `topics.txt`, then the AI suggests more when it runs out.

## Rules this setup follows (keep it that way)

- Disclosure on every page: "As an Amazon Associate I earn from qualifying purchases."
- No prices, discounts or deal wording. Don't add them by hand.
- Don't buy through your own links, and don't offer cashback or rewards for using them.
- Keep your Associates account's list of sites up to date.
- Read Amazon's Operating Agreement yourself; the rules can change.

## Files

`autopilot.py` main loop · `llm.py` AI + safety checks · `sitegen.py` website · `cover.py` pin images ·
`telegram_io.py` Telegram · `tests/test_flow.py` offline test (`python tests/test_flow.py`) ·
`python autopilot.py --demo` builds a sample site locally with a fake AI.
