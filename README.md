Marketplace Monitor — Automated Vehicle Alert System
A Python + Playwright browser automation platform that continuously monitors Facebook Marketplace for target vehicle listings and delivers real-time Discord alerts — before other buyers see them.
Built to solve a real problem: Facebook killed native listing alerts years ago, and paid alternatives cost monthly subscriptions. This system replicates and exceeds that functionality for free.

What It Does

Monitors 16 search URLs across 6 vehicle categories within a 200-mile radius
Runs every 30 minutes via macOS crontab — fully unattended
Fires Discord rich-embed alerts with price, location, mileage, timestamp, and direct listing link
Filters high-mileage listings using mileage extracted from title, description, and rendered HTML
Sends a heartbeat ping every 90 minutes confirming the system is alive
Fires a crash alert if the script dies unexpectedly, instead of silently failing
Maintains a seen.json state file to prevent duplicate alerts across runs


Target Vehicles & Filtering Logic
Vehicles Monitored
VehicleYear RangeNotesToyota Tacoma2013–2015, 2018–2021Skips 2016–2017 (timing cover oil leak, transmission shudder)Toyota Tundra2014–2021Nissan Frontier2014–2019Avoids SMOD years (radiator/transmission failure)Toyota 4Runner2005–2021Lexus GX4602010–2019Land Cruiser Prado platformLexus GX4702003–2009Same platform, prior generation
Hard Filters Applied to Every Listing

4WD only, automatic transmission only
Price range: $5,000 – $20,000
Mileage cap: 175,000 miles — checked in title, description, AND rendered HTML
Bad price filter: Rejects scam listings ($1, $99, $999, etc.)
SKIP_KEYWORDS: salvage, rebuilt, wrecked, parts, damaged, flood, 2wd, rwd, manual, 5 speed, 6 speed, stick shift, prerunner, access cab, single cab, dealer, financing, and others
VALID_KEYWORDS: Must match a target vehicle — rejects unrelated listings that slip into search results


Architecture
Every 30 minutes (crontab on local MacBook)
        ↓
Python opens real Chromium browser via Playwright (headless=True)
        ↓
Loads saved Facebook session from fb_profile/
        ↓
If session expired → Discord warning fired → exits cleanly (no hang)
        ↓
Checks 16 search URLs across 200mi radius of Gadsden, AL
        ↓
Scrolls each page to trigger React lazy-load rendering
        ↓
Block isolation parser — each listing parsed independently (no index drift)
        ↓
Extracts mileage from title, rendered HTML, and description
        ↓
Runs through mileage cap, SKIP_KEYWORDS, VALID_KEYWORDS, price filters
        ↓
New matching vehicle → Discord embed alert → phone buzzes
        ↓
Every 90 min → heartbeat ping confirming system healthy

Why Playwright Instead of requests
This was the core engineering problem that required three pivots to solve.
Attempt 1 — GitHub Actions + requests.get()
Facebook Marketplace is a React single-page application. Plain HTTP requests return an empty shell — JavaScript never executes, no listings load. GitHub Actions was also running from datacenter IP ranges that Facebook's firewall blocks outright regardless of headers or user-agent spoofing. Every search returned Status 400.
Attempt 2 — Local machine + requests.get()
Residential IP solved the firewall problem, but the SPA rendering problem remained. Facebook still returned a blank page because requests doesn't execute JavaScript.
Attempt 3 — Render.com
Cron jobs are not included in Render's free tier. Paid tier would have the same datacenter IP block problem as GitHub Actions.
Solution — Playwright + persistent browser context
Playwright drives a real Chromium browser. Facebook sees a real human browser on a residential IP. The persistent browser context (fb_profile/) saves the authenticated session locally so manual login is only required once. All subsequent runs load the saved session automatically and run headless in the background — invisible, unattended, and undetected.
This is the same fingerprinting logic used by enterprise WAFs and bot-detection systems — understanding it from the automation side directly informs how defenders build detection rules.

Key Engineering Decisions
Block isolation parser — Each listing is parsed as an independent DOM block. Earlier versions used four separate findall() passes across the full page, which caused index misalignment when listings had missing fields (wrong price matched to wrong listing). Block isolation eliminated this entirely.
Listing ID extraction fix — Early versions grabbed any 10+ digit number from the page using generic regex, which matched image IDs, user IDs, and other Facebook object IDs — generating broken listing URLs. The fix targets the specific "listing":{"__typename":"GroupCommerceProductItem","id":"..." pattern, which is always the actual marketplace listing ID.
Three-layer mileage extraction — Facebook only includes mileage in structured JSON on individual listing pages, not search results. On search pages, mileage appears in three inconsistent locations: the listing title (e.g. 232,936 mi.), the rendered HTML span elements (e.g. 170K miles), and the seller description. The extractor checks all three and handles formats including 176K miles, 176,000 miles, 176,000 mi, and 176000.
Crash handler wrapping main() — Unattended scripts that fail silently are useless. Any unhandled exception fires a Discord alert with the error before exiting, so failures are visible immediately on your phone.
Absolute file paths via BASE_DIR — crontab runs with a different working directory than Terminal. Relative paths silently break. All file references use os.path.join(BASE_DIR, filename) constructed from __file__.
input() hang prevention — An earlier version blocked on input() when the Facebook session expired, freezing the script forever during unattended runs. Replaced with a Discord warning + clean exit.
Random delays (5–10s) between requests — Reduces request fingerprinting and mimics human browsing cadence.
Full Python path in crontab — macOS crontab uses a restricted environment with a different PATH than Terminal. Using the full Python path (/Library/Frameworks/Python.framework/Versions/3.14/bin/python3) ensures the correct interpreter and installed packages are always found.
Full Disk Access for Terminal — macOS silently blocks crontab jobs from accessing files without Full Disk Access granted to Terminal in System Settings → Privacy & Security.

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
What Was BuiltSecurity/Engineering ParallelPivoted from requests to Playwright after fingerprint detectionUnderstanding WAF evasion, bot-detection logic, and browser fingerprintingThree-layer mileage extraction from inconsistent data sourcesParsing unstructured/inconsistent data — same challenge in log analysis and SIEM ingestionSession stored locally, never uploaded to remoteSession management and credential hygieneSKIP_KEYWORDS / VALID_KEYWORDS filteringInput validation and sanitization — same logic used in SIEM detection rules to reduce noiseSwitched from GitHub Actions to local cronInfrastructure constraint analysis — knowing when cloud environments are non-viableCrash handler + Discord alertingOperational monitoring and alerting pipeline designBlock isolation parserStructured data parsing and handling malformed/inconsistent inputsListing ID extraction fixUnderstanding application data structure — same skill used in API fuzzing and recon

Lessons Learned

Facebook actively blocks all datacenter scraping — GitHub Actions, hosted services, and VPNs all fail because IP reputation is checked before any content is served
Real browser automation is the only reliable free solution for SPAs — requests.get() is dead against React apps
crontab requires exact Python paths and Full Disk Access — silent failures are almost always a permissions or path issue
Never block on input() in unattended scripts — it hangs forever in cron context
Three LLMs reviewing the same code independently caught real bugs — index misalignment, missing keyword filters, the input() hang, and broken listing ID extraction were all caught in review
Mileage data lives in three different places in Facebook's page depending on listing — robust extraction requires checking all of them


Built and documented by Hunter Hanners — active duty U.S. Army, pursuing offensive security roles
