import streamlit as st
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import subprocess
import os

# Try importing selenium — gracefully handle if unavailable
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Advanced Web Scraper", layout="wide")
st.title("🚀 Advanced Web Scraper")
st.markdown("Supports both static and JavaScript-rendered websites.")

# ---------- INPUT ----------
url = st.text_input("Enter Website URL", placeholder="https://books.toscrape.com")

selected_options = st.multiselect(
    "Select what you want to extract:",
    ["Title", "Headings", "Links", "Images", "Paragraphs", "Emails"],
    default=["Title", "Headings", "Paragraphs"]
)

col_a, col_b = st.columns(2)
with col_a:
    max_items = st.slider("Limit results per category", 5, 100, 20)
with col_b:
    use_selenium = st.toggle(
        "Use Selenium (for JS-heavy sites)",
        value=False,
        help="Turn OFF for faster scraping of static sites like Wikipedia, books.toscrape.com"
    )

# ---------- HEADERS FOR REQUESTS ----------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ---------- METHOD 1: REQUESTS (FAST, STATIC SITES) ----------
def get_page_source_requests(target_url):
    response = requests.get(target_url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.text


# ---------- DETECT CHROME PATHS ----------
def get_chrome_binary():
    candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    for name in ["chromium", "chromium-browser", "google-chrome"]:
        try:
            result = subprocess.run(["which", name], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    return None


def get_chromedriver_path():
    candidates = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
        "/snap/bin/chromedriver",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


# ---------- METHOD 2: SELENIUM (JS SITES) ----------
def get_page_source_selenium(target_url):
    if not SELENIUM_AVAILABLE:
        raise EnvironmentError("Selenium is not installed.")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    binary = get_chrome_binary()
    driver_path = get_chromedriver_path()

    if not binary:
        raise EnvironmentError(
            "Chrome/Chromium not found. Add 'chromium' and 'chromium-driver' to packages.txt"
        )
    if not driver_path:
        raise EnvironmentError(
            "chromedriver not found. Add 'chromium-driver' to packages.txt"
        )

    chrome_options.binary_location = binary
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(target_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        import time
        time.sleep(3)
        page_source = driver.page_source
    finally:
        driver.quit()

    return page_source


# ---------- PARSE HTML ----------
def parse_html(html, base_url, options, max_items):
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style tags to clean up text extraction
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    data = []

    # TITLE
    if "Title" in options:
        title = soup.title.string.strip() if soup.title else "No title found"
        data.append({"Type": "Title", "Value": title, "Label": ""})

    # HEADINGS
    if "Headings" in options:
        count = 0
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            if count >= max_items:
                break
            text = tag.text.strip()
            if text:
                data.append({"Type": f"Heading ({tag.name.upper()})", "Value": text, "Label": ""})
                count += 1

    # LINKS
    if "Links" in options:
        seen = set()
        count = 0
        for link in soup.find_all("a", href=True):
            if count >= max_items:
                break
            href = link["href"]
            full = urljoin(base_url, href)
            if full not in seen and full.startswith("http"):
                seen.add(full)
                label = link.text.strip() or "(no text)"
                data.append({"Type": "Link", "Value": full, "Label": label})
                count += 1

    # IMAGES
    if "Images" in options:
        seen = set()
        count = 0
        for img in soup.find_all("img"):
            if count >= max_items:
                break
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src and src not in seen:
                seen.add(src)
                full_src = urljoin(base_url, src)
                alt = img.get("alt", "")
                data.append({"Type": "Image", "Value": full_src, "Label": alt})
                count += 1

    # PARAGRAPHS
    if "Paragraphs" in options:
        count = 0
        for p in soup.find_all("p"):
            if count >= max_items:
                break
            text = p.text.strip()
            if len(text) > 20:
                data.append({"Type": "Paragraph", "Value": text, "Label": ""})
                count += 1

    # EMAILS
    if "Emails" in options:
        emails = re.findall(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            html
        )
        for email in list(set(emails))[:max_items]:
            if "example" not in email and "domain" not in email:
                data.append({"Type": "Email", "Value": email, "Label": ""})

    return data, soup


# ---------- SCRAPE BUTTON ----------
if st.button("🚀 Scrape Now"):
    if not url:
        st.warning("⚠️ Please enter a URL first.")
    elif not selected_options:
        st.warning("⚠️ Please select at least one option.")
    else:
        with st.spinner("🔄 Fetching page..."):
            try:
                if use_selenium:
                    st.info("⏳ Using Selenium (slower but handles JS)...")
                    html = get_page_source_selenium(url)
                else:
                    st.info("⚡ Using Requests (fast, works for most static sites)...")
                    html = get_page_source_requests(url)

                # Debug panel — always show so user can diagnose
                with st.expander("🔍 Debug: Raw HTML Info"):
                    st.write(f"**HTML size:** {len(html):,} characters")
                    st.write(f"**First 500 chars:**")
                    st.code(html[:500])

                data, soup = parse_html(html, url, selected_options, max_items)
                df = pd.DataFrame(data)

                if not df.empty:
                    st.success(f"✅ Done! Found **{len(df)}** items.")

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.subheader("📋 Scraped Data")
                        st.dataframe(df, use_container_width=True)
                    with col2:
                        st.subheader("📊 Summary")
                        summary = df["Type"].value_counts().reset_index()
                        summary.columns = ["Type", "Count"]
                        st.dataframe(summary, use_container_width=True)

                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Download CSV", csv, "scraped_data.csv", "text/csv")

                    # Image preview
                    if "Images" in selected_options:
                        img_rows = df[df["Type"] == "Image"]["Value"].tolist()
                        if img_rows:
                            st.subheader("🖼️ Image Preview")
                            cols = st.columns(4)
                            for i, img_url in enumerate(img_rows[:8]):
                                with cols[i % 4]:
                                    try:
                                        st.image(img_url, use_container_width=True)
                                    except Exception:
                                        st.caption("Could not load image")

                else:
                    st.warning("⚠️ No data extracted.")
                    st.markdown("""
                    **Check the Debug panel above.** Common causes:
                    - HTML size < 2000 chars → site blocked the request, try a different URL
                    - HTML size is large but no data → selectors didn't match, open an issue
                    
                    **Known working test URLs (use with Selenium OFF):**
                    - `https://books.toscrape.com`
                    - `https://quotes.toscrape.com`
                    - `https://en.wikipedia.org/wiki/Web_scraping`
                    """)

            except EnvironmentError as env_err:
                st.error(f"🔧 Setup Error: {env_err}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect. Check the URL and your internet connection.")
            except requests.exceptions.HTTPError as e:
                st.error(f"❌ HTTP Error: {e} — The site returned an error response.")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {str(e)}")
                with st.expander("🔍 Full Traceback"):
                    import traceback
                    st.code(traceback.format_exc())
