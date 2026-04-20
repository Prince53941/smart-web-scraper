import streamlit as st
import pandas as pd
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Advanced Web Scraper", layout="wide")

st.title("🚀 Advanced Web Scraper (Selenium Powered)")
st.markdown("Handles dynamic websites (JavaScript loaded content)")

# ---------- INPUT ----------
url = st.text_input("Enter Website URL")

options = st.multiselect(
    "Select what you want to extract:",
    ["Title", "Headings", "Links", "Images", "Paragraphs", "Emails"]
)

max_items = st.slider("Limit results per category", 5, 100, 20)

# ---------- FUNCTION TO LOAD PAGE ----------
def get_page_source(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get(url)
    driver.implicitly_wait(5)

    page_source = driver.page_source
    driver.quit()

    return page_source

# ---------- SCRAPE ----------
if st.button("🚀 Scrape Now"):
    if not url:
        st.warning("Enter a URL first")
    else:
        try:
            html = get_page_source(url)
            soup = BeautifulSoup(html, "html.parser")

            data = []

            # TITLE
            if "Title" in options:
                title = soup.title.string.strip() if soup.title else "No title"
                data.append({"Type": "Title", "Value": title})

            # HEADINGS
            if "Headings" in options:
                for tag in soup.find_all(["h1", "h2", "h3"])[:max_items]:
                    data.append({"Type": "Heading", "Value": tag.text.strip()})

            # LINKS
            if "Links" in options:
                for link in soup.find_all("a")[:max_items]:
                    href = link.get("href")
                    if href:
                        data.append({
                            "Type": "Link",
                            "Value": urljoin(url, href)
                        })

            # IMAGES
            if "Images" in options:
                for img in soup.find_all("img")[:max_items]:
                    src = img.get("src")
                    if src:
                        data.append({
                            "Type": "Image",
                            "Value": urljoin(url, src)
                        })

            # PARAGRAPHS
            if "Paragraphs" in options:
                for p in soup.find_all("p")[:max_items]:
                    text = p.text.strip()
                    if text:
                        data.append({"Type": "Paragraph", "Value": text})

            # EMAILS
            if "Emails" in options:
                emails = re.findall(
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    html
                )
                for email in list(set(emails))[:max_items]:
                    data.append({"Type": "Email", "Value": email})

            df = pd.DataFrame(data)

            if not df.empty:
                st.success("✅ Scraping Completed")

                col1, col2 = st.columns(2)

                with col1:
                    st.dataframe(df, use_container_width=True)

                with col2:
                    st.write("Summary:")
                    st.write(df["Type"].value_counts())

                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "⬇️ Download CSV",
                    csv,
                    "scraped_data.csv",
                    "text/csv"
                )

            else:
                st.warning("No data found")

        except Exception as e:
            st.error(f"Error: {str(e)}")
