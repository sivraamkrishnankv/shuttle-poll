# Shuttle Poll Automation — Build Doc

**Stack:** Green API (free Developer plan) + cron-job.org (free scheduler) + GitHub Actions (free runner)
**Cost:** ₹0 / month
**Goal:** Every evening at 6:00 PM IST, auto-post a WhatsApp poll to the shuttle group asking who's coming. Single-choice Yes/No, posted every day of the week.

---

## 1. How it works

```
cron-job.org (18:00 Asia/Kolkata, daily)
        │  POST workflow_dispatch  (GitHub fine-grained token)
        ▼
GitHub Actions  ──►  send_poll.py  ──►  Green API sendPoll  ──►  WhatsApp group
 (runs the job)                                                    (native poll,
                                                                    single choice)
```

Nothing is hosted. cron-job.org fires on the minute and tells GitHub to run the workflow. GitHub runs a ~1 second script and shuts down. Green API holds the WhatsApp session on their side.

### Why not GitHub's own cron?

GitHub's `schedule:` trigger is best-effort. In this repo it fired 4–8 hours late. Moving the cron minute doesn't help, because the scheduler itself is the unreliable part. So the `schedule:` trigger was **removed** from `poll.yml` and an external scheduler calls the `workflow_dispatch` API instead.

Do **not** add `schedule:` back "as a backup". A late GitHub run on top of the on-time cron-job.org run would post a duplicate poll to the group.

Because there is no `schedule:` trigger, GitHub's 60-day inactivity auto-disable no longer applies, so the old keepalive job was removed as well.

### Schedule

Daily, **18:00 IST**, including Saturday (the Saturday poll asks about Sunday). `send_poll.py` has no day-of-week check. If the poll should skip a day, change the schedule in cron-job.org, not the code.

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

- `multipleAnswers: False` is what enforces one option per person.
- `message` is the poll question. Max 255 characters.
- `options` takes 2–12 entries, each as `{"optionName": "..."}`. They must differ from each other by at least one character.
- No external libraries — `urllib` is in the Python standard library, so the workflow needs no `pip install`.
- `tmw` and the "Sunday" comment are leftovers from the old Sunday-skip check, which was removed on purpose. They do nothing.

---

## 4. `.github/workflows/poll.yml`

```yaml
name: shuttle-poll

on:
  # Triggered on time by cron-job.org (18:00 Asia/Kolkata, daily) via the
  # workflow_dispatch API. GitHub's own `schedule:` was removed because it
  # fires hours late; keeping it too would risk a duplicate poll.
  workflow_dispatch:

jobs:
  send:
    runs-on: ubuntu-latest
    permissions:
      contents: read
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

- `workflow_dispatch` is the only trigger. It also gives you a **Run workflow** button in the Actions tab. **Careful: that button posts a real poll to whatever group `WA_GROUP_ID` points at.**
- `permissions: contents: read` is declared explicitly so the job's token access can't silently widen if the repo setting changes.

---

## 5. Getting the group ID

Green API group IDs look like `120363xxxxxxxxxxxx@g.us` — not a phone number. Run this in **your own** PowerShell window (so the token never leaves your machine):

```powershell
$api = "https://XXXX.api.greenapi.com"   # your apiUrl
$iid = "YOUR_ID_INSTANCE"
$tok = "YOUR_API_TOKEN_INSTANCE"
Invoke-RestMethod "$api/waInstance$iid/getContacts/$tok`?group=true" |
  Select-Object name, id | Format-Table -AutoSize
```

`getContacts?group=true` returns only groups. `getChats` also works but can miss a brand-new group with no messages. The bot number must be a member of the group. To double-check a candidate, call `getGroupData` (POST, body `{"groupId":"<id>"}`) and confirm the `subject` and `size`.

---

## 6. Manual steps — the things only you can do

> The script and workflow are just files; these steps are what make them actually work.

### A. WhatsApp side

1. **Decide which number the bot runs on.** A spare/secondary number is strongly recommended. Green API connects the way WhatsApp Web does, which is not Meta's officially sanctioned path — one poll a day to one group is low-risk, but keep that risk off your main account. *(The current instance is linked to a personal number; consider moving to a spare.)*
2. **Add that number to the shuttle group.** It must be a member to post. It does *not* need to be admin.
3. Keep the bot's phone online occasionally — a linked session drops if the phone stays offline for ~14 days.

### B. Green API setup

1. Sign up at **console.green-api.com** and create **one instance** on the free **Developer** plan.
2. From the instance page, note down `apiUrl`, `idInstance`, `apiTokenInstance`.
3. **Link the number**: Link with QR code (WhatsApp → Settings → Linked Devices → Link a Device). Wait until the status shows **Authorized**.
4. Get the group's `id` (section 5).

### C. GitHub setup

1. Public repo `shuttle-poll` (public repos get unlimited free Actions minutes). Tokens live in Secrets, not in the code.
2. Add the files from sections 3 and 4.
3. **Settings → Secrets and variables → Actions**, add all four:

   | Secret name          | Value                   |
   | -------------------- | ----------------------- |
   | `GREEN_API_URL`      | your `apiUrl`           |
   | `GREEN_API_INSTANCE` | your `idInstance`       |
   | `GREEN_API_TOKEN`    | your `apiTokenInstance` |
   | `WA_GROUP_ID`        | the `...@g.us` group ID |

4. **Create a fine-grained personal access token** for cron-job.org: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens.
   - Resource owner: your account
   - Repository access: **Only select repositories** → `shuttle-poll`
   - Permissions → Repository → **Actions: Read and write** (Metadata: Read-only is added automatically). Nothing else.
   - Expiration: the longest allowed (max 1 year). **Set a calendar reminder to rotate it before it expires.**
   - Do not use a classic token — its scopes cover all your repos.

### D. cron-job.org setup

Create a job at cron-job.org (free):

| Field | Value |
| --- | --- |
| URL | `https://api.github.com/repos/sivraamkrishnankv/shuttle-poll/actions/workflows/poll.yml/dispatches` (must be `https`) |
| Schedule | Every day at 18:00, timezone **Asia/Kolkata** (or, if left on UTC, 12:30) |
| Method | POST |
| Header | `Authorization: Bearer <fine-grained token>` |
| Header | `Accept: application/vnd.github+json` |
| Header | `X-GitHub-Api-Version: 2022-11-28` |
| Header | `User-Agent: cron-job.org` |
| Body | `{"ref":"main"}` |
| Save responses in job history | On |
| Notifications | On failure |

Check that the first "Next executions" entry reads 6:00 PM IST (12:30 UTC). A successful dispatch returns **HTTP 204** — visible in the job history.

**Never press "Test run" on the live job** — it posts a real poll to whatever group `WA_GROUP_ID` currently points at.

### E. Testing without touching the live group

1. Create a throwaway WhatsApp group with the bot number in it and get its ID (section 5).
2. Temporarily set `WA_GROUP_ID` to the dummy group's ID.
3. Trigger via the Actions tab or cron-job.org and confirm the poll lands there and only one option can be picked.
4. **Set `WA_GROUP_ID` back to the live group's ID.** If the dummy ID stays in the secret, the real poll goes to the wrong group.

### F. Ongoing

1. **Rotate the fine-grained GitHub token before it expires** (max 1 year). When it expires, cron-job.org starts getting 401s and the poll silently stops (failure notifications should email you).
2. **Rotate `apiTokenInstance`** if it was ever exposed (pasted in chat, a screenshot, etc.) — the circular-arrow icon beside it in the Green API console — and update the `GREEN_API_TOKEN` secret.
3. Glance at the cron-job.org history and the Actions tab every so often.

---

## 7. Known limits and gotchas

| Thing                    | Detail |
| ------------------------ | ------ |
| **Free chat cap**        | Green API's Developer plan allows interaction with **3 chats total per month**. Live group + one test group = fine. More groups will hit the cap. |
| **Timing**               | cron-job.org fires on the minute. The workflow then needs a few seconds to start on GitHub. A `workflow_dispatch` can still queue briefly, but not for hours like `schedule:` did. |
| **GitHub token expiry**  | The fine-grained token expires within a year. Expired = silent 401s. Rotate it on a calendar reminder. |
| **Token blast radius**   | The GitHub token is scoped to this repo's Actions only. The Green API token is **not** scopable — it controls the whole instance. It lives only in GitHub Secrets. |
| **Session expiry**       | If the bot phone has no WhatsApp activity for ~14 days, the instance goes `notAuthorized` and every poll fails until you re-link. Check `getStateInstance` if polls stop. |
| **Unofficial protocol**  | Green API is not Meta's official Business API (which can't post polls to groups). Use a spare number. |
| **Message length**       | Poll question capped at 255 chars, options at 100 chars each, 2–12 options. |
| **Single point of failure** | cron-job.org is now the scheduler. If its job is disabled or deleted, nothing fires. |

---

## 8. Nice-to-haves (later, if you want them)

- **Holiday skip list** — a small `skip_dates.txt` in the repo; the script checks tomorrow's date against it and bails.
- **Weather-aware skip** — a free weather API check could skip the poll on heavy-rain forecasts.
- **Vote summary** — needs a webhook listener (a server), so reading votes in WhatsApp is simpler.
- **Failure alerts** — cron-job.org emails on a failed dispatch, but a failure *inside* the workflow (e.g. `notAuthorized`) is only visible in the Actions tab; add an alert step if that matters.

---

## 9. Quick test checklist

- [ ] Instance shows `authorized` in the Green API console
- [ ] `getContacts?group=true` returns the shuttle group with a `...@g.us` id
- [ ] All four secrets exist, and `WA_GROUP_ID` is the **live** group (not the test group)
- [ ] `poll.yml` has no `schedule:` trigger
- [ ] cron-job.org job: https URL, POST, 3–4 headers, body `{"ref":"main"}`, 18:00 Asia/Kolkata, enabled
- [ ] cron-job.org history shows HTTP 204 after a run
- [ ] Poll title reads **🏸 Playing tomorrow?** and only one option can be selected
- [ ] Workflow run log shows `sent:` and exits green
- [ ] Calendar reminder set to rotate the GitHub token before it expires
