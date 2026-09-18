# 🛡️ SafeProfiles — free, open, offline multi-profile browser manager

One isolated Chrome profile per YouTube channel / Facebook page / account, with
per-profile proxy, consistent fingerprint, and human-paced automation helpers.

**No paid proxy needed. No accounts. No telemetry. Works offline.**

---

## ⬇️ Download & run (Windows, easiest)

1. Install **Google Chrome** (any recent version).
2. Go to this repo's **Releases** page → download **`SafeProfiles.exe`**.
   - No Release yet? Push this code to your GitHub (below) — the exe builds
     itself automatically, then appears under Releases / Actions artifacts.
3. **Double-click `SafeProfiles.exe`.** A small status window appears and your
   browser opens the dashboard automatically. That's it — no install.
4. Press **Launch** on a profile, log in once. Sessions stay separated forever.

> 📴 **Offline:** the app opens and runs without internet. Internet is only
> needed for actual browsing / proxy testing, like any browser.

## ▶️ Run from source (any OS)

```bash
pip install -r requirements.txt
python run.py
```
(Windows: double-click `start.bat`. Linux/Mac: `bash start.sh`.)

## ☁️ Put this on YOUR GitHub (3 minutes)

```bash
cd safe-profiles-browser
git init
git add .
git commit -m "SafeProfiles v1.0 - my own safe multi-profile browser"
# create an EMPTY repo on github.com (web UI, no README), then:
git branch -M main
git remote add origin https://github.com/<YOUR-USERNAME>/<REPO-NAME>.git
git push -u origin main
# build your exe: Actions tab -> the run finishes -> download SafeProfiles.exe
# or create a Release:  git tag v1.0.0 && git push --tags
```

---

## ✨ Features

| Area | What you get |
|---|---|
| **Profiles** | Unlimited isolated Chrome/Edge/Brave profiles (separate cookies, logins, cache). Color + notes per profile |
| **Fingerprint** | Per-profile preset (Win/Mac desktop, iPhone, Android): user-agent, viewport, screen, GPU, cores, locale, timezone + seeded canvas/audio noise. Full source in `extension/` |
| **Custom proxies** | Paste any format (`ip:port`, `ip:port:user:pass`, `user:pass@ip:port`, `socks5://…`), live-tested with country/city/ping/timezone. Passwords encrypted on disk |
| **Free proxy pool** | Fetch public lists → auto-test → keep working ones → assign to any profile. **$0 forever** |
| **Anti-leak flags** | WebRTC IP-leak blocked, `AutomationControlled` blink feature disabled, no automation banners |
| **Automation** | Official-API uploaders/posters (YouTube Data API, FB Graph API) + careful browser fallbacks where the human clicks Publish. See `automation/` |
| **Safety design** | No telemetry, no auto-update, no remote config, no GitHub token needed, local API token-locked, **never** `--remote-allow-origins=*` |

## 🔌 Proxies without money — how to do it right

1. **For real logins (your main channels/pages): use NO proxy.** Your home IP
   with a consistent fingerprint is the safest, most "human" setup.
2. **For extra profiles:** Proxies tab → *Fetch lists* → *Test & save* → assign
   a working free proxy to the profile. Re-test weekly (free proxies die fast).
3. **Never type real passwords through a free proxy you don't trust** — the app
   warns you, because free-proxy owners *can* see unencrypted traffic. (Google/
   Facebook logins are HTTPS-encrypted, but session hijacking on hostile
   proxies is still a real risk. When in doubt: direct connection.)
4. Later, any cheap VPS + SSH (`ssh -D 1080 user@vps`) gives you your own
   private SOCKS5 at `127.0.0.1:1080` — paste it as a custom proxy.

### Why is there no "login with GitHub token for free residential proxies"?

Because that trick (used by the closed-source app this replaces) spends **your**
GitHub account: it runs proxy servers on GitHub Actions with **your** token and
tunnels traffic through a free third-party relay. That gets GitHub accounts
flagged/banned, leaks your token in plaintext, and lets strangers observe your
traffic. SafeProfiles will never do that — the free pool above costs nothing
and risks nothing.

## 🕵️ Will Facebook/YouTube detect it?

Honest answer: **no tool is undetectable**, including $100/month ones. What
actually keeps accounts safe — and what this app gives you:

- one stable profile + one stable IP per account (no fingerprint/IP hopping),
- timezone/locale matching the proxy country,
- human pacing and real watch/scroll history before heavy actions,
- official APIs for uploads/posts wherever possible.

What gets accounts banned with ANY tool: fresh accounts + instant mass actions,
spam, fake engagement, CAPTCHA-solving services, 50 accounts on one IP. Don't.

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| "No Chrome found" | Install Google Chrome (or Edge/Brave), restart the app |
| Dashboard didn't auto-open | Copy the `http://127.0.0.1:…?token=…` URL from the status window into your browser |
| Port busy | The app auto-picks ports 17500–17519; close other copies of the app |
| Fingerprint extension missing in launched window | Newer branded Chrome may ignore `--load-extension`. In the launched window: `chrome://extensions` → Developer mode ON → *Load unpacked* → `…\SafeProfiles\browsers\<profile>\fingerprint_ext` (once; it sticks to that profile). Or use unbranded Chromium |
| Proxy auth popup appears | The per-profile auth extension should handle it; if it pops up, re-save the proxy password in Edit profile |
| Free proxies all fail | Normal — public lists decay hourly. Fetch fresh + test again, or browse direct |

## 📁 Project layout

```
app/            server, profiles, browser launcher, proxy tools, free-pool, secrets
extension/      fingerprint-consistency extension (full source, per-profile seed)
static/         offline dashboard (no CDNs, no external requests)
automation/     official-API + careful browser scripts for YouTube/Facebook
.github/        workflow that builds YOUR SafeProfiles.exe automatically
```

MIT licensed. Use responsibly and respect each platform's Terms of Service.
