"""Upload via YouTube Studio in YOUR profile's real browser session (fallback).

Prefer youtube_api_upload.py (official API). Use this only if the API quota
or category doesn't fit. By default the script fills everything and YOU click
the final Publish/Done button (human click = far lower risk).

Usage:
  1. Launch the profile from the dashboard, log into YouTube, CLOSE the browser.
  2. python automation/youtube_studio_upload.py --profile "Channel 1 - Desktop" --file short.mp4 --title "My short #shorts"
"""
import argparse

from common import get_profile, human_sleep, require_playwright, open_profile_context  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Profile id or name from the dashboard")
    ap.add_argument("--file", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--public", action="store_true", help="Set visibility Public (default Unlisted)")
    ap.add_argument("--auto-confirm", action="store_true", help="Click through Publish automatically (riskier)")
    ap.add_argument("--browser-path", default=None)
    args = ap.parse_args()

    sync_playwright = require_playwright()
    profile = get_profile(args.profile)
    with sync_playwright() as pw:
        ctx = open_profile_context(pw, profile, browser_path=args.browser_path)
        page = ctx.new_page()
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
        human_sleep(2, 4)
        # Create -> Upload videos
        page.get_by_label("Create").first.click()
        human_sleep(1, 2)
        page.get_by_text("Upload videos", exact=False).first.click()
        human_sleep(1, 2)
        page.set_input_files('input[type="file"]', args.file)
        print("File selected, waiting for details form…")
        page.wait_for_selector('ytcp-video-metadata-editor', timeout=120000)
        human_sleep(2, 4)
        # Title
        title_box = page.locator('ytcp-video-metadata-editor #title-textarea [contenteditable="true"], #title-textarea [contenteditable]').first
        title_box.click(); human_sleep(0.5, 1)
        title_box.press("ControlOrMeta+a"); title_box.press("Backspace")
        title_box.type(args.title, delay=40)
        human_sleep(1, 2)
        # Description
        if args.description:
            desc = page.locator('#description-textarea [contenteditable]').first
            desc.click(); human_sleep(0.5, 1)
            desc.type(args.description, delay=30)
            human_sleep(1, 2)
        # Kids question -> Not made for kids
        try:
            page.get_by_text("No, it's not made for kids", exact=False).first.click(timeout=5000)
        except Exception:
            pass
        # Next x3 (details -> checks -> visibility handled separately)
        for _ in range(2):
            page.get_by_text("Next", exact=True).last.click()
            human_sleep(2, 3)
        # Visibility
        page.get_by_text("Unlisted" if not args.public else "Public", exact=False).first.click()
        human_sleep(1, 2)
        if args.auto_confirm:
            page.get_by_text("Publish", exact=True).first.click()
            human_sleep(2, 3)
            print("Publish clicked. Verify in Studio.")
        else:
            print("READY: review everything in the opened window and click Publish yourself.")
            input("Press Enter here AFTER you published (browser stays open)…")
        ctx.close()


if __name__ == "__main__":
    main()
