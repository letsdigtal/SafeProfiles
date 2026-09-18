"""Post to YOUR OWN Facebook Page via the official Graph API (recommended).

No browser automation, no detection risk. You need a Page access token:
  1. https://developers.facebook.com -> create app -> add "Facebook Login"
     ... simplest: use the Graph API Explorer to mint a User token with
     pages_manage_posts + pages_read_engagement, then exchange for a
     Page token (accounts endpoint). Meta has a step-by-step in docs.
  2. Never share the token; pass it via --token or FB_PAGE_TOKEN env var.

Usage:
  python automation/facebook_api_post.py --page-id 123456 --message "Hello fans!" --token EAA...
  python automation/facebook_api_post.py --page-id 123456 --message "New video!" --link https://youtu.be/xxx
"""
import argparse
import json
import os
import urllib.parse
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-id", required=True)
    ap.add_argument("--message", required=True)
    ap.add_argument("--link", default=None)
    ap.add_argument("--token", default=os.environ.get("FB_PAGE_TOKEN", ""))
    args = ap.parse_args()
    if not args.token:
        raise SystemExit("Provide --token or set FB_PAGE_TOKEN env var.")

    data = {"message": args.message, "access_token": args.token}
    if args.link:
        data["link"] = args.link
    req = urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{args.page_id}/feed",
        data=urllib.parse.urlencode(data).encode(),
        headers={"User-Agent": "SafeProfiles/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("Posted OK:", r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Graph API error {e.code}: {e.read().decode()[:500]}")


if __name__ == "__main__":
    main()
