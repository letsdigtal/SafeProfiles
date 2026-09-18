"""Draft a post on YOUR Page via the real browser session (last-resort fallback).

WARNING: Facebook detects browser automation aggressively and this can get
your account restricted. Prefer facebook_api_post.py (official API).
This script only TYPES the draft; YOU click Post yourself by default.

Usage:
  1. Launch the profile from the dashboard, log into Facebook, CLOSE the browser.
  2. python automation/facebook_page_post.py --profile "Page 1 - Mobile" --page "https://www.facebook.com/YourPage" --message "Hello!"
"""
import argparse

from common import get_profile, human_sleep, require_playwright, open_profile_context  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--page", required=True, help="Your Page URL")
    ap.add_argument("--message", required=True)
    ap.add_argument("--auto-confirm", action="store_true")
    ap.add_argument("--browser-path", default=None)
    args = ap.parse_args()

    sync_playwright = require_playwright()
    profile = get_profile(args.profile)
    with sync_playwright() as pw:
        ctx = open_profile_context(pw, profile, browser_path=args.browser_path)
        page = ctx.new_page()
        page.goto(args.page, wait_until="domcontentloaded")
        human_sleep(3, 5)
        # Open composer
        try:
            page.get_by_text("What's on your mind?", exact=False).first.click(timeout=15000)
        except Exception:
            page.keyboard.press("c")  # fallback hotkey sometimes focuses composer
        human_sleep(1, 2)
        box = page.locator('[role="dialog"] [contenteditable="true"], [aria-label*="Create a post"] [contenteditable]').first
        box.click()
        human_sleep(0.5, 1)
        box.type(args.message, delay=50)
        human_sleep(1, 2)
        if args.auto_confirm:
            try:
                page.locator('[role="dialog"] [aria-label="Post"]').first.click(timeout=5000)
                print("Post clicked.")
            except Exception:
                print("Could not find the Post button - click it yourself.")
                input("Press Enter after posting…")
        else:
            print("DRAFT READY: review in the opened window and click Post yourself.")
            input("Press Enter here AFTER you posted…")
        ctx.close()


if __name__ == "__main__":
    main()
