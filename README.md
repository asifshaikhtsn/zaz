# zaz — country-filtered proxy validator

Collects candidate proxies from Walla, habibi, shaikh and HProxy, validates them, uses **GeoLite2 Country** exclusively for country lookup, and publishes only tested proxies from 43 specified countries and territories.

## Setup

The project uses the bundled database archive `geoip/GeoLite2-Country_20261110.tar.gz`, **not** an online MaxMind download or credentials. Upload that file (from the complete project ZIP) to the `geoip/` folder of this repository. It is required; refresh will fail without it. The archive has an expiry safeguard (December 5, 2026), and must be replaced regularly. For newer releases, edit the file name in the workflow and date in `zaz.py`.

Enable **Actions**, and set repository **Settings → Actions → General → Workflow permissions → Read and write permissions**. Trigger **Refresh validated proxies** manually the first time. Scheduled runs execute at minute 13 each hour UTC, subject to GitHub's scheduling delays.

Output: `country/US/http.txt`, `country/GB/socks5.txt`, etc.; `all_working.txt` and `last_run.json`. Unverified, unsupported-country and unresolved country proxies are excluded. The source's country folder is never trusted as evidence of the IP's real location. Tests are performed from GitHub's hosted runner and don't guarantee reachability from other networks.

Database attribution: **This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com**. Also includes GeoNames data. See `geoip/LICENSE.txt`, `geoip/COPYRIGHT.txt` and https://www.maxmind.com/en/geolite/eula. Public redistribution of the database requires complying with the GeoLite EULA, including downstream requirements, attribution, and deleting old databases.

Set `max_tests_per_run` in config to manage test budget. An entire source outage or zero healthy validations causes the workflow to fail and preserve the previously published lists. Proxy quality can change at any time. Public proxies can spy on traffic: never use them for sensitive credentials.
