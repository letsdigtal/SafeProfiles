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
| **GitHub tunnels** | Optional: your own throwaway GitHub accounts become free SOCKS5 proxies (one account per profile). Token stored **encrypted**, **never uploaded**; tunnel is password-protected |
| **Anti-leak flags** | WebRTC IP-leak blocked, `AutomationControlled` blink feature disabled, no automation banners |
| **Automation** | Official-API uploaders/posters (YouTube Data API, FB Graph API) + careful browser fallbacks where the human clicks Publish. See `automation/` |
| **Safety design** | No telemetry, no auto-update, no remote config; local API token-locked; **never** `--remote-allow-origins=*`; GitHub-token feature (optional) keeps your PAT encrypted and local |

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

### 🆓 GitHub tunnel proxies (optional — your own accounts, by popular request)

The closed-source app this replaces had a "free proxy with GitHub token" trick.
SafeProfiles includes a **safe, fully readable version** of it.

**One throwaway GitHub account = one free SOCKS5 proxy = one browser profile.**

1. Create a **separate** GitHub account for the profile (verify its email —
   Actions requires it). Do NOT use your main account.
2. On that account: *Settings → Developer settings → Personal access tokens →
   Tokens (classic) → Generate new token* → tick **repo** + **workflow**.
3. SafeProfiles → Proxies tab → *GitHub tunnel proxies* → type a label, paste
   the token → **Add account & start tunnel** (needs internet, ~30 seconds).
4. The app creates a repo `safeprofiles-tunnel` in that account containing two
   plain-text files (`.github/workflows/tunnel.yml` + `run_tunnel.sh`) — you can
   read every line on GitHub. The workflow runs `microsocks` (a tiny open-source
   SOCKS5 server) on GitHub's runner and exposes it through a **pinggy.io** TCP
   tunnel. The public address is committed to `endpoint.json`; press
   **Refresh** (≈1–2 min) then **Test**.
5. Edit profile → Proxy → **GitHub tunnel** → pick the account → Launch. 🎉

   **Tip — pre-fill the token:** put it in a `token.txt` file next to
   `SafeProfiles.exe`. The dashboard loads it automatically and the file
   deletes itself once the account is added. (Never bake tokens into the
   exe or repo — this repo is public!)

Safer than the original app's version:

- your token is stored **encrypted** locally and is **never uploaded anywhere**
  (the runner only receives GitHub's own short-lived token),
- the SOCKS proxy **requires a random username/password** (theirs was an open
  proxy anyone could find and abuse),
- nothing is base64-obfuscated — every pushed file is readable.

⚠️ **Honest warnings:** running proxies on GitHub Actions **violates GitHub's
Terms of Service** — accounts can get **banned**, so use throwaway accounts you
can afford to lose. Traffic passes through pinggy.io (third party). GitHub
datacenter IPs are *not* residential — expect occasional "unusual login
location" emails from Facebook/Google. Each runner lives ≤ ~5.5 h and a cron
re-starts it automatically (brief gaps possible); if a tunnel dies, press
**Start** again. For valuable accounts, a direct connection or a real proxy is
still the better choice.

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
| "Cannot reach SafeProfiles" screen | Means the app is closed - start SafeProfiles.exe. Stale tabs reconnect automatically since v1.2.3 (the dashboard fetches the live key from the app and repairs itself, no reload needed) |
| Port busy | The app auto-picks ports 17500–17519; close other copies of the app |
| Fingerprint extension missing in launched window | Newer branded Chrome may ignore `--load-extension`. In the launched window: `chrome://extensions` → Developer mode ON → *Load unpacked* → `…\SafeProfiles\browsers\<profile>\fingerprint_ext` (once; it sticks to that profile). Or use unbranded Chromium |
| Proxy auth popup appears | Fixed in v1.2: proxy passwords are applied by a local relay inside the app (works even on Chrome 137+). If it still fails, re-test the proxy in the Proxies tab |
| Free proxies all fail | Normal — public lists decay hourly. Fetch fresh + test again, or browse direct |
| Tunnel stuck on "starting" | Open that account's repo → Actions tab on github.com and read the run's error; verify the account's email (Actions needs it); press Start again |
| "Token scopes missing" | Create a CLASSIC token and tick both **repo** and **workflow** scopes |
| Tunnel worked, then died | Runners end after ~5.5 h (cron auto-restarts, small gaps). Press Start, then Refresh |
| Browser window loses network after ~1h | Fixed in v1.2.5: the tunnel address rotates hourly and the app now follows it automatically - keep the SafeProfiles app open while browsing. If an old window still has no network: close it, press Refresh on the account, launch the profile again |
| Launch works but pages say "no network" | Since v1.2.6 launch REFUSES dead tunnels with a clear message. Usual cause: the tunnel's GitHub account was banned (they live hours-days) - Proxies tab shows it as "dead": Remove it, add a new GitHub account, then Edit profile -> pick the new tunnel. Your channel/logins are not affected |

## 📁 Project layout

```
app/            server, profiles, browser launcher, proxy tools, free-pool, secrets
extension/      fingerprint-consistency extension (full source, per-profile seed)
static/         offline dashboard (no CDNs, no external requests)
automation/     official-API + careful browser scripts for YouTube/Facebook
.github/        workflow that builds YOUR SafeProfiles.exe automatically
```

MIT licensed. Use responsibly and respect each platform's Terms of Service.
