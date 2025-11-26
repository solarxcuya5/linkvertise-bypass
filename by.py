#!/usr/bin/env python3
"""
Driver script for linkvertise_bypasser.py (no Selenium).
- Multithreaded (ThreadPoolExecutor)
- Per-host concurrency limit
- Incremental output (append) so terminal/file aren't 'diam'
- Saves session cookies to session.pkl for reuse

Run example:
    python3 by.py -i mega.txt -t 6 -o hasil.txt --per-host 2 --retries 4

Dependencies:
    pip install requests
    (optional) pip install beautifulsoup4

Termux-friendly: avoids selenium and other non-Python OS tools.
"""

import os
import pickle
import random
import string
import time
import argparse
import concurrent.futures
import threading
import requests
import urllib.parse
import datetime

from linkvertise_bypasser import bypass, BypassFailedError, InvalidLinkError

SESSION_FILE = "session.pkl"
DEFAULT_THREADS = 6
DEFAULT_PER_HOST = 2

# Locks
print_lock = threading.Lock()
file_lock = threading.Lock()
cookie_lock = threading.Lock()
host_lock = threading.Lock()

# merged cookies from worker sessions
merged_cookies = requests.cookies.RequestsCookieJar()

# per-host semaphores
host_semaphores = {}

def now_ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_session_cookies(filename=SESSION_FILE):
    if os.path.exists(filename):
        try:
            with open(filename, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None

def save_session_cookies(cookie_jar, filename=SESSION_FILE):
    try:
        with open(filename, "wb") as f:
            pickle.dump(cookie_jar, f)
    except Exception:
        pass

def make_session_from_cookies(cookies=None):
    s = requests.Session()
    # mobile User-Agent by default (Termux)
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://link-hub.net/",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1"
    })
    if cookies:
        try:
            s.cookies.update(cookies)
        except Exception:
            try:
                s.cookies.update(dict(cookies))
            except Exception:
                pass
    return s

def get_host_semaphore(host, limit):
    with host_lock:
        sem = host_semaphores.get(host)
        if sem is None:
            sem = threading.Semaphore(limit)
            host_semaphores[host] = sem
        return sem

def parse_input_file(input_path):
    entries = []
    current_title = ""
    with open(input_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("🌐"):
                current_title = line
            elif line.startswith("http://") or line.startswith("https://"):
                entries.append((current_title, line))
                current_title = ""
    return entries

def write_result(title, url, result, output_path):
    text = "\n".join([title or "", url, str(result), ""]) + "\n"
    with file_lock:
        with open(output_path, "a", encoding="utf-8") as fout:
            fout.write(text)

def process_entry(idx, total, title, url, initial_cookies, output_path, counters, per_host_limit, max_retries):
    host = urllib.parse.urlparse(url).hostname or "unknown"
    sem = get_host_semaphore(host, per_host_limit)

    session = make_session_from_cookies(initial_cookies)

    with print_lock:
        print(f"{now_ts()} [{idx}/{total}] Start: {url} (host={host})", flush=True)

    # try to acquire semaphore with timeout to avoid indefinite blocking
    acquired = sem.acquire(timeout=60)
    if not acquired:
        result = "Skipped (semaphore timeout)"
        write_result(title, url, result, output_path)
        with print_lock:
            counters['done'] += 1
            print(f"{now_ts()} [{idx}/{total}] Skipped (host busy): {url}", flush=True)
            print(f"{now_ts()} Progress: {counters['done']}/{total}", flush=True)
        return

    try:
        try:
            res = bypass(url, session=session, max_retries=max_retries)
            result = res
        except InvalidLinkError as e:
            result = f"Gagal bypass: {e}"
        except BypassFailedError as e:
            result = f"Gagal bypass: {e}"
        except Exception as e:
            result = f"Unexpected error: {e}"
    finally:
        sem.release()

    # write incremental output
    write_result(title, url, result, output_path)

    # merge cookies from this session
    with cookie_lock:
        try:
            merged_cookies.update(session.cookies)
        except Exception:
            pass

    # write failed to failed.txt for manual retry
    if isinstance(result, str) and (result.startswith("Gagal bypass") or result.startswith("Unexpected")):
        with file_lock:
            with open("failed.txt", "a", encoding="utf-8") as ff:
                ff.write(f"{url} -> {result}\n")

    with print_lock:
        counters['done'] += 1
        print(f"{now_ts()} [{idx}/{total}] Done: {url} -> {str(result)[:160]}", flush=True)
        print(f"{now_ts()} Progress: {counters['done']}/{total}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Linkvertise bypass driver (no selenium)")
    parser.add_argument("-i", "--input", default="mega.txt", help="Input file (default: mega.txt)")
    parser.add_argument("-o", "--output", default=None, help="Output file (default: random <8>.txt)")
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS, help="Number of worker threads")
    parser.add_argument("--per-host", type=int, default=DEFAULT_PER_HOST, help="Max concurrent requests per host")
    parser.add_argument("--retries", type=int, default=3, help="Max retries/backoff attempts in bypass")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print("Input file not found:", args.input)
        return

    output_path = args.output
    if not output_path:
        rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        output_path = rnd + ".txt"

    # truncate output & failed
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("")
    with open("failed.txt", "w", encoding="utf-8") as f:
        f.write("")

    initial_cookies = load_session_cookies(SESSION_FILE)

    entries = parse_input_file(args.input)
    total = len(entries)
    if total == 0:
        print("No entries found in input.")
        return

    print(f"{now_ts()} Mulai memproses {total} entri dengan {args.threads} thread (per-host={args.per_host}). Output: {output_path}")

    counters = {'done': 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as exe:
        futures = []
        for idx, (title, url) in enumerate(entries, start=1):
            futures.append(exe.submit(process_entry, idx, total, title, url, initial_cookies, output_path, counters, args.per_host, args.retries))

        for fut in concurrent.futures.as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                with print_lock:
                    print(f"{now_ts()} Worker exception: {e}", flush=True)

    # save merged cookies
    try:
        save_session_cookies(merged_cookies, SESSION_FILE)
        print(f"{now_ts()} Session disimpan ke {SESSION_FILE}")
    except Exception as e:
        print(f"{now_ts()} Gagal menyimpan session: {e}")

    print(f"{now_ts()} Selesai! File output: {output_path}")
    print(f"{now_ts()} Jika ada kegagalan, periksa failed.txt")

if __name__ == "__main__":
    main()