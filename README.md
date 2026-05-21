Marketplace Monitoring & Automated Alert System



A Python + Playwright browser automation platform that continuously monitors Facebook Marketplace for target vehicle listings and delivers real-time Discord alerts — before other buyers see them.
Built to solve a real problem: Facebook killed native listing alerts years ago, and paid alternatives cost monthly subscriptions. This system replicates and exceeds that functionality for free.

What It Does

Monitors 16 search URLs across 6 vehicle categories within a 200-mile radius
Runs every 30 minutes via macOS crontab — fully unattended
Fires Discord rich-embed alerts with price, location, timestamp, and direct listing link
Sends a heartbeat ping every 90 minutes confirming the system is alive
Fires a crash alert if the script dies unexpectedly, instead of silently failing
Maintains a seen.json state file to prevent duplicate alerts across runs


Target Vehicles & Filtering Logic
Vehicles Monitored
VehicleYear RangeNotesToyota Tacoma2013–2015, 2018–2021Skips 2016–2017 (timing cover oil leak, transmission shudder)Toyota Tundra2014–2021Nissan Frontier2014–2019Avoids SMOD years (radiator/transmission failure)Toyota 4Runner2005–2021Lexus GX4602010–2019Land Cruiser Prado platformLexus GX4702003–2009Same platform, prior generation
Hard Filters Applied to Every Listing

4WD only, automatic transmission only
Price range: $5,000 – $20,000
Mileage: Rejects listings mentioning 220k+ miles in title
Bad price filter: Rejects scam listings ($1, $99, etc.)
SKIP_KEYWORDS: salvage, rebuilt, wrecked, parts, damaged, flood, 2wd, rwd, manual, 5 speed, 6 speed, stick shift, dealer, financing, and others
VALID_KEYWORDS: Must match a target vehicle — rejects unrelated listings that slip into search results


Architecture
Every 30 minutes (crontab on local machine)
        ↓
Python opens real Chromium browser via Playwright (headless)
        ↓
Loads saved Facebook session from fb_profile/
        ↓
If session expired → Discord warning fired → exits cleanly
        ↓
Checks 16 search URLs across 200mi radius
        ↓
Scrolls each page to trigger React lazy-load rendering
        ↓
Block isolation parser — each listing parsed independently (no index drift)
        ↓
Runs through SKIP_KEYWORDS, VALID_KEYWORDS, mileage, price filters
        ↓
New matching vehicle → Discord embed alert → phone buzzes
        ↓
Every 90 min → heartbeat ping confirming system healthy

Why Playwright Instead of requests
This was the core engineering problem.
Attempt 1 — GitHub Actions + requests.get()
Facebook Marketplace is a React single-page application. Plain HTTP requests return an empty shell — JavaScript never executes, no listings load. GitHub Actions was also running from datacenter IP ranges that Facebook's firewall blocks outright regardless of headers or user-agent spoofing.
Attempt 2 — Local machine + requests.get()
Residential IP solved the firewall problem, but the SPA rendering problem remained. Facebook still returned a blank page.
Solution — Playwright + persistent browser context
Playwright drives a real Chromium browser. Facebook sees a real human browser on a residential IP. The persistent browser context (fb_profile/) saves the authenticated session locally so manual login is only required once. All subsequent runs load the saved session automatically and run headless.
This is the same fingerprinting logic used by enterprise WAFs and bot-detection systems — understanding it from the attacker/automation side directly informs how defenders build detection rules.

Key Engineering Decisions
Block isolation parser — Each listing is parsed as an independent DOM block. Earlier versions used four separate findall() passes across the full page, which caused index misalignment when listings had missing fields. Block isolation eliminated this entirely.
Crash handler wrapping main() — Unattended scripts that fail silently are useless. Any unhandled exception fires a Discord alert with the error before exiting, so failures are visible immediately.
Absolute file paths via BASE_DIR — crontab runs with a different working directory than Terminal. Relative paths silently break. All file references use os.path.join(BASE_DIR, filename) constructed from __file__.
input() hang prevention — An earlier version blocked on input() when the session expired, freezing the script forever during unattended runs. Replaced with a Discord warning + clean exit.
Random delays (5–10s) between requests — Reduces request fingerprinting and mimics human browsing cadence.

Tech Stack
ToolPurposePython 3.14Core scripting languagePlaywrightReal browser automation (Chromium)Discord WebhooksReal-time alert deliverycrontab (macOS)30-minute schedulingseen.jsonPersistent duplicate-prevention statetruck_log.txtTimestamped execution logGitHubPrivate code repository

Operational Notes
Health Check Commands
bash# See recent activity
tail -50 ~/truck-alerts/truck_log.txt

# Confirm schedule is active
crontab -l

# Check if script is currently running
ps aux | grep monitor.py

# Check crontab error output
tail -5 /var/mail/$USER
Session Expiry Recovery
Discord sends an alert when the Facebook session expires. To recover:

Open monitor.py → set headless=False
Run python3 ~/truck-alerts/monitor.py in Terminal
Log into Facebook in the browser window that opens
Set headless=True
crontab resumes automatically on next cycle


Skills Demonstrated
This project maps directly to security and automation engineering workflows:
What Was BuiltSecurity/Engineering ParallelPivoted from requests to Playwright after fingerprint detectionUnderstanding WAF evasion, bot-detection logic, and browser fingerprintingSession stored locally, never uploaded to remoteSession management and credential hygieneSKIP_KEYWORDS / VALID_KEYWORDS filteringInput validation and sanitization — same logic used in SIEM detection rules to reduce noiseSwitched from GitHub Actions to local cronInfrastructure constraint analysis — knowing when cloud environments are non-viableCrash handler + Discord alertingOperational monitoring and alerting pipeline designBlock isolation parserStructured data parsing and handling malformed/inconsistent inputs

Lessons Learned

Facebook actively blocks all datacenter scraping — GitHub Actions, hosted services, and VPNs all fail because IP reputation is checked before any content is served
Real browser automation is the only reliable free solution for SPAs — requests.get() is dead against React apps
crontab requires exact Python paths and Full Disk Access — silent failures are almost always a permissions or path issue
Never block on user input in unattended scripts — input() hangs forever in cron context
Three LLMs reviewing the same code independently caught real bugs — index misalignment, missing keyword filters, and the input() hang were all caught in review, not production


Built and documented by Hunter Hanners — active duty U.S. Army, pursuing offensive security roles
