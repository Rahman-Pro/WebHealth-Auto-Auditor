"""
Web Health & Security Audit Suite
Tests: HTTPS, SEO, Responsive Design, Performance, Broken Links
"""

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

TARGET_URL = "https://www.wikipedia.org/"
MAX_LOAD_TIME_SECONDS = 3.0
LINK_SCAN_LIMIT = 10


@pytest.fixture(scope="module")
def driver():
    """Headless Chrome driver, CI/CD compatible."""
    options = Options()
    for arg in [
        "--headless", "--window-size=1920,1080",
        "--disable-gpu", "--no-sandbox",
    ]:
        options.add_argument(arg)

    drv = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    drv.get(TARGET_URL)
    yield drv
    drv.quit()


class TestWebHealthAndSecurity:

    def test_ssl_security(self, driver):
        """Verify HTTPS."""
        assert driver.current_url.startswith("https://"), (
            f"Not HTTPS: {driver.current_url}"
        )

    @pytest.mark.xfail(reason="Wikipedia homepage omits meta description")
    def test_seo_meta_tags(self, driver):
        """Validate title and meta description."""
        assert driver.title, "Missing page title"
        desc = driver.find_elements(By.XPATH, "//meta[@name='description']")
        assert len(desc) > 0, "Missing meta description"

    def test_mobile_responsive_viewport(self, driver):
        """Check viewport tag and no horizontal overflow at mobile width."""
        tags = driver.find_elements(By.XPATH, "//meta[@name='viewport']")
        assert len(tags) > 0, "No viewport meta tag"

        original = driver.get_window_size()
        try:
            driver.set_window_size(375, 812)
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script(
                    "return document.readyState"
                ) == "complete"
            )
            sw = driver.execute_script(
                "return document.documentElement.scrollWidth"
            )
            cw = driver.execute_script(
                "return document.documentElement.clientWidth"
            )
            assert sw <= cw, "Horizontal scroll on mobile"
        finally:
            driver.set_window_size(original["width"], original["height"])

    def test_page_load_performance(self, driver):
        """Load time via Navigation Timing Level 2."""
        load_ms = driver.execute_script("""
            const [e] = performance.getEntriesByType('navigation');
            return e ? e.loadEventEnd : null;
        """)
        assert load_ms, "Navigation Timing API unavailable"
        load_s = load_ms / 1000.0
        assert load_s < MAX_LOAD_TIME_SECONDS, (
            f"Slow load: {load_s:.2f}s"
        )

    def test_broken_links(self, driver):
        """Scan first N links for 4xx/5xx responses."""
        hrefs = [
            a.get_attribute("href")
            for a in driver.find_elements(By.TAG_NAME, "a")[:LINK_SCAN_LIMIT]
            if a.get_attribute("href")
            and a.get_attribute("href").startswith("http")
        ]
        broken = []
        
        # Disguise the automated request as a standard Chrome browser to prevent 403 Forbidden blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        for url in hrefs:
            try:
                # Add headers to the request
                r = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                
                # If a site strictly blocks HEAD requests, fall back to a standard GET request
                if r.status_code == 405 or r.status_code == 403:
                    r = requests.get(url, headers=headers, timeout=5, stream=True)
                    
                if r.status_code >= 400:
                    broken.append(f"{url} → {r.status_code}")
            except requests.RequestException as exc:
                broken.append(f"{url} → {exc}")
                
        assert not broken, f"Broken links: {broken}"