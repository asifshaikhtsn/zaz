#!/usr/bin/env python3
"""zaz: validate public proxies, use current MaxMind DB, publish country-filtered lists."""
import asyncio
import collections
import datetime as dt
import ipaddress
import json
import os
import random
import re
import shutil
import sys
from pathlib import Path

import aiohttp
from aiohttp_socks import ProxyConnector
import geoip2.database

PROTOCOLS = ("http", "https", "socks4", "socks5")
PUBLIC_HOST = "https://raw.githubusercontent.com"
TEST_URL = "https://www.google.com/generate_204"
PROXY_RE = re.compile(r"^([0-9.]+):(\d{1,5})$")


def parse_proxy(s):
    m = PROXY_RE.fullmatch(s.strip())
    if not m:
        return None
    try:
        ip = ipaddress.IPv4Address(m.group(1))
        port = int(m.group(2))
        if ip.is_global and 1 <= port <= 65535:
            return f"{ip}:{port}"
    except (ValueError, ipaddress.AddressValueError):
        pass
    return None


def source_url(repo, country, protocol):
    branch = "master" if repo.endswith("/shaikh") else "main"
    return f"{PUBLIC_HOST}/{repo}/{branch}/country/{country}/{protocol}.txt"


async def fetch_candidates(config):
    jobs = [(repo, cc, proto, source_url(repo, cc, proto))
            for repo in config["sources"][:3]
            for cc in config["allowed_countries"] for proto in PROTOCOLS]
    jobs += [("hproxy-com/free-proxy-list", None, proto,
              f"{PUBLIC_HOST}/hproxy-com/free-proxy-list/main/{proto}.txt")
             for proto in PROTOCOLS]
    gate = asyncio.Semaphore(20)
    candidates = set()
    per_source = collections.Counter()
    failures = []
    success_files = 0

    async with aiohttp.ClientSession(headers={"User-Agent": "zaz-validator/1.0"}) as sess:
        async def fetch(repo, country, proto, url):
            nonlocal success_files
            async with gate:
                for attempt in range(2):
                    try:
                        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=25)) as response:
                            if response.status == 404:
                                return
                            response.raise_for_status()
                            body = await response.text()
                        success_files += 1
                        for raw in body.splitlines():
                            proxy = parse_proxy(raw)
                            if proxy and (proto, proxy) not in candidates:
                                candidates.add((proto, proxy))
                                per_source[repo] += 1
                        return
                    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                        if attempt:
                            failures.append({"source": repo, "error": type(exc).__name__})
                        else:
                            await asyncio.sleep(1)
        await asyncio.gather(*(fetch(*job) for job in jobs))
    if not candidates or not success_files:
        raise RuntimeError("All source fetches failed; preserving existing output")
    return candidates, dict(per_source), failures, success_files


def select_for_test(candidates, db, allowed, budget):
    groups = collections.defaultdict(list)
    for proto, proxy in sorted(candidates):
        try:
            country = db.country(proxy.split(":")[0]).country.iso_code
        except Exception:
            country = None
        if country in allowed:
            groups[country].append((country, proto, proxy))
    # Round-robin country sampling avoids allocating the entire budget to big countries.
    rng = random.Random(int(dt.datetime.now(dt.timezone.utc).timestamp() // 3600))
    for group in groups.values():
        rng.shuffle(group)
    countries = sorted(groups)
    rng.shuffle(countries)
    selected = []
    while len(selected) < budget:
        added = False
        for cc in countries:
            if groups[cc]:
                selected.append(groups[cc].pop())
                added = True
                if len(selected) == budget:
                    break
        if not added:
            break
    return selected


async def check_proxy(country, proto, proxy, limit, seconds):
    async with limit:
        try:
            timeout = aiohttp.ClientTimeout(total=seconds)
            if proto.startswith("socks"):
                conn = ProxyConnector.from_url(f"{proto}://{proxy}", rdns=True, limit=1)
                async with aiohttp.ClientSession(connector=conn, timeout=timeout) as sess:
                    async with sess.get(TEST_URL, allow_redirects=False) as resp:
                        return resp.status == 204
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get(TEST_URL, proxy=f"http://{proxy}",
                                    allow_redirects=False) as resp:
                    return resp.status == 204
        except Exception:
            # Public proxies routinely refuse connections or fail SOCKS handshakes.
            # python-socks raises ProxyConnectionError/ProxyError, which are not
            # necessarily aiohttp.ClientError; a single bad endpoint must not
            # abort the entire validation batch.
            return False


async def validate(candidates, config):
    sem = asyncio.Semaphore(config["concurrency"])
    ok = await asyncio.gather(*(check_proxy(*record, sem, config["timeout_seconds"])
                                for record in candidates))
    return {record for record, healthy in zip(candidates, ok) if healthy}


def publish(validated, report, threshold):
    if len(validated) < threshold:
        raise RuntimeError("Not enough live proxies; preserving existing outputs")
    next_dir = Path(".country-next")
    old_dir = Path(".country-old")
    if next_dir.exists():
        shutil.rmtree(next_dir)
    next_dir.mkdir()
    country_counts = collections.Counter()
    protocol_counts = collections.Counter()
    combined = []
    groups = collections.defaultdict(list)
    for cc, proto, proxy in validated:
        groups[(cc, proto)].append(proxy)
        combined.append(f"{proto}://{proxy}")
        country_counts[cc] += 1
        protocol_counts[proto] += 1
    for (cc, proto), addresses in groups.items():
        dst = next_dir / cc
        dst.mkdir(exist_ok=True)
        (dst / f"{proto}.txt").write_text("\n".join(sorted(addresses)) + "\n",
                                           encoding="utf-8")
    if old_dir.exists():
        shutil.rmtree(old_dir)
    current = Path("country")
    if current.exists():
        current.rename(old_dir)
    next_dir.rename(current)
    Path("all_working.txt").write_text("\n".join(sorted(combined)) + "\n",
                                       encoding="utf-8")
    report.update({
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stored_count": len(validated),
        "country_counts": dict(sorted(country_counts.items())),
        "protocol_counts": dict(sorted(protocol_counts.items()))
    })
    Path("last_run.json").write_text(json.dumps(report, indent=2) + "\n",
                                      encoding="utf-8")
    if old_dir.exists():
        shutil.rmtree(old_dir)
    print(json.dumps({k: report[k] for k in
                      ("timestamp", "stored_count", "country_counts")}, indent=2))


async def main():
    config = json.loads(Path("config.json").read_text())
    allowed = set(config["allowed_countries"])
    if len(allowed) != 43:
        raise RuntimeError("Expected exactly 43 countries/territories")
    # Validate the actual MMDB build date, not a hardcoded archive filename.
    db_path = Path(os.environ.get("GEOIP_DB_PATH", "GeoLite2-Country.mmdb"))
    if not db_path.is_file():
        raise RuntimeError("GeoLite2 Country .mmdb missing; automatic download must succeed")
    with geoip2.database.Reader(str(db_path)) as reader:
        metadata = reader.metadata()
        if metadata.database_type != "GeoLite2-Country":
            raise RuntimeError("Wrong MaxMind database: GeoLite2-Country is required")
        built = dt.datetime.fromtimestamp(metadata.build_epoch, tz=dt.timezone.utc)
        age_days = (dt.datetime.now(dt.timezone.utc) - built).total_seconds() / 86400
        if age_days > 30 or age_days < -2:
            raise RuntimeError(f"MaxMind database is outdated or has invalid build date ({age_days:.1f} days old)")
    candidates, source_counts, failures, downloaded = await fetch_candidates(config)
    with geoip2.database.Reader(str(db_path)) as db:
        selected = select_for_test(candidates, db, allowed, config["max_tests_per_run"])
    if not selected:
        raise RuntimeError("No IPs geolocated into the allowed countries")
    passed = await validate(selected, config)
    publish(passed, {
        "engine": "zaz-v1", "sources": config["sources"],
        "allowed_countries": config["allowed_countries"],
        "candidate_count": len(candidates),
        "source_candidate_counts": source_counts,
        "source_fetch_failures": failures[:50],
        "source_fetch_failure_count": len(failures),
        "source_files_loaded": downloaded,
        "validation_tested": len(selected),
        "validation_failed": len(selected) - len(passed),
    }, config["minimum_valid_to_publish"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"::error::{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
