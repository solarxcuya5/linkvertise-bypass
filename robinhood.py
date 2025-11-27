#!/usr/bin/env python3
import os
import random
import string
import logging
import linkvertise_bypasser as linkvertise

# ==============================
# 1. BIKIN NAMA FILE RANDOM
# ==============================
def random_filename():
    letters = string.ascii_lowercase + string.digits
    name = "".join(random.choice(letters) for _ in range(8))
    return name + ".txt"

OUTPUT_FILE = random_filename()

# ==============================
# 2. PARSE mega.txt
# ==============================
entries = []    # (name, url)

current_name = None

with open("mega.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if line.startswith("🌐"):  
            current_name = line

        elif line.startswith("http://") or line.startswith("https://"):
            if current_name:
                entries.append((current_name, line))
            current_name = None

# ==============================
# 3. SETUP LOGGING + SESSION UA
# ==============================
logging.basicConfig(level=logging.INFO)

session = linkvertise.RandomUserAgentSession()

try:
    ua = getattr(session, "_ua", None)
    if ua:
        print("Session User-Agent:", ua)
except:
    pass

print(f"Total data ditemukan: {len(entries)}\n")

# ==============================
# 4. BYPASS & SIMPAN KE FILE
# ==============================
with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    for idx, (name, ad_url) in enumerate(entries, start=1):
        print(f"[{idx}/{len(entries)}] Bypass:", ad_url)

        try:
            bypassed = linkvertise.bypass(ad_url, session=session)
            print("   ✓ SUCCESS →", bypassed)

            out.write(name + "\n")
            out.write(bypassed + "\n\n")

        except Exception as e:
            print("   ✗ ERROR:", e)
            out.write(name + "\n")
            out.write("ERROR: " + str(e) + "\n\n")

print("\nSelesai!")
print("Disimpan di:", OUTPUT_FILE)