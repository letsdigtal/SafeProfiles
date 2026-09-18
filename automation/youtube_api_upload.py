"""Upload a video to YOUR OWN YouTube channel via the official Data API v3.

This is the SAFE, Google-approved path: no browser automation, no detection
risk, no login-session handling. Quota cost ~1600 units per upload.

Setup (one time, free):
  1. https://console.cloud.google.com -> New project -> enable "YouTube Data API v3"
  2. OAuth consent screen (External) -> add yourself as test user
  3. Credentials -> Create OAuth client ID (Desktop app) -> download JSON
     and save it as automation/client_secrets.json
  4. First run opens a browser to authorize; token is saved as token.json

Usage:
  python automation/youtube_api_upload.py --file short.mp4 --title "My short #shorts" --privacy unlisted
"""
import argparse
import pickle
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--category", default="22")
    ap.add_argument("--privacy", default="unlisted", choices=["public", "unlisted", "private"])
    ap.add_argument("--made-for-kids", action="store_true")
    args = ap.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError
    except ImportError:
        raise SystemExit("Missing google libs. Run: pip install -r automation/requirements.txt")

    creds = None
    token_file = HERE / "token.json"
    if token_file.exists():
        import json as _json
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(_json.loads(token_file.read_text()), [
            "https://www.googleapis.com/auth/youtube.upload"])
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets = HERE / "client_secrets.json"
            if not secrets.exists():
                raise SystemExit("Put your OAuth client JSON at automation/client_secrets.json (see docstring).")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(secrets), ["https://www.googleapis.com/auth/youtube.upload"])
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": args.title, "description": args.description,
                    "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
                    "categoryId": args.category},
        "status": {"privacyStatus": args.privacy,
                   "selfDeclaredMadeForKids": args.made_for_kids},
    }
    media = MediaFileUpload(args.file, chunksize=1024 * 1024, resumable=True,
                            mimetype="video/*")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    print("Uploading", args.file)
    resp = None
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                print(f"  {int(status.progress() * 100)}%")
        except HttpError as e:
            raise SystemExit(f"Upload failed: {e}")
    print("DONE. videoId =", resp.get("id"), "-> https://youtu.be/" + resp.get("id", ""))


if __name__ == "__main__":
    main()
