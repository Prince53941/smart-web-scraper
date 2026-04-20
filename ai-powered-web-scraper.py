import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import urljoin

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Web Scraper Dashboard", layout="wide")

# ---------- TITLE ----------
st.title("🌐 Web Scraper Dashboard")
st.markdown("Extract structured data from any website and download it as a sheet.")

# ---------- INPUT ----------
url = st.text_input("Enter Website URL")

options = st.multiselect(
    "Select what you want to extract:",
    ["Title", "Headings", "Links", "Images", "Paragraphs", "Emails"]
)

max_items = st.slider("Limit results per category", 5, 100, 20)

# ---------- SCRAPE BUTTON ----------
if st.button("🚀 Scrape Now"):
    if not url:
        st.warning("Please enter a URL")
    else:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            data = []

            # ---------- TITLE ----------
            if "Title" in options:
                title = soup.title.string.strip() if soup.title else "No title"
                data.append({"Type": "Title", "Value": title})

            # ---------- HEADINGS ----------
            if "Headings" in options:
                headings = soup.find_all(["h1", "h2", "h3"])
                for tag in headings[:max_items]:
                    text = tag.text.strip()
                    if text:
                        data.append({"Type": "Heading", "Value": text})

            # ---------- LINKS ----------
            if "Links" in options:
                links = soup.find_all("a")
                for link in links[:max_items]:
                    href = link.get("href")
                    if href:
                        full_url = urljoin(url, href)
                        data.append({"Type": "Link", "Value": full_url})

            # ---------- IMAGES ----------
            if "Images" in options:
                images = soup.find_all("img")
                for img in images[:max_items]:
                    src = img.get("src")
                    if src:
                        full_src = urljoin(url, src)
                        data.append({"Type": "Image", "Value": full_src})

            # ---------- PARAGRAPHS ----------
            if "Paragraphs" in options:
                paragraphs = soup.find_all("p")
                for p in paragraphs[:max_items]:
                    text = p.text.strip()
                    if text:
                        data.append({"Type": "Paragraph", "Value": text})

            # ---------- EMAILS ----------
            if "Emails" in options:
                emails = re.findall(
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    response.text
                )
                unique_emails = list(set(emails))[:max_items]

                for email in unique_emails:
                    data.append({"Type": "Email", "Value": email})

            # ---------- DATAFRAME ----------
            df = pd.DataFrame(data)

            if not df.empty:
                st.success("✅ Scraping Completed")

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Preview")
                    st.dataframe(df, use_container_width=True)

                with col2:
                    st.subheader("Summary")
                    st.write(df["Type"].value_counts())

                # ---------- DOWNLOAD ----------
                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "⬇️ Download CSV",
                    csv,
                    "scraped_data.csv",
                    "text/csv"
                )

            else:
                st.warning("No data found for selected options.")

        except Exception as e:
            st.error(f"Error: {str(e)}")
