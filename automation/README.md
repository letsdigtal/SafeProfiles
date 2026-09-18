# 🤖 SafeProfiles Automation (optional)

The main app needs **nothing** from this folder. These scripts are extras for
uploading/posting to accounts you own.

## Golden rules

1. **Official APIs first** — `youtube_api_upload.py` and `facebook_api_post.py`
   are Google/Meta-approved. No detection risk, no bans for "automation".
2. **Browser scripts are fallbacks** — only for what APIs can't do.
3. **Human clicks Publish** — browser scripts draft everything and pause so
   YOU click the final button (override with `--auto-confirm` at your own risk).
4. **Small volume** — a few actions/day, random delays, normal hours.
   Mass posting / spam / fake engagement will get accounts banned with ANY tool.
5. **One profile per account** — create it in the dashboard, launch once, log in
   normally, close the browser, then run the script with `--profile`.

## Setup

```bash
pip install -r automation/requirements.txt
playwright install chromium   # or pass --browser-path to your Chrome
```

Run from the repo root, e.g.:

```bash
python automation/youtube_api_upload.py --file short.mp4 --title "Hi #shorts"
python automation/facebook_api_post.py --page-id 123 --message "Hello!" --token EAA...
python automation/youtube_studio_upload.py --profile "Channel 1 - Desktop" --file short.mp4 --title "Hi #shorts"
python automation/facebook_page_post.py --profile "Page 1 - Mobile" --page https://www.facebook.com/YourPage --message "Hi"
```

Each script prints its own setup steps when something is missing.
