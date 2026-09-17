# Shuttle Poll Automation — Build Doc

**Stack:** Green API (free Developer plan) + GitHub Actions (free scheduler)
**Cost:** ₹0 / month
**Goal:** Every evening, auto-post a WhatsApp poll to the shuttle group asking who's coming for tomorrow morning's session. Single-choice Yes/No. Skips the evening before Sunday, since there's no Sunday play.

---

## 1. How it works

```
GitHub Actions cron (8 PM IST, Sun–Fri)
        │
        ▼
  send_poll.py  ──►  Green API sendPoll  ──►  WhatsApp group
   (computes                                  (native poll,
    tomorrow's date)                           single choice)
```

Nothing is hosted. GitHub wakes up once a day, runs a ~1 second script, and shuts down. Green API holds the WhatsApp session on their side.

### Why the schedule is Sun–Fri

The poll asks about **tomorrow**, so it runs the evening *before* a play day.


| Poll posted (evening) | Asks about | Play day? | Run? |
| --------------------- | ---------- | --------- | ---- |
| Sunday                | Monday     | Yes       | ✅    |
| Monday                | Tuesday    | Yes       | ✅    |
| Tuesday               | Wednesday  | Yes       | ✅    |
| Wednesday             | Thursday   | Yes       | ✅    |
| Thursday              | Friday     | Yes       | ✅    |
| Friday                | Saturday   | Yes       | ✅    |
| **Saturday**          | **Sunday** | **No**    | ❌    |


So: cron days `0-5` (Sunday through Friday). Saturday evening is the one that's skipped.

---

## 2. Repo structure

```
shuttle-poll/
├── send_poll.py
├── shuttle-poll-build-doc.md
└── .github/
    └── workflows/
        └── poll.yml
```

That's the whole project. Two code files plus this doc.

Live repo: https://github.com/sivraamkrishnankv/shuttle-poll

---

## 3. `send_poll.py`

```python
import os
import sys
import json
import urllib.request
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

url = os.environ["GREEN_API_URL"].rstrip("/")
iid = os.environ["GREEN_API_INSTANCE"]
tok = os.environ["GREEN_API_TOKEN"]
gid = os.environ["WA_GROUP_ID"]


def main():
    tmw = datetime.now(IST) + timedelta(days=1)

    # safety net: if the run fires late/wrong and tomorrow is a Sunday, bail out
    if tmw.weekday() == 6:
        print("tomorrow is sunday, no shuttle, skipping")
        return

    title = "🏸 Playing tomorrow?"

    body = {
        "chatId": gid,
        "message": title,
        "options": [{"optionName": "Yes"}, {"optionName": "No"}],
        "multipleAnswers": False,
    }

    ep = f"{url}/waInstance{iid}/sendPoll/{tok}"
    req = urllib.request.Request(
        ep,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = r.read().decode()
            print("sent:", title, "|", out)
    except urllib.error.HTTPError as e:
        print("failed:", e.code, e.read().decode(), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Notes on the payload**

- `multipleAnswers: False` is what enforces one option per person — this is exactly the flag you asked about.
- `message` is the poll question. Max 255 characters, so your title is well inside.
- `options` takes 2–12 entries, each as `{"optionName": "..."}`. They must differ from each other by at least one character, so `Yes` / `No` is fine.
- No external libraries — `urllib` is in the Python standard library, so the workflow needs zero `pip install` steps and runs in a couple of seconds.

**Poll title:** `🏸 Playing tomorrow?` — short, no date, reads naturally with Yes/No. `tmw` is still computed for the Sunday safety check.

---

## 4. `.github/workflows/poll.yml`

```yaml
name: shuttle-poll

on:
  schedule:
    # 14:30 UTC = 8:00 PM IST (no DST in India), Sunday through Friday
    - cron: '30 14 * * 0-5'
  workflow_dispatch:

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Send poll
        env:
          GREEN_API_URL: ${{ secrets.GREEN_API_URL }}
          GREEN_API_INSTANCE: ${{ secrets.GREEN_API_INSTANCE }}
          GREEN_API_TOKEN: ${{ secrets.GREEN_API_TOKEN }}
          WA_GROUP_ID: ${{ secrets.WA_GROUP_ID }}
        run: python send_poll.py
```

- `cron: '30 14 * * 0-5'` = 14:30 UTC = 8:00 PM IST, Sunday through Friday. GitHub cron always runs in UTC, so to change the time subtract 5:30 from the IST time you want. India has no daylight saving, so this stays correct year-round.
- `workflow_dispatch` gives you a **Run workflow** button in the Actions tab — that's how you test it without waiting for 8 PM.

---

## 5. Getting the group ID

Green API group IDs look like `120363043968854xxx@g.us` — not a phone number. Easiest way to find yours: after your instance is authorized, open this URL in a browser (substitute your own values):

```
https://<apiUrl>/waInstance<idInstance>/getChats/<apiTokenInstance>
```

You'll get a JSON list. Find the entry with `"type": "group"` and a `"name"` matching your shuttle group, and copy its `id` value.

---

## 6. Manual steps — the things only you can do

> Everything below needs your hands. The script and workflow above are just files; these steps are what make them actually work.

### A. WhatsApp side

1. **Decide which number the bot runs on.** Strongly recommend a spare/secondary number, not your primary. Green API connects the same way WhatsApp Web does, which is not Meta's officially sanctioned path — one poll a day to one group is low-risk, but keep that risk off your main account.
2. **Add that number to the shuttle group.** It must be a member to post. It does *not* need to be admin.
3. Keep the bot's phone online occasionally — a linked session drops if the phone stays offline for ~14 days.

### B. Green API setup

1. Sign up at **console.green-api.com** and create **one instance** on the free **Developer** plan.
2. From the instance page, note down three values — you'll paste them into GitHub in a moment:
  - `apiUrl` (looks like `https://7105.api.greenapi.com`)
  - `idInstance`
  - `apiTokenInstance`
3. **Scan the QR code** shown in the console, using the bot phone: WhatsApp → Settings → Linked Devices → Link a Device. Wait until the instance state shows `authorized`.
4. Hit the `getChats` URL from section 5 and **copy your group's `id`**.

### C. GitHub setup

1. Create a repo named `shuttle-poll`. **Make it public** — public repos get unlimited free Actions minutes; private ones get 2,000/month (still plenty, but public is the safer free path). Your tokens live in Secrets, not in the code, so public is safe here.
2. Add the two files from sections 3 and 4, at exactly those paths.
3. Go to **Settings → Secrets and variables → Actions → New repository secret** and add all four:

  | Secret name          | Value                   |
  | -------------------- | ----------------------- |
  | `GREEN_API_URL`      | your `apiUrl`           |
  | `GREEN_API_INSTANCE` | your `idInstance`       |
  | `GREEN_API_TOKEN`    | your `apiTokenInstance` |
  | `WA_GROUP_ID`        | the `...@g.us` group ID |

4. Go to the **Actions** tab, select `shuttle-poll`, click **Run workflow**. Check the group — the poll should land within a few seconds.
5. Vote on it yourself and confirm you can only pick one option. That verifies `multipleAnswers` is behaving.

### D. Ongoing (roughly once every 6 weeks)

1. **Touch the repo.** GitHub silently disables scheduled workflows after 60 days with no repository activity. Any commit resets the clock — edit the README, change a comment, anything. Put a recurring reminder in your calendar; this is the single most likely way this setup quietly dies.

---

## 7. Known limits and gotchas


| Thing                   | Detail                                                                                                                                                            |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Free chat cap**       | Green API's Developer plan allows interaction with **3 chats total per month**. One group = fine. If you later add more groups, you'll hit this.                  |
| **Best-effort timing**  | GitHub's cron is not guaranteed to the minute — it can lag, especially on the hour. Off-hour minutes like `:07` or `:23` tend to fire more punctually than `:00`. |
| **60-day auto-disable** | See step 13. The most common failure mode for this kind of setup.                                                                                                 |
| **Session expiry**      | If the bot phone has no WhatsApp activity for ~14 days, the linked session drops and you'll re-scan the QR.                                                       |
| **Unofficial protocol** | Green API is not Meta's official Business API (which still can't post polls to groups at all). Use a spare number.                                                |
| **Message length**      | Poll question capped at 255 chars, options at 100 chars each, 2–12 options.                                                                                       |


---

## 8. Nice-to-haves (later, if you want them)

- **Holiday skip list** — a small `skip_dates.txt` in the repo; the script checks tomorrow's date against it and bails. Useful for festivals or court-closed weeks.
- **Weather-aware skip** — if the group plays outdoors, a free weather API check could skip the poll on heavy-rain forecasts.
- **Vote summary** — Green API can receive poll-vote webhooks, but that needs a listener endpoint, which means a server — at which point you're back to the hosted-bot option. Reading votes directly in WhatsApp is simpler.
- **Failure alerts** — add a step that pings you on failure, so a silently broken run doesn't go unnoticed for a week.

---

## 9. Quick test checklist

- [ ] Instance shows `authorized` in the Green API console
- [ ] `getChats` returns the shuttle group with a `...@g.us` id
- [ ] All four secrets exist in the repo
- [ ] Manual **Run workflow** posts a poll to the group
- [ ] Poll title reads **🏸 Playing tomorrow?**
- [ ] Only one option can be selected per person
- [ ] Workflow run log shows `sent:` and exits green
- [ ] Calendar reminder set to touch the repo every ~6 weeks