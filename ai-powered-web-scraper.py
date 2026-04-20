import streamlit as st
import pandas as pd
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import subprocess
import os

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Advanced Web Scraper", layout="wide")
st.title("🚀 Advanced Web Scraper (Selenium Powered)")
st.markdown("Handles dynamic websites (JavaScript loaded content)")

# ---------- INPUT ----------
url = st.text_input("Enter Website URL")
selected_options = st.multiselect(
    "Select what you want to extract:",
    ["Title", "Headings", "Links", "Images", "Paragraphs", "Emails"]
)
max_items = st.slider("Limit results per category", 5, 100, 20)


# ---------- DETECT CHROME / CHROMIUM BINARY ----------
def get_chrome_binary():
    """Detect the correct Chrome/Chromium binary path."""
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

    # Try which command
    for name in ["chromium", "chromium-browser", "google-chrome"]:
        try:
            result = subprocess.run(["which", name], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    return None


def get_chromedriver_path():
    """Detect the correct chromedriver path."""
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
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


# ---------- FUNCTION TO LOAD PAGE ----------
def get_page_source(target_url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Detect binary paths
    binary = get_chrome_binary()
    driver_path = get_chromedriver_path()

    if binary:
        chrome_options.binary_location = binary
    else:
        raise EnvironmentError(
            "Chrome/Chromium binary not found. "
            "Add 'chromium' and 'chromium-driver' to packages.txt (Streamlit Cloud), "
            "or install via: sudo apt-get install -y chromium chromium-driver"
        )

    if driver_path:
        service = Service(driver_path)
    else:
        raise EnvironmentError(
            "chromedriver not found. "
            "Add 'chromium-driver' to packages.txt (Streamlit Cloud), "
            "or install via: sudo apt-get install -y chromium-driver"
        )

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(target_url)
        driver.implicitly_wait(5)
        page_source = driver.page_source
    finally:
        driver.quit()

    return page_source


# ---------- SCRAPE ----------
if st.button("🚀 Scrape Now"):
    if not url:
        st.warning("⚠️ Please enter a URL first.")
    elif not selected_options:
        st.warning("⚠️ Please select at least one extraction option.")
    else:
        with st.spinner("🔄 Loading page with Selenium..."):
            try:
                html = get_page_source(url)
                soup = BeautifulSoup(html, "html.parser")
                data = []

                # TITLE
                if "Title" in selected_options:
                    title = soup.title.string.strip() if soup.title else "No title found"
                    data.append({"Type": "Title", "Value": title})

                # HEADINGS
                if "Headings" in selected_options:
                    for tag in soup.find_all(["h1", "h2", "h3"])[:max_items]:
                        text = tag.text.strip()
                        if text:
                            data.append({"Type": f"Heading ({tag.name.upper()})", "Value": text})

                # LINKS
                if "Links" in selected_options:
                    seen_links = set()
                    count = 0
                    for link in soup.find_all("a"):
                        if count >= max_items:
                            break
                        href = link.get("href")
                        if href and href not in seen_links:
                            full_url = urljoin(url, href)
                            seen_links.add(href)
                            data.append({"Type": "Link", "Value": full_url})
                            count += 1

                # IMAGES
                if "Images" in selected_options:
                    seen_imgs = set()
                    count = 0
                    for img in soup.find_all("img"):
                        if count >= max_items:
                            break
                        src = img.get("src") or img.get("data-src")
                        if src and src not in seen_imgs:
                            seen_imgs.add(src)
                            data.append({"Type": "Image", "Value": urljoin(url, src)})
                            count += 1

                # PARAGRAPHS
                if "Paragraphs" in selected_options:
                    count = 0
                    for p in soup.find_all("p"):
                        if count >= max_items:
                            break
                        text = p.text.strip()
                        if text:
                            data.append({"Type": "Paragraph", "Value": text})
                            count += 1

                # EMAILS
                if "Emails" in selected_options:
                    emails = re.findall(
                        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
                        html
                    )
                    for email in list(set(emails))[:max_items]:
                        data.append({"Type": "Email", "Value": email})

                # ---------- DISPLAY RESULTS ----------
                df = pd.DataFrame(data)

                if not df.empty:
                    st.success(f"✅ Scraping Completed! Found {len(df)} items.")

                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.subheader("📋 Scraped Data")
                        st.dataframe(df, use_container_width=True)

                    with col2:
                        st.subheader("📊 Summary")
                        summary = df["Type"].value_counts().reset_index()
                        summary.columns = ["Type", "Count"]
                        st.dataframe(summary, use_container_width=True)

                    # Download CSV
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv,
                        file_name="scraped_data.csv",
                        mime="text/csv"
                    )

                    # Show images if extracted
                    if "Images" in selected_options:
                        img_urls = df[df["Type"] == "Image"]["Value"].tolist()
                        if img_urls:
                            st.subheader("🖼️ Image Preview")
                            cols = st.columns(4)
                            for i, img_url in enumerate(img_urls[:8]):
                                with cols[i % 4]:
                                    try:
                                        st.image(img_url, use_container_width=True)
                                    except Exception:
                                        st.caption(f"Could not load: {img_url[:40]}...")

                else:
                    st.warning("⚠️ No data found. The page might be blocking scraping or the selectors found nothing.")

            except EnvironmentError as env_err:
                st.error(f"🔧 Setup Error: {env_err}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                with st.expander("🔍 Debug Info"):
                    st.code(str(e))
