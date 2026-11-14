# zaz — country-filtered proxy validator

Collects candidate proxies from Walla, habibi, shaikh and HProxy, validates them, uses **GeoLite2 Country** exclusively for country lookup, and publishes only tested proxies from 43 specified countries and territories.

## Setup

The hourly GitHub Actions workflow **automatically downloads the current official GeoLite2-Country database** directly from MaxMind. Configure two GitHub Actions repository secrets via **Settings → Secrets and variables → Actions → New repository secret**: `MAXMIND_ACCOUNT_ID` and `MAXMIND_LICENSE_KEY`. These are required; never commit credentials. The downloaded `.mmdb` is used locally on the runner (it is not published to the repo). The program checks the MaxMind MMDB metadata to reject incorrect or overly old databases (older than 30 days), with no hardcoded December 2026 expiry. The previously bundled archive is no longer required and should not be uploaded to this public repository.

Enable **Actions**, and set repository **Settings → Actions → General → Workflow permissions → Read and write permissions**. Trigger **Refresh validated proxies** manually the first time. Scheduled runs are requested at minute 7, 22, 37, and 52 UTC each hour. A freshness gate skips redundant scheduled runs if the last successful refresh is less than 50 minutes old; manually dispatched runs always proceed. The additional schedule slots improve retry opportunities but **GitHub Actions does not guarantee exact hourly delivery** and may delay or drop scheduled runs.

Output: one `working_proxies/` folder with `all.txt` (combined `scheme://IP:PORT` list), `http.txt`, `https.txt`, `socks4.txt`, and `socks5.txt` (protocol-specific `IP:PORT` lists). No country output subfolders. `last_run.json` remains at repository root. Unverified, unsupported-country and unresolved country proxies are excluded. The source's country folder is never trusted as evidence of the IP's real location. Tests are performed from GitHub's hosted runner and don't guarantee reachability from other networks.

Database attribution: **This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com**. Also includes GeoNames data. See `geoip/LICENSE.txt`, `geoip/COPYRIGHT.txt` and https://www.maxmind.com/en/geolite/eula. Public redistribution of the database requires complying with the GeoLite EULA, including downstream requirements, attribution, and deleting old databases.

The current budget is 40,000 candidates per run with a bounded concurrency of 220 (instead of the previous 15,000). A maximum budget is not a guarantee that 40,000 candidates are available or country-eligible. Set `max_tests_per_run` in config to manage test budget. An entire source outage or zero healthy validations causes the workflow to fail and preserve the previously published lists. Proxy quality can change at any time. Public proxies can spy on traffic: never use them for sensitive credentials.
