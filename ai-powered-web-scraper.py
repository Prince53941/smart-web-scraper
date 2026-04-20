import streamlit as st
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from collections import deque

# Try selenium import
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    import subprocess, os
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Email Extractor Pro", layout="wide", page_icon="📧")

st.markdown("""
    <style>
        .email-card {
            background: #f0f9ff;
            border-left: 4px solid #0ea5e9;
            padding: 10px 16px;
            border-radius: 6px;
            margin: 4px 0;
            font-family: monospace;
            font-size: 15px;
            color: #0c4a6e;
        }
        .stat-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
        }
        .stat-number { font-size: 2rem; font-weight: 700; color: #0ea5e9; }
        .stat-label  { font-size: 0.85rem; color: #64748b; }
    </style>
""", unsafe_allow_html=True)

st.title("📧 Email Extractor Pro")
st.markdown("Extract emails from any website — single page or full site crawl.")

# ---------- CONSTANTS ----------
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".pdf", ".zip", ".rar", ".exe", ".mp4", ".mp3",
    ".css", ".js", ".ico", ".woff", ".ttf"
}

COMMON_EMAIL_PAGES = [
    "contact", "contact-us", "contactus", "about", "about-us",
    "team", "staff", "people", "support", "help", "info",
    "reach-us", "get-in-touch", "connect", "enquiry", "inquiry"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------- HELPERS ----------
def is_valid_email(email):
    """Filter out false positives."""
    noise = [
        "example", "domain", "youremail", "email@", "user@",
        "test@", "sample", "placeholder", "yourname", "name@",
        "sentry", ".png", ".jpg", ".svg", "noreply", "no-reply",
        "donotreply", "do-not-reply", "wixpress", "sampleemail"
    ]
    email_lower = email.lower()
    return not any(n in email_lower for n in noise)


def extract_emails_from_html(html):
    """Extract and clean emails from raw HTML."""
    # Also decode HTML entities like &#64; → @
    html_decoded = html.replace("&#64;", "@").replace("%40", "@").replace("[at]", "@").replace(" at ", "@")
    raw = EMAIL_REGEX.findall(html_decoded)
    return {e.lower() for e in raw if is_valid_email(e)}


def get_all_links(soup, base_url):
    """Extract all internal links from a page."""
    base_domain = urlparse(base_url).netloc
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        # Only same-domain, http/https, no file extensions
        if (
            parsed.netloc == base_domain
            and parsed.scheme in ("http", "https")
            and not any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS)
            and "#" not in full
        ):
            links.add(full.split("?")[0])  # strip query params
    return links


def score_link_priority(url):
    """Return higher score for URLs likely to have emails."""
    url_lower = url.lower()
    for i, keyword in enumerate(COMMON_EMAIL_PAGES):
        if keyword in url_lower:
            return len(COMMON_EMAIL_PAGES) - i  # higher = better
    return 0


def fetch_html_requests(url):
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


# ---------- SELENIUM HELPERS ----------
def get_chrome_binary():
    import os, subprocess
    candidates = ["/usr/bin/chromium", "/usr/bin/chromium-browser",
                  "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]
    for p in candidates:
        if os.path.exists(p):
            return p
    for name in ["chromium", "chromium-browser", "google-chrome"]:
        try:
            r = subprocess.run(["which", name], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return None


def get_chromedriver_path():
    import os, subprocess
    candidates = ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver",
                  "/usr/lib/chromium-browser/chromedriver"]
    for p in candidates:
        if os.path.exists(p):
            return p
    try:
        r = subprocess.run(["which", "chromedriver"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def fetch_html_selenium(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")

    binary = get_chrome_binary()
    driver_path = get_chromedriver_path()
    if not binary or not driver_path:
        raise EnvironmentError("Chrome/Chromium not found. Add 'chromium chromium-driver' to packages.txt")

    chrome_options.binary_location = binary
    driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)
        return driver.page_source
    finally:
        driver.quit()


# ---------- CORE CRAWL FUNCTION ----------
def crawl_and_extract(
    start_url,
    max_pages,
    use_selenium,
    delay,
    progress_bar,
    status_text,
    log_container
):
    visited = set()
    emails_found = {}       # email → [list of source URLs]
    queue = deque()

    # Seed queue with start URL + common contact pages
    queue.append((start_url, 0))
    base_domain = urlparse(start_url).netloc
    base = f"{urlparse(start_url).scheme}://{base_domain}"
    for page in COMMON_EMAIL_PAGES:
        queue.append((f"{base}/{page}", 1))
        queue.append((f"{base}/{page}/", 1))

    pages_crawled = 0
    logs = []

    fetch_fn = fetch_html_selenium if use_selenium else fetch_html_requests

    while queue and pages_crawled < max_pages:
        url, priority = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        try:
            status_text.markdown(f"🔍 Scanning: `{url}`")
            html = fetch_fn(url)
            soup = BeautifulSoup(html, "html.parser")

            # Extract emails
            found = extract_emails_from_html(html)
            for email in found:
                if email not in emails_found:
                    emails_found[email] = []
                emails_found[email].append(url)

            log_entry = f"✅ `{url}` → **{len(found)}** email(s) found"
            logs.append(log_entry)

            # Add new links to queue, prioritized
            if pages_crawled < max_pages - 1:
                new_links = get_all_links(soup, url)
                prioritized = sorted(
                    new_links - visited,
                    key=score_link_priority,
                    reverse=True
                )
                for link in prioritized:
                    queue.append((link, score_link_priority(link)))

            pages_crawled += 1
            progress_bar.progress(min(pages_crawled / max_pages, 1.0))
            log_container.markdown("\n\n".join(logs[-10:]))  # show last 10

            if delay > 0:
                time.sleep(delay)

        except Exception as e:
            logs.append(f"⚠️ `{url}` → skipped ({str(e)[:60]})")
            log_container.markdown("\n\n".join(logs[-10:]))
            continue

    return emails_found, pages_crawled


# ===================== UI =====================

tab1, tab2 = st.tabs(["🔍 Extractor", "ℹ️ How It Works"])

with tab1:
    url_input = st.text_input(
        "🌐 Enter Website URL",
        placeholder="https://toscrape.com",
        help="Enter the starting URL. The crawler will find emails on this page and linked pages."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        crawl_mode = st.radio(
            "Crawl Mode",
            ["Single Page", "Deep Crawl"],
            help="Single Page = only this URL. Deep Crawl = follows links across the site."
        )
    with col2:
        max_pages = st.slider(
            "Max Pages to Scan",
            min_value=1, max_value=50, value=5,
            disabled=(crawl_mode == "Single Page"),
            help="How many pages to crawl. More pages = more emails but slower."
        )
        if crawl_mode == "Single Page":
            max_pages = 1
    with col3:
        use_selenium = st.toggle(
            "Use Selenium",
            value=False,
            help="Enable for JS-heavy sites. Slower but more thorough."
        )
        delay = st.slider(
            "Delay between requests (sec)",
            min_value=0.0, max_value=3.0, value=0.5, step=0.5,
            help="Be polite to servers. 0.5s recommended."
        )

    # Extra options
    with st.expander("⚙️ Advanced Options"):
        also_extract = st.multiselect(
            "Also extract (bonus data)",
            ["Page Titles", "Phone Numbers", "Social Media Links"],
            default=[]
        )

    if st.button("🚀 Extract Emails", type="primary", use_container_width=True):
        if not url_input:
            st.warning("⚠️ Please enter a URL.")
        else:
            if not url_input.startswith("http"):
                url_input = "https://" + url_input

            st.divider()
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_container = st.empty()

            with st.spinner(""):
                emails_found, pages_crawled = crawl_and_extract(
                    start_url=url_input,
                    max_pages=max_pages,
                    use_selenium=use_selenium,
                    delay=delay,
                    progress_bar=progress_bar,
                    status_text=status_text,
                    log_container=log_container
                )

            progress_bar.progress(1.0)
            status_text.empty()
            log_container.empty()

            st.divider()

            # ---- STATS ROW ----
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-number">{len(emails_found)}</div>
                        <div class="stat-label">Unique Emails Found</div>
                    </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-number">{pages_crawled}</div>
                        <div class="stat-label">Pages Scanned</div>
                    </div>
                """, unsafe_allow_html=True)
            with c3:
                domains = len({e.split("@")[1] for e in emails_found}) if emails_found else 0
                st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-number">{domains}</div>
                        <div class="stat-label">Unique Domains</div>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            if emails_found:
                st.success(f"✅ Found **{len(emails_found)}** unique email(s)!")

                # ---- EMAIL CARDS ----
                st.subheader("📧 Extracted Emails")
                for email, sources in sorted(emails_found.items()):
                    source_str = sources[0] if sources else ""
                    st.markdown(
                        f'<div class="email-card">📨 {email} '
                        f'<span style="font-size:11px;color:#94a3b8;float:right">'
                        f'found on {len(sources)} page(s)</span></div>',
                        unsafe_allow_html=True
                    )

                # ---- TABLE + DOWNLOAD ----
                st.subheader("📋 Full Results Table")
                rows = []
                for email, sources in emails_found.items():
                    domain = email.split("@")[1] if "@" in email else ""
                    rows.append({
                        "Email": email,
                        "Domain": domain,
                        "Found On (first page)": sources[0],
                        "Total Pages Found On": len(sources)
                    })
                df = pd.DataFrame(rows).sort_values("Email")
                st.dataframe(df, use_container_width=True)

                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download Emails as CSV",
                    csv,
                    "emails_extracted.csv",
                    "text/csv",
                    use_container_width=True
                )

                # ---- BONUS EXTRACTIONS ----
                if also_extract:
                    st.divider()
                    st.subheader("➕ Bonus Extractions")

                    if "Phone Numbers" in also_extract:
                        phone_regex = re.compile(
                            r"(\+?\d[\d\s\-\.\(\)]{7,}\d)"
                        )
                        # Re-fetch first page for bonus data
                        try:
                            html_bonus = fetch_html_requests(url_input)
                            phones = list(set(phone_regex.findall(html_bonus)))[:20]
                            if phones:
                                st.write("**📞 Phone Numbers:**")
                                for p in phones:
                                    st.code(p.strip())
                            else:
                                st.info("No phone numbers found on main page.")
                        except Exception:
                            st.warning("Could not fetch bonus data.")

                    if "Social Media Links" in also_extract:
                        social_domains = ["twitter.com", "x.com", "linkedin.com",
                                          "facebook.com", "instagram.com", "youtube.com",
                                          "github.com", "tiktok.com"]
                        try:
                            html_bonus = fetch_html_requests(url_input)
                            soup_bonus = BeautifulSoup(html_bonus, "html.parser")
                            social_links = []
                            for a in soup_bonus.find_all("a", href=True):
                                href = a["href"]
                                if any(sd in href for sd in social_domains):
                                    social_links.append(href)
                            social_links = list(set(social_links))
                            if social_links:
                                st.write("**🔗 Social Media Links:**")
                                for sl in social_links:
                                    st.markdown(f"- [{sl}]({sl})")
                            else:
                                st.info("No social media links found on main page.")
                        except Exception:
                            st.warning("Could not fetch bonus data.")

            else:
                st.warning("⚠️ No emails found.")
                st.markdown("""
                **Tips to find more emails:**
                - Enable **Deep Crawl** and increase max pages
                - Try enabling **Selenium** if the site is JS-heavy
                - Try visiting the site's `/contact` or `/about` page directly
                - Some sites obfuscate emails (e.g. `user [at] domain.com`) — these are handled automatically

                **Test with these URLs:**
                - `https://toscrape.com` — has visible emails
                - `https://quotes.toscrape.com` — good for general testing
                """)

with tab2:
    st.markdown("""
    ### How Email Extractor Pro Works

    **1. Smart Crawling**
    The tool starts at your URL and automatically prioritizes pages likely to have emails —
    `/contact`, `/about`, `/team`, `/support`, etc. are always checked first.

    **2. Deep Extraction**
    Emails are extracted from raw HTML, including obfuscated formats like `&#64;` (HTML entity for @)
    and `%40` (URL-encoded @).

    **3. False Positive Filtering**
    Common fake emails like `example@domain.com`, `noreply@`, `test@` are automatically removed.

    **4. Two Fetch Methods**
    - **Requests** (default): Fast, works on 90% of sites
    - **Selenium**: Slower, handles JavaScript-rendered pages (requires Chromium installed)

    **5. Deep Crawl Mode**
    Follows internal links up to your max page limit, staying within the same domain.
    Links are scored by relevance — contact/about pages are visited before random product pages.

    ---
    ### Best Test URLs
    | URL | What to expect |
    |-----|---------------|
    | `https://toscrape.com` | Emails present |
    | `https://quotes.toscrape.com` | Good general test |
    | `https://en.wikipedia.org/wiki/Python_(programming_language)` | No emails (expected) |
    """)
