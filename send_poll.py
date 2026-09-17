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

    title = tmw.strftime("%d-%m-%Y") + " Tomorrow Shuttle"

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
