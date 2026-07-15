#!/usr/bin/env python3
"""
Download Shiller data files from shillerdata.com
"""

import os
import re
import sys
import time
import urllib.request
import hashlib
from bs4 import BeautifulSoup

REQUIRED_FILES = ['ie_data.xls', 'Fig3-1.xls']

RETRY_ATTEMPTS = 3
RETRY_BACKOFF = [2, 4]  # seconds between retry attempts

USER_AGENT = 'Mozilla/5.0 (compatible; shiller-wrapper/1.0; +https://github.com/jwanies/shiller_wrapper_data)'


def _fetch_page():
    """Fetch shillerdata.com homepage with retry and backoff."""
    last_exc = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            req = urllib.request.Request('https://shillerdata.com/',
                                         headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            last_exc = e
            if attempt < RETRY_ATTEMPTS - 1:
                delay = RETRY_BACKOFF[attempt]
                print(f"  Fetch attempt {attempt + 1} failed ({e}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"  All {RETRY_ATTEMPTS} fetch attempts failed")
    raise last_exc


def scrape_download_urls():
    """Scrape download URLs from shillerdata.com, warning instead of raising on misses."""
    print("Scraping download URLs from shillerdata.com...")

    try:
        html = _fetch_page()
    except Exception as e:
        print(f"  ✗ Failed to fetch shillerdata.com after {RETRY_ATTEMPTS} attempts: {e}")
        print(f"  ⚠ Will fall back to committed copies for all files")
        return {}

    soup = BeautifulSoup(html, 'html.parser')
    urls = {}

    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'ie_data.xls' not in urls and re.search(r'ie_data', href, re.I) and re.search(r'\.xlsx?', href, re.I):
            urls['ie_data.xls'] = 'https:' + href if href.startswith('//') else href
            print(f"  ✓ Found ie_data.xls URL")
        elif 'Fig3-1.xls' not in urls and re.search(r'fig\s*3[-.]1', href, re.I) and re.search(r'\.xlsx?', href, re.I):
            urls['Fig3-1.xls'] = 'https:' + href if href.startswith('//') else href
            print(f"  ✓ Found Fig3-1.xls URL")

    for fname in REQUIRED_FILES:
        if fname not in urls:
            print(f"  ⚠ {fname} URL not found on page — will keep committed copy if present")

    return urls


def download_file(url, filename):
    """Download a file from URL to filename."""
    print(f"Downloading {filename} from {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req) as resp, open(filename, 'wb') as f:
            f.write(resp.read())
        print(f"  ✓ Downloaded {filename}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to download {filename}: {e}")
        return False


def get_file_hash(filename):
    """Calculate SHA256 hash of a file."""
    if not os.path.exists(filename):
        return None
    with open(filename, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    """Main function to download all data files."""
    changes = []
    hard_failure = False

    # Scrape the latest download URLs (retries internally, never raises)
    data_files = scrape_download_urls()

    for filename in REQUIRED_FILES:
        old_hash = get_file_hash(filename)
        url = data_files.get(filename)

        if url:
            if download_file(url, filename):
                new_hash = get_file_hash(filename)
                if old_hash != new_hash:
                    if old_hash is None:
                        changes.append(f"Added {filename}")
                    else:
                        changes.append(f"Updated {filename}")
                    print(f"  File changed: {filename}")
                else:
                    print(f"  No changes to {filename}")
            else:
                if old_hash is not None:
                    print(f"  ⚠ Download failed for {filename}, keeping committed copy")
                else:
                    print(f"  ✗ Download failed for {filename} and no committed copy exists")
                    hard_failure = True
        else:
            if old_hash is not None:
                print(f"  ⚠ Keeping committed copy of {filename}")
            else:
                print(f"  ✗ Cannot scrape {filename} URL and no committed copy exists")
                hard_failure = True

    if changes:
        print(f"\n{len(changes)} file(s) changed:")
        for change in changes:
            print(f"  - {change}")
    else:
        print("\nNo changes detected in data files")

    if hard_failure:
        print("\n✗ Required data unavailable — cannot deploy")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
