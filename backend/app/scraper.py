import asyncio
import base64
import os
import aiohttp
import random
import time
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
import logging
from dotenv import load_dotenv
import os.path

logger = logging.getLogger(__name__)

class WebsiteScraper:
    def __init__(self):
        # Load environment variables more robustly
        load_dotenv()  # Current directory
        
        # Try backend directory specifically
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backend_env = os.path.join(script_dir, '..', '.env')
        if os.path.exists(backend_env):
            load_dotenv(backend_env, override=True)
        
        self.browserbase_api_key = os.getenv('BROWSERBASE_API_KEY')
        self.browserbase_project_id = os.getenv('BROWSERBASE_PROJECT_ID')
        self.use_cloud_browser = bool(self.browserbase_api_key)
        self.page = None
        self.browser = None
        
        # User agents for rotation to avoid detection
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
    
    async def scrape_website(self, url: str) -> dict:
        """
        Scrape website using cloud browsers with fallbacks for reliability.
        Primary: Browserbase (cloud)
        Fallback 1: Local Playwright with stealth
        Fallback 2: HTTP requests with parsing
        """
        
        # Validate URL
        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        methods = [
            self._scrape_with_browserbase,
            self._scrape_with_local_playwright,
            self._scrape_with_http_fallback
        ]
        
        last_error = None
        
        for i, method in enumerate(methods):
            try:
                logger.info(f"Attempting scraping method {i+1}: {method.__name__}")
                result = await method(url)
                if result:
                    logger.info(f"Successfully scraped {url} using {method.__name__}")
                    return result
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed for {url}: {str(e)}")
                last_error = e
                # Add delay between retries
                if i < len(methods) - 1:
                    await asyncio.sleep(2 ** i)  # Exponential backoff
        
        raise Exception(f"All scraping methods failed. Last error: {str(last_error)}")
    
    async def _scrape_with_browserbase(self, url: str) -> Optional[dict]:
        """
        Use Browserbase cloud browser service for reliable scraping.
        Handles IP rotation, proxy management, and anti-bot measures.
        """
        if not self.browserbase_api_key:
            logger.info("Browserbase API key not found, skipping cloud browser method")
            return None
        
        if not self.browserbase_project_id:
            logger.info("Browserbase project ID not found, skipping cloud browser method")
            return None
        
        if not self.browserbase_api_key.startswith('bb_'):
            logger.warning(f"Browserbase API key seems invalid (doesn't start with 'bb_'): {self.browserbase_api_key[:10]}...")
            return None
        
        try:
            logger.info(f"🚀 ATTEMPTING BROWSERBASE: Using API key: {self.browserbase_api_key[:15]}...")
            print(f"🔥 DEBUG: Creating Browserbase session with key: {self.browserbase_api_key[:15]}...")
            
            # Create a session with Browserbase - only include supported fields
            session_data = {
                "projectId": self.browserbase_project_id,  # Required project ID
                "keepAlive": False,
                "timeout": 300  # 5 minutes in seconds
            }
            
            async with aiohttp.ClientSession() as session:
                # Create Browserbase session
                logger.info("Creating Browserbase session...")
                async with session.post(
                    "https://api.browserbase.com/v1/sessions",
                    headers={
                        "x-bb-api-key": self.browserbase_api_key,
                        "Content-Type": "application/json"
                    },
                    json=session_data
                ) as response:
                    response_text = await response.text()
                    logger.info(f"Browserbase response status: {response.status}")
                    logger.info(f"Browserbase response: {response_text[:200]}...")
                    
                    if response.status == 429:
                        logger.warning(f"⚠️ Browserbase rate limit hit (concurrent sessions): {response_text}")
                        return None
                    elif response.status not in [200, 201]:
                        logger.error(f"Failed to create Browserbase session: {response.status} - {response_text}")
                        return None
                    
                    session_info = await response.json()
                    session_id = session_info.get("id")
                    ws_url = session_info.get("connectUrl")
                    
                    logger.info(f"Browserbase session created: {session_id}")
                    logger.info(f"WebSocket URL: {ws_url}")
                
                if not ws_url:
                    logger.error("No WebSocket URL returned from Browserbase")
                    return None
                
                # Connect to the cloud browser via WebSocket
                logger.info("Connecting to Browserbase browser...")
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(ws_url)
                    context = browser.contexts[0] if browser.contexts else await browser.new_context()
                    page = await context.new_page()
                    
                    try:
                        logger.info(f"Navigating to {url}...")
                        # Navigate with advanced options
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(2000)  # Allow dynamic content to load
                        
                        # Take screenshot
                        screenshot = await page.screenshot(full_page=True, type="png")
                        screenshot_base64 = base64.b64encode(screenshot).decode("utf-8")
                        title = await page.title()
                        
                        logger.info(f"Successfully loaded page: {title}")
                        
                        # Extract comprehensive page data
                        page_data = await self._extract_page_data(page)
                        
                        logger.info(f"Extracted {page_data.get('articles_found', 0)} articles using Browserbase")
                        
                        return {
                            "url": url,
                            "title": title,
                            "screenshot": screenshot_base64,
                            "data": page_data,
                            "method": "browserbase"
                        }
                    
                    finally:
                        await page.close()
                        await browser.close()
                        
                        # Clean up Browserbase session
                        try:
                            async with session.delete(
                                f"https://api.browserbase.com/v1/sessions/{session_id}",
                                headers={"x-bb-api-key": self.browserbase_api_key}
                            ) as del_response:
                                if del_response.status == 200:
                                    logger.info(f"✅ Successfully cleaned up Browserbase session: {session_id}")
                                else:
                                    logger.warning(f"⚠️ Session cleanup returned status: {del_response.status}")
                        except Exception as cleanup_error:
                            logger.warning(f"⚠️ Failed to cleanup Browserbase session: {cleanup_error}")
        
        except Exception as e:
            logger.error(f"Browserbase scraping failed: {str(e)}")
            import traceback
            logger.error(f"Browserbase error traceback: {traceback.format_exc()}")
            return None
    
    async def _scrape_with_local_playwright(self, url: str) -> Optional[dict]:
        """
        Fallback to local Playwright with stealth mode and anti-detection measures.
        """
        try:
            async with async_playwright() as p:
                # Launch with stealth options
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ]
                )
                
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=random.choice(self.user_agents),
                    java_script_enabled=True,
                    accept_downloads=False,
                    ignore_https_errors=True
                )
                
                page = await context.new_page()
                
                # Set extra headers to appear more human-like
                await page.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                })
                
                try:
                    # Navigate with retries
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=45000)
                            break
                        except Exception as nav_error:
                            if attempt == max_retries - 1:
                                raise nav_error
                            await asyncio.sleep(2 ** attempt)
                    
                    # Wait for content to load
                    await page.wait_for_timeout(3000)
                    
                    # Take screenshot
                    screenshot = await page.screenshot(full_page=True, type="png")
                    screenshot_base64 = base64.b64encode(screenshot).decode("utf-8")
                    title = await page.title()
                    
                    # Extract page data
                    page_data = await self._extract_page_data(page)
                    
                    return {
                        "url": url,
                        "title": title,
                        "screenshot": screenshot_base64,
                        "data": page_data,
                        "method": "local_playwright"
                    }
                
                finally:
                    await page.close()
                    await context.close()
                    await browser.close()
        
        except Exception as e:
            logger.error(f"Local Playwright scraping failed: {str(e)}")
            return None
    
    async def _scrape_with_http_fallback(self, url: str) -> Optional[dict]:
        """
        Final fallback using HTTP requests with HTML parsing.
        Limited functionality but works when browsers are blocked.
        """
        try:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"HTTP request failed with status: {response.status}")
                        return None
                    
                    html_content = await response.text()
                    
                    # Basic HTML parsing without JavaScript execution
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Extract basic information
                    title = soup.find('title')
                    title_text = title.get_text().strip() if title else "Unknown Title"
                    
                    # Extract all text content for comprehensive coverage
                    text_content = {
                        'allText': [],
                        'buttonTexts': [],
                        'navigationText': [],
                        'productContent': [],
                        'heroContent': [],
                        'sectionContent': [],
                        'footerContent': []
                    }
                    
                    # Extract button and CTA text
                    for button in soup.find_all(['button', 'input']):
                        btn_text = ''
                        if button.name == 'input' and button.get('type') in ['button', 'submit']:
                            btn_text = button.get('value', '').strip()
                        else:
                            btn_text = button.get_text().strip()
                        
                        if btn_text:
                            text_content['buttonTexts'].append({
                                'text': btn_text,
                                'type': button.name,
                                'className': button.get('class', [''])[0] if button.get('class') else ''
                            })
                    
                    # Extract CTA links
                    for a in soup.find_all('a'):
                        link_text = a.get_text().strip().lower()
                        if any(keyword in link_text for keyword in ['learn more', 'buy', 'shop', 'get started', 'try', 'download', 'explore', 'discover', 'view', 'watch', 'order']):
                            text_content['buttonTexts'].append({
                                'text': a.get_text().strip(),
                                'type': 'a',
                                'className': a.get('class', [''])[0] if a.get('class') else '',
                                'href': a.get('href', '')
                            })
                    
                    # Extract navigation text
                    nav_elements = soup.find_all(['nav', 'header']) + soup.find_all(class_=['nav', 'navbar', 'navigation', 'menu'])
                    for nav in nav_elements:
                        for a in nav.find_all('a'):
                            nav_text = a.get_text().strip()
                            if nav_text:
                                text_content['navigationText'].append({
                                    'text': nav_text,
                                    'href': a.get('href', ''),
                                    'className': a.get('class', [''])[0] if a.get('class') else ''
                                })
                    
                    # Extract product content
                    product_selectors = soup.find_all(class_=lambda x: x and any(term in x.lower() for term in ['product', 'item', 'card']))
                    for product in product_selectors:
                        title_elem = product.find(['h1', 'h2', 'h3']) or product.find(class_=lambda x: x and any(term in x.lower() for term in ['title', 'name']))
                        desc_elem = product.find('p') or product.find(class_=lambda x: x and any(term in x.lower() for term in ['description', 'desc', 'summary']))
                        price_elem = product.find(class_=lambda x: x and any(term in x.lower() for term in ['price', 'cost']))
                        
                        if title_elem or desc_elem:
                            product_data = {
                                'title': title_elem.get_text().strip() if title_elem else '',
                                'description': desc_elem.get_text().strip() if desc_elem else '',
                                'price': price_elem.get_text().strip() if price_elem else '',
                                'buttonText': [btn.get_text().strip() for btn in product.find_all(['button', 'a']) if btn.get_text().strip()],
                                'className': product.get('class', [''])[0] if product.get('class') else ''
                            }
                            if product_data['title'] or product_data['description']:
                                text_content['productContent'].append(product_data)
                    
                    # Extract hero/banner content
                    hero_selectors = soup.find_all(class_=lambda x: x and any(term in x.lower() for term in ['hero', 'banner', 'jumbotron']))
                    for hero in hero_selectors:
                        title_elem = hero.find(['h1', 'h2']) or hero.find(class_=lambda x: x and any(term in x.lower() for term in ['title', 'headline']))
                        subtitle_elem = hero.find(['h3', 'h4', 'p']) or hero.find(class_=lambda x: x and any(term in x.lower() for term in ['subtitle', 'subheading']))
                        
                        if title_elem or subtitle_elem:
                            hero_data = {
                                'title': title_elem.get_text().strip() if title_elem else '',
                                'subtitle': subtitle_elem.get_text().strip() if subtitle_elem else '',
                                'ctaText': [btn.get_text().strip() for btn in hero.find_all(['button', 'a']) if btn.get_text().strip()],
                                'className': hero.get('class', [''])[0] if hero.get('class') else ''
                            }
                            if hero_data['title'] or hero_data['subtitle']:
                                text_content['heroContent'].append(hero_data)
                    
                    # Extract section content
                    sections = soup.find_all(['section', 'article']) + soup.find_all(class_=lambda x: x and 'section' in x.lower())
                    for section in sections:
                        heading_elem = section.find(['h1', 'h2', 'h3']) or section.find(class_=lambda x: x and any(term in x.lower() for term in ['title', 'heading']))
                        content_elem = section.find('p') or section.find(class_=lambda x: x and any(term in x.lower() for term in ['description', 'text', 'content']))
                        
                        if heading_elem or content_elem:
                            section_data = {
                                'heading': heading_elem.get_text().strip() if heading_elem else '',
                                'content': content_elem.get_text().strip()[:200] if content_elem else '',
                                'className': section.get('class', [''])[0] if section.get('class') else ''
                            }
                            if section_data['heading'] or section_data['content']:
                                text_content['sectionContent'].append(section_data)
                    
                    # Extract footer content
                    footer_elements = soup.find_all('footer') + soup.find_all(class_=['footer'])
                    for footer in footer_elements:
                        footer_data = {
                            'links': [a.get_text().strip() for a in footer.find_all('a') if a.get_text().strip()],
                            'text': [el.get_text().strip() for el in footer.find_all(['p', 'span', 'div']) if el.get_text().strip() and len(el.get_text().strip()) < 100],
                            'className': footer.get('class', [''])[0] if footer.get('class') else ''
                        }
                        if footer_data['links'] or footer_data['text']:
                            text_content['footerContent'].append(footer_data)
                    
                    # Extract all visible text elements
                    for tag in ['p', 'span', 'div', 'li', 'a']:
                        for elem in soup.find_all(tag):
                            elem_text = elem.get_text().strip()
                            if elem_text and len(elem_text) < 500 and len(elem_text) > 0:
                                text_content['allText'].append({
                                    'tagName': tag,
                                    'text': elem_text,
                                    'className': elem.get('class', [''])[0] if elem.get('class') else '',
                                    'id': elem.get('id', '')
                                })

                    # Basic article extraction for Hacker News
                    articles = []
                    for tr in soup.find_all('tr', class_='athing'):
                        title_link = tr.find('a', class_='storylink') or tr.find('a', class_='titleline')
                        if title_link:
                            href = title_link.get('href', '')
                            if href.startswith('/'):
                                href = urljoin(url, href)
                            
                            articles.append({
                                'index': len(articles) + 1,
                                'title': title_link.get_text().strip(),
                                'href': href,
                                'score': '',
                                'author': '',
                                'time': '',
                                'comments': '',
                                'className': tr.get('class', [''])[0] if tr.get('class') else '',
                                'id': tr.get('id', '')
                            })
                    
                    return {
                        "url": url,
                        "title": title_text,
                        "screenshot": "",  # No screenshot available
                        "data": {
                            'html': str(soup),
                            'headings': headings,
                            'links': [],
                            'articles': articles,
                            'genericArticles': [],
                            'navigation': {'headerLinks': [], 'sidebarLinks': [], 'mainContentLinks': []},
                            'layout': {'hasTopNav': False, 'hasSidebar': False, 'isResponsive': False},
                            'colors': [],
                            'viewport': {'width': 1920, 'height': 1080},
                            'textContent': text_content
                        },
                        "method": "http_fallback"
                    }
        
        except Exception as e:
            logger.error(f"HTTP fallback scraping failed: {str(e)}")
            return None
    
    def _extract_basic_html_data(self, soup, url: str) -> dict:
        """Extract basic data from BeautifulSoup object"""
        try:
            # Extract links
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = urljoin(url, href)
                links.append({
                    'text': a.get_text().strip(),
                    'href': href,
                    'className': a.get('class', [''])[0] if a.get('class') else ''
                })
            
            # Extract headings
            headings = []
            for i in range(1, 7):
                for h in soup.find_all(f'h{i}'):
                    headings.append({
                        'level': i,
                        'text': h.get_text().strip(),
                        'className': h.get('class', [''])[0] if h.get('class') else ''
                    })
            
            # Extract all text content for comprehensive coverage
            text_content = {
                'allText': [],
                'buttonTexts': [],
                'navigationText': [],
                'productContent': [],
                'heroContent': [],
                'sectionContent': [],
                'footerContent': []
            }
            
            # Extract button and CTA text
            for button in soup.find_all(['button', 'input']):
                btn_text = ''
                if button.name == 'input' and button.get('type') in ['button', 'submit']:
                    btn_text = button.get('value', '').strip()
                else:
                    btn_text = button.get_text().strip()
                
                if btn_text:
                    text_content['buttonTexts'].append({
                        'text': btn_text,
                        'type': button.name,
                        'className': button.get('class', [''])[0] if button.get('class') else ''
                    })
            
            # Extract CTA links
            for a in soup.find_all('a'):
                link_text = a.get_text().strip().lower()
                if any(keyword in link_text for keyword in ['learn more', 'buy', 'shop', 'get started', 'try', 'download', 'explore', 'discover', 'view', 'watch', 'order']):
                    text_content['buttonTexts'].append({
                        'text': a.get_text().strip(),
                        'type': 'a',
                        'className': a.get('class', [''])[0] if a.get('class') else '',
                        'href': a.get('href', '')
                    })
            
            # Extract navigation text
            nav_elements = soup.find_all(['nav', 'header']) + soup.find_all(class_=['nav', 'navbar', 'navigation', 'menu'])
            for nav in nav_elements:
                for a in nav.find_all('a'):
                    nav_text = a.get_text().strip()
                    if nav_text:
                        text_content['navigationText'].append({
                            'text': nav_text,
                            'href': a.get('href', ''),
                            'className': a.get('class', [''])[0] if a.get('class') else ''
                        })
            
            # Extract product content
            product_selectors = soup.find_all(class_=lambda x: x and any(term in x.lower() for term in ['product', 'item', 'card']))
            for product in product_selectors:
                title_elem = product.find(['h1', 'h2', 'h3']) or product.find(class_=lambda x: x and any(term in x.lower() for term in ['title', 'name']))
                desc_elem = product.find('p') or product.find(class_=lambda x: x and any(term in x.lower() for term in ['description', 'desc', 'summary']))
                price_elem = product.find(class_=lambda x: x and any(term in x.lower() for term in ['price', 'cost']))
                
                if title_elem or desc_elem:
                    product_data = {
                        'title': title_elem.get_text().strip() if title_elem else '',
                        'description': desc_elem.get_text().strip() if desc_elem else '',
                        'price': price_elem.get_text().strip() if price_elem else '',
                        'buttonText': [btn.get_text().strip() for btn in product.find_all(['button', 'a']) if btn.get_text().strip()],
                        'className': product.get('class', [''])[0] if product.get('class') else ''
                    }
                    if product_data['title'] or product_data['description']:
                        text_content['productContent'].append(product_data)
            
            # Extract hero/banner content
            hero_selectors = soup.find_all(class_=lambda x: x and any(term in x.lower() for term in ['hero', 'banner', 'jumbotron']))
            for hero in hero_selectors:
                title_elem = hero.find(['h1', 'h2']) or hero.find(class_=lambda x: x and any(term in x.lower() for term in ['title', 'headline']))
                subtitle_elem = hero.find(['h3', 'h4', 'p']) or hero.find(class_=lambda x: x and any(term in x.lower() for term in ['subtitle', 'subheading']))
                
                if title_elem or subtitle_elem:
                    hero_data = {
                        'title': title_elem.get_text().strip() if title_elem else '',
                        'subtitle': subtitle_elem.get_text().strip() if subtitle_elem else '',
                        'ctaText': [btn.get_text().strip() for btn in hero.find_all(['button', 'a']) if btn.get_text().strip()],
                        'className': hero.get('class', [''])[0] if hero.get('class') else ''
                    }
                    if hero_data['title'] or hero_data['subtitle']:
                        text_content['heroContent'].append(hero_data)
            
            # Extract section content
            sections = soup.find_all(['section', 'article']) + soup.find_all(class_=lambda x: x and 'section' in x.lower())
            for section in sections:
                heading_elem = section.find(['h1', 'h2', 'h3']) or section.find(class_=lambda x: x and any(term in x.lower() for term in ['title', 'heading']))
                content_elem = section.find('p') or section.find(class_=lambda x: x and any(term in x.lower() for term in ['description', 'text', 'content']))
                
                if heading_elem or content_elem:
                    section_data = {
                        'heading': heading_elem.get_text().strip() if heading_elem else '',
                        'content': content_elem.get_text().strip()[:200] if content_elem else '',
                        'className': section.get('class', [''])[0] if section.get('class') else ''
                    }
                    if section_data['heading'] or section_data['content']:
                        text_content['sectionContent'].append(section_data)
            
            # Extract footer content
            footer_elements = soup.find_all('footer') + soup.find_all(class_=['footer'])
            for footer in footer_elements:
                footer_data = {
                    'links': [a.get_text().strip() for a in footer.find_all('a') if a.get_text().strip()],
                    'text': [el.get_text().strip() for el in footer.find_all(['p', 'span', 'div']) if el.get_text().strip() and len(el.get_text().strip()) < 100],
                    'className': footer.get('class', [''])[0] if footer.get('class') else ''
                }
                if footer_data['links'] or footer_data['text']:
                    text_content['footerContent'].append(footer_data)
            
            # Extract all visible text elements
            for tag in ['p', 'span', 'div', 'li', 'a']:
                for elem in soup.find_all(tag):
                    elem_text = elem.get_text().strip()
                    if elem_text and len(elem_text) < 500 and len(elem_text) > 0:
                        text_content['allText'].append({
                            'tagName': tag,
                            'text': elem_text,
                            'className': elem.get('class', [''])[0] if elem.get('class') else '',
                            'id': elem.get('id', '')
                        })

            # Basic article extraction for Hacker News
            articles = []
            for tr in soup.find_all('tr', class_='athing'):
                title_link = tr.find('a', class_='storylink') or tr.find('a', class_='titleline')
                if title_link:
                    href = title_link.get('href', '')
                    if href.startswith('/'):
                        href = urljoin(url, href)
                    
                    articles.append({
                        'index': len(articles) + 1,
                        'title': title_link.get_text().strip(),
                        'href': href,
                        'score': '',
                        'author': '',
                        'time': '',
                        'comments': '',
                        'className': tr.get('class', [''])[0] if tr.get('class') else '',
                        'id': tr.get('id', '')
                    })
            
            # Extract comprehensive text content for fallback method
            text_content = {
                'buttonTexts': [],
                'navigationText': [],
                'productContent': [],
                'heroContent': [],
                'sectionContent': [],
                'footerContent': [],
                'allText': []
            }
            
            # Extract button and CTA text
            for button in soup.find_all(['button', 'input']):
                btn_text = ''
                if button.name == 'input' and button.get('type') in ['button', 'submit']:
                    btn_text = button.get('value', '').strip()
                else:
                    btn_text = button.get_text().strip()
                
                if btn_text:
                    text_content['buttonTexts'].append({
                        'text': btn_text,
                        'type': button.name,
                        'className': button.get('class', [''])[0] if button.get('class') else ''
                    })
            
            # Extract CTA links that look like buttons
            for a in soup.find_all('a'):
                link_text = a.get_text().strip().lower()
                if any(keyword in link_text for keyword in ['learn more', 'buy', 'shop', 'get started', 'try', 'download', 'explore', 'discover', 'view', 'watch', 'order']):
                    text_content['buttonTexts'].append({
                        'text': a.get_text().strip(),
                        'type': 'a',
                        'className': a.get('class', [''])[0] if a.get('class') else '',
                        'href': a.get('href', '')
                    })
            
            # Extract navigation text
            nav_elements = soup.find_all(['nav', 'header']) + soup.find_all(class_=['nav', 'navbar', 'navigation', 'menu'])
            for nav in nav_elements:
                for a in nav.find_all('a'):
                    nav_text = a.get_text().strip()
                    if nav_text:
                        text_content['navigationText'].append({
                            'text': nav_text,
                            'href': a.get('href', ''),
                            'className': a.get('class', [''])[0] if a.get('class') else ''
                        })
            
            return {
                'html': str(soup),
                'headings': headings,
                'links': links,
                'articles': articles,
                'genericArticles': [],
                'navigation': {'headerLinks': [], 'sidebarLinks': [], 'mainContentLinks': []},
                'layout': {'hasTopNav': False, 'hasSidebar': False, 'isResponsive': False},
                'colors': [],
                'viewport': {'width': 1920, 'height': 1080},
                'textContent': text_content
            }
        
        except Exception as e:
            logger.error(f"Failed to extract basic HTML data: {str(e)}")
            return {'html': '', 'headings': [], 'links': [], 'articles': []}
    
    async def _extract_page_data(self, page) -> dict:
        """Extract comprehensive page data using JavaScript execution"""
        try:
            return await page.evaluate("""
                () => {
                    const data = {
                        html: document.documentElement.outerHTML,
                        headings: Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map(h => ({ 
                            level: parseInt(h.tagName.substr(1)), 
                            text: h.textContent.trim(),
                            className: h.className || ''
                        })),
                        links: Array.from(document.querySelectorAll("a")).map(a => ({ 
                            text: a.textContent.trim(), 
                            href: a.href,
                            className: a.className || ''
                        })),
                        
                        // Enhanced content extraction for Hacker News
                        articles: Array.from(document.querySelectorAll('tr.athing')).map((article, index) => {
                            const titleEl = article.querySelector('a.storylink') || article.querySelector('.titleline a');
                            const nextRow = article.nextElementSibling;
                            
                            let scoreEl, authorEl, timeEl, commentsEl;
                            if (nextRow && nextRow.querySelector('.subtext')) {
                                scoreEl = nextRow.querySelector('.score');
                                authorEl = nextRow.querySelector('.hnuser') || nextRow.querySelector('a[href*="user"]');
                                timeEl = nextRow.querySelector('.age') || nextRow.querySelector('a[href*="item"]');
                                commentsEl = nextRow.querySelector('a[href*="item"]:last-child');
                            }
                            
                            const siteEl = article.querySelector('.sitestr') || article.querySelector('span.sitebit');
                            
                            let absoluteHref = '';
                            if (titleEl && titleEl.href) {
                                absoluteHref = titleEl.href.startsWith('http') 
                                    ? titleEl.href 
                                    : new URL(titleEl.href, window.location.href).href;
                            }
                            
                            return {
                                index: index + 1,
                                title: titleEl ? titleEl.textContent.trim() : '',
                                href: absoluteHref,
                                score: scoreEl ? scoreEl.textContent.trim() : '',
                                author: authorEl ? authorEl.textContent.trim() : '',
                                time: timeEl ? timeEl.textContent.trim() : '',
                                comments: commentsEl ? commentsEl.textContent.trim() : '',
                                source: siteEl ? siteEl.textContent.trim() : '',
                                className: article.className || '',
                                id: article.id || ''
                            };
                        }).filter(item => item.title && item.title.length > 0),
                        
                        // Generic articles for other sites
                        genericArticles: Array.from(document.querySelectorAll('.story, .item, article, .post, .entry, .news-item, [class*="story"], [class*="item"], [class*="post"]')).map((article, index) => {
                            const titleEl = article.querySelector('h1, h2, h3, .title, a') || article.querySelector('a');
                            
                            let absoluteHref = '';
                            if (titleEl && titleEl.href) {
                                absoluteHref = titleEl.href.startsWith('http') 
                                    ? titleEl.href 
                                    : new URL(titleEl.href, window.location.href).href;
                            }
                            
                            return {
                                index: index + 1,
                                title: titleEl ? titleEl.textContent.trim() : '',
                                href: absoluteHref,
                                text: article.textContent.trim().substring(0, 200)
                            };
                        }).filter(item => item.title && item.title.length > 0),
                        
                        navigation: {
                            headerLinks: Array.from(document.querySelectorAll('header a, .header a, nav a, .nav a, .navbar a')).map(a => ({
                                text: a.textContent.trim(),
                                href: a.href,
                                absoluteHref: new URL(a.href, window.location.href).href,
                                isExternal: a.href.startsWith('http') && !a.href.includes(window.location.hostname),
                                className: a.className || '',
                                style: {
                                    color: window.getComputedStyle(a).color,
                                    fontSize: window.getComputedStyle(a).fontSize,
                                    fontWeight: window.getComputedStyle(a).fontWeight,
                                    textDecoration: window.getComputedStyle(a).textDecoration,
                                    padding: window.getComputedStyle(a).padding,
                                    margin: window.getComputedStyle(a).margin
                                },
                                parentElement: a.parentElement?.tagName.toLowerCase() || '',
                                position: a.getBoundingClientRect()
                            })),
                            
                            // Enhanced navigation structure analysis
                            headerStructure: {
                                headerElement: document.querySelector('header, .header, nav, .nav, .navbar')?.tagName.toLowerCase() || '',
                                headerClass: document.querySelector('header, .header, nav, .nav, .navbar')?.className || '',
                                headerStyle: document.querySelector('header, .header, nav, .nav, .navbar') ? {
                                    backgroundColor: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).backgroundColor,
                                    height: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).height,
                                    padding: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).padding,
                                    display: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).display,
                                    justifyContent: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).justifyContent,
                                    alignItems: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).alignItems,
                                    flexDirection: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar')).flexDirection
                                } : {},
                                logoPosition: document.querySelector('header img, .header img, nav img, .logo') ? 'left' : 'none',
                                menuPosition: 'right',
                                isSticky: window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar') || document.body).position === 'fixed' || 
                                         window.getComputedStyle(document.querySelector('header, .header, nav, .nav, .navbar') || document.body).position === 'sticky'
                            },
                            sidebarLinks: Array.from(document.querySelectorAll('aside a, .sidebar a, .nav-sidebar a, [class*="sidebar"] a')).map(a => ({
                                text: a.textContent.trim(),
                                href: a.href,
                                absoluteHref: new URL(a.href, window.location.href).href,
                                isExternal: a.href.startsWith('http') && !a.href.includes(window.location.hostname),
                                className: a.className || ''
                            })),
                            mainContentLinks: Array.from(document.querySelectorAll('main a, .main a, .content a, article a')).map(a => ({
                                text: a.textContent.trim(),
                                href: a.href,
                                absoluteHref: new URL(a.href, window.location.href).href,
                                isExternal: a.href.startsWith('http') && !a.href.includes(window.location.hostname),
                                className: a.className || ''
                            }))
                        },
                        
                        layout: {
                            hasFixedHeader: !!document.querySelector('header[style*="fixed"], .header[style*="fixed"], nav[style*="fixed"]'),
                            hasSidebar: !!document.querySelector('aside, .sidebar, .nav-sidebar, [class*="sidebar"]'),
                            isResponsive: !!document.querySelector('meta[name="viewport"]'),
                            gridContainers: Array.from(document.querySelectorAll('*')).filter(el => 
                                window.getComputedStyle(el).display === 'grid'
                            ).length,
                            flexContainers: Array.from(document.querySelectorAll('*')).filter(el => 
                                window.getComputedStyle(el).display === 'flex'
                            ).length,
                            hasTopNav: !!document.querySelector('header, .header, .top-nav, .navbar'),
                            hasMainContent: !!document.querySelector('main, .main, .content'),
                            hasSectionDividers: !!document.querySelector('hr, .divider, .separator, [class*="divider"], [class*="separator"]'),
                            hasProductCards: !!document.querySelector('.product, .card, .item-card, [class*="product"], [class*="card"]'),
                            hasHeroBanner: !!document.querySelector('.hero, .banner, .jumbotron, [class*="hero"], [class*="banner"]')
                        },
                        
                        // Extract product cards and featured items
                        productCards: Array.from(document.querySelectorAll('.product, .card, .item-card, [class*="product"], [class*="card"], .tile, [class*="tile"]')).map(card => ({
                            title: (card.querySelector('h1, h2, h3, h4, .title, .name, [class*="title"], [class*="name"]') || {}).textContent?.trim() || '',
                            description: (card.querySelector('p, .description, .desc, [class*="description"], [class*="desc"]') || {}).textContent?.trim() || '',
                            image: (card.querySelector('img') || {}).src || '',
                            link: (card.querySelector('a') || {}).href || '',
                            className: card.className || '',
                            price: (card.querySelector('.price, [class*="price"]') || {}).textContent?.trim() || ''
                        })).filter(item => item.title || item.image),
                        
                        // Extract section dividers and separators
                        dividers: Array.from(document.querySelectorAll('hr, .divider, .separator, [class*="divider"], [class*="separator"]')).map(div => ({
                            tagName: div.tagName.toLowerCase(),
                            className: div.className || '',
                            style: div.style.cssText || '',
                            computedStyle: {
                                borderTop: window.getComputedStyle(div).borderTop,
                                borderBottom: window.getComputedStyle(div).borderBottom,
                                backgroundColor: window.getComputedStyle(div).backgroundColor,
                                height: window.getComputedStyle(div).height,
                                margin: window.getComputedStyle(div).margin
                            }
                        })),
                        
                        // COMPREHENSIVE TEXT CONTENT EXTRACTION
                        textContent: {
                            // Extract all visible text elements with complete color information
                            allText: Array.from(document.querySelectorAll('p, span, div, li, h1, h2, h3, h4, h5, h6, a, button, .text, .content, .description, .title, .subtitle, .caption, .label, .price, .product-name, .product-title')).map(el => {
                                const computedStyle = window.getComputedStyle(el);
                                return {
                                    tagName: el.tagName.toLowerCase(),
                                    text: el.textContent?.trim() || '',
                                    className: el.className || '',
                                    id: el.id || '',
                                    context: el.closest('.product, .card, .hero, .banner, section, article, .content, nav, header, footer')?.className || '',
                                    // Complete font and color information
                                    styles: {
                                        fontFamily: computedStyle.fontFamily,
                                        fontSize: computedStyle.fontSize,
                                        fontWeight: computedStyle.fontWeight,
                                        letterSpacing: computedStyle.letterSpacing,
                                        lineHeight: computedStyle.lineHeight,
                                        textAlign: computedStyle.textAlign,
                                        textDecoration: computedStyle.textDecoration,
                                        // Color information
                                        color: computedStyle.color,
                                        backgroundColor: computedStyle.backgroundColor,
                                        // Parent background for context
                                        parentBackgroundColor: el.parentElement ? window.getComputedStyle(el.parentElement).backgroundColor : 'transparent',
                                        // Contrast context
                                        isOnDarkBackground: (() => {
                                            const bgColor = computedStyle.backgroundColor;
                                            const parentBg = el.parentElement ? window.getComputedStyle(el.parentElement).backgroundColor : 'transparent';
                                            const isColorDark = (color) => {
                                                if (!color || color === 'transparent' || color === 'rgba(0, 0, 0, 0)') return false;
                                                const rgb = color.match(/\\d+/g);
                                                if (!rgb) return false;
                                                const brightness = (parseInt(rgb[0]) * 299 + parseInt(rgb[1]) * 587 + parseInt(rgb[2]) * 114) / 1000;
                                                return brightness < 128;
                                            };
                                            return isColorDark(bgColor) || isColorDark(parentBg);
                                        })(),
                                        // Text role classification
                                        textRole: (() => {
                                            if (el.closest('nav, header, .navbar')) return 'navigation';
                                            if (el.closest('button, .btn')) return 'button';
                                            if (el.tagName.match(/H[1-6]/)) return 'heading';
                                            if (el.closest('.price, [class*="price"]')) return 'price';
                                            if (el.closest('.product, [class*="product"]')) return 'product';
                                            if (el.closest('footer')) return 'footer';
                                            return 'content';
                                        })(),
                                        // Semantic context
                                        semanticContext: (() => {
                                            const contexts = [];
                                            if (el.closest('.hero, .banner')) contexts.push('hero');
                                            if (el.closest('.product, .item')) contexts.push('product');
                                            if (el.closest('.cta, .call-to-action')) contexts.push('cta');
                                            if (el.closest('nav, header')) contexts.push('navigation');
                                            if (el.closest('footer')) contexts.push('footer');
                                            return contexts.join(',') || 'general';
                                        })()
                                    },
                                    position: el.getBoundingClientRect(),
                                    isVisible: computedStyle.display !== 'none' && computedStyle.visibility !== 'hidden' && computedStyle.opacity !== '0'
                                };
                            }).filter(item => item.text && item.text.length > 0 && item.text.length < 500 && item.isVisible),
                            
                            // Extract comprehensive color palette from the website
                            colorPalette: (() => {
                                const colors = new Set();
                                const elements = document.querySelectorAll('*');
                                elements.forEach(el => {
                                    const style = window.getComputedStyle(el);
                                    if (style.color && style.color !== 'rgba(0, 0, 0, 0)') colors.add(style.color);
                                    if (style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)') colors.add(style.backgroundColor);
                                    if (style.borderColor && style.borderColor !== 'rgba(0, 0, 0, 0)') colors.add(style.borderColor);
                                });
                                return Array.from(colors).slice(0, 50); // Limit to top 50 colors
                            })(),
                            
                            // Navigation-specific color extraction
                            navigationColors: Array.from(document.querySelectorAll('nav, header, .navbar, .navigation, .menu')).map(nav => {
                                const computedStyle = window.getComputedStyle(nav);
                                return {
                                    element: nav.tagName.toLowerCase(),
                                    className: nav.className || '',
                                    backgroundColor: computedStyle.backgroundColor,
                                    textColor: computedStyle.color,
                                    linkColors: Array.from(nav.querySelectorAll('a')).map(link => ({
                                        text: link.textContent?.trim() || '',
                                        color: window.getComputedStyle(link).color,
                                        hoverColor: link.getAttribute('data-hover-color') || 'inherit',
                                        className: link.className || ''
                                    })),
                                    borderColor: computedStyle.borderColor,
                                    boxShadow: computedStyle.boxShadow
                                };
                            }),
                            
                            // Button-specific color extraction
                            buttonColors: Array.from(document.querySelectorAll('button, .btn, .button, input[type="button"], input[type="submit"], a[class*="btn"]')).map(btn => {
                                const computedStyle = window.getComputedStyle(btn);
                                return {
                                    text: btn.textContent?.trim() || btn.value || '',
                                    type: btn.tagName.toLowerCase(),
                                    className: btn.className || '',
                                    colors: {
                                        textColor: computedStyle.color,
                                        backgroundColor: computedStyle.backgroundColor,
                                        borderColor: computedStyle.borderColor,
                                        hoverTextColor: btn.getAttribute('data-hover-text-color') || computedStyle.color,
                                        hoverBackgroundColor: btn.getAttribute('data-hover-bg-color') || computedStyle.backgroundColor
                                    },
                                    styles: {
                                        padding: computedStyle.padding,
                                        borderRadius: computedStyle.borderRadius,
                                        fontSize: computedStyle.fontSize,
                                        fontWeight: computedStyle.fontWeight
                                    },
                                    context: btn.closest('.product, .card, .hero, .banner, section, article, nav, header, footer')?.className || ''
                                };
                            }).filter(item => item.text),
                            
                            // Heading-specific color extraction
                            headingColors: Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(heading => {
                                const computedStyle = window.getComputedStyle(heading);
                                return {
                                    level: parseInt(heading.tagName.substring(1)),
                                    text: heading.textContent?.trim() || '',
                                    className: heading.className || '',
                                    colors: {
                                        textColor: computedStyle.color,
                                        backgroundColor: computedStyle.backgroundColor
                                    },
                                    styles: {
                                        fontSize: computedStyle.fontSize,
                                        fontWeight: computedStyle.fontWeight,
                                        lineHeight: computedStyle.lineHeight,
                                        marginTop: computedStyle.marginTop,
                                        marginBottom: computedStyle.marginBottom
                                    },
                                    context: heading.closest('.product, .card, .hero, .banner, section, article')?.className || ''
                                };
                            }).filter(item => item.text),
                            
                            // Product names and descriptions
                            productContent: Array.from(document.querySelectorAll('.product, .item, [class*="product"], [class*="item"]')).map(product => ({
                                title: product.querySelector('h1, h2, h3, .title, .name, .product-name, .product-title')?.textContent?.trim() || '',
                                description: product.querySelector('p, .description, .desc, .summary, .details')?.textContent?.trim() || '',
                                price: product.querySelector('.price, .cost, [class*="price"], [class*="cost"]')?.textContent?.trim() || '',
                                buttonText: Array.from(product.querySelectorAll('button, .btn, .button, a[class*="btn"]')).map(btn => btn.textContent?.trim()).filter(text => text),
                                className: product.className || '',
                                id: product.id || ''
                            })).filter(item => item.title || item.description),
                            
                            // Navigation and menu text
                            navigationText: Array.from(document.querySelectorAll('nav a, header a, .menu a, .navbar a, .navigation a')).map(link => ({
                                text: link.textContent?.trim() || '',
                                href: link.href || '',
                                className: link.className || '',
                                parentContext: link.closest('nav, header, .menu, .navbar')?.className || ''
                            })).filter(item => item.text),
                            
                            // Hero/banner text content
                            heroContent: Array.from(document.querySelectorAll('.hero, .banner, .jumbotron, [class*="hero"], [class*="banner"]')).map(hero => ({
                                title: hero.querySelector('h1, h2, .title, .headline')?.textContent?.trim() || '',
                                subtitle: hero.querySelector('h3, h4, .subtitle, .subheading, p')?.textContent?.trim() || '',
                                ctaText: Array.from(hero.querySelectorAll('button, .btn, .cta, a[class*="btn"]')).map(btn => btn.textContent?.trim()).filter(text => text),
                                className: hero.className || ''
                            })).filter(item => item.title || item.subtitle),
                            
                            // All button and CTA text
                            buttonTexts: Array.from(document.querySelectorAll('button, .btn, .button, .cta, input[type="button"], input[type="submit"], a[class*="btn"], a[class*="button"]')).map(btn => ({
                                text: btn.textContent?.trim() || btn.value || btn.alt || '',
                                type: btn.tagName.toLowerCase(),
                                className: btn.className || '',
                                href: btn.href || '',
                                context: btn.closest('.product, .card, .hero, section, article')?.className || ''
                            })).filter(item => item.text),
                            
                            // Section headings and content
                            sectionContent: Array.from(document.querySelectorAll('section, article, .section, .content-section')).map(section => ({
                                heading: section.querySelector('h1, h2, h3, .title, .heading')?.textContent?.trim() || '',
                                content: section.querySelector('p, .description, .text, .content')?.textContent?.trim().substring(0, 200) || '',
                                className: section.className || '',
                                id: section.id || ''
                            })).filter(item => item.heading || item.content),
                            
                            // Footer text
                            footerContent: Array.from(document.querySelectorAll('footer, .footer')).map(footer => ({
                                links: Array.from(footer.querySelectorAll('a')).map(link => link.textContent?.trim()).filter(text => text),
                                text: Array.from(footer.querySelectorAll('p, span, div')).map(el => el.textContent?.trim()).filter(text => text && text.length < 100),
                                className: footer.className || ''
                            })).filter(item => item.links.length > 0 || item.text.length > 0)
                        },
                        
                        // Extract images with their attributes
                        images: Array.from(document.querySelectorAll('img')).map(img => ({
                            src: img.src.startsWith('http') ? img.src : new URL(img.src, window.location.href).href,
                            alt: img.alt || '',
                            width: img.width || img.naturalWidth || '',
                            height: img.height || img.naturalHeight || '',
                            className: img.className || '',
                            id: img.id || '',
                            loading: img.loading || '',
                            srcset: img.srcset || '',
                            sizes: img.sizes || '',
                            title: img.title || '',
                            style: img.style.cssText || ''
                        })).filter(img => img.src && !img.src.startsWith('data:')),
                        
                        // Extract background images from CSS
                        backgroundImages: Array.from(document.querySelectorAll('*')).map(el => {
                            const style = window.getComputedStyle(el);
                            const bgImage = style.backgroundImage;
                            if (bgImage && bgImage !== 'none' && bgImage.includes('url(')) {
                                const match = bgImage.match(/url\\(["']?([^"']+)["']?\\)/);
                                const imageUrl = match ? match[1] : bgImage;
                                // Convert relative URLs to absolute
                                const absoluteUrl = imageUrl.startsWith('http') ? imageUrl : new URL(imageUrl, window.location.href).href;
                                return {
                                    element: el.tagName.toLowerCase(),
                                    className: el.className || '',
                                    id: el.id || '',
                                    backgroundImage: absoluteUrl,
                                    backgroundSize: style.backgroundSize,
                                    backgroundPosition: style.backgroundPosition,
                                    backgroundRepeat: style.backgroundRepeat
                                };
                            }
                            return null;
                        }).filter(item => item !== null),
                        
                        // Extract logo and brand images with enhanced Apple-specific detection
                        logoImages: Array.from(document.querySelectorAll('img[alt*="logo" i], img[class*="logo" i], img[id*="logo" i], .logo img, .brand img, header img, nav img, .globalnav img, img[src*="apple"], img[alt*="apple" i]')).map(img => ({
                            src: img.src.startsWith('http') ? img.src : new URL(img.src, window.location.href).href,
                            alt: img.alt || '',
                            className: img.className || '',
                            id: img.id || '',
                            width: img.width || img.naturalWidth || '',
                            height: img.height || img.naturalHeight || '',
                            parentElement: img.parentElement?.tagName.toLowerCase() || '',
                            parentClass: img.parentElement?.className || '',
                            // Enhanced Apple logo detection
                            isAppleLogo: img.alt.toLowerCase().includes('apple') || img.src.includes('apple') || img.className.includes('apple'),
                            hasValidSrc: img.src && !img.src.startsWith('data:') && img.src.length > 10,
                            naturalDimensions: {
                                width: img.naturalWidth || 0,
                                height: img.naturalHeight || 0
                            }
                        })).filter(logo => logo.hasValidSrc),
                        
                        // Extract fonts and typography information with Apple-specific detection
                        fonts: {
                            bodyFont: window.getComputedStyle(document.body).fontFamily,
                            headingFonts: Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                                tag: h.tagName.toLowerCase(),
                                fontFamily: window.getComputedStyle(h).fontFamily,
                                fontSize: window.getComputedStyle(h).fontSize,
                                fontWeight: window.getComputedStyle(h).fontWeight,
                                color: window.getComputedStyle(h).color,
                                letterSpacing: window.getComputedStyle(h).letterSpacing,
                                lineHeight: window.getComputedStyle(h).lineHeight,
                                textContent: h.textContent.trim().substring(0, 50)
                            })),
                            navigationFonts: Array.from(document.querySelectorAll('nav a, header a, .globalnav a')).map(a => ({
                                fontFamily: window.getComputedStyle(a).fontFamily,
                                fontSize: window.getComputedStyle(a).fontSize,
                                fontWeight: window.getComputedStyle(a).fontWeight,
                                color: window.getComputedStyle(a).color,
                                letterSpacing: window.getComputedStyle(a).letterSpacing,
                                lineHeight: window.getComputedStyle(a).lineHeight,
                                textContent: a.textContent.trim()
                            })),
                            primaryFonts: Array.from(new Set(
                                Array.from(document.querySelectorAll('*')).map(el => 
                                    window.getComputedStyle(el).fontFamily
                                ).filter(font => font && font !== 'serif' && font !== 'sans-serif')
                            )).slice(0, 10),
                            // Detect Apple system fonts
                            hasAppleFonts: Array.from(document.querySelectorAll('*')).some(el => {
                                const font = window.getComputedStyle(el).fontFamily.toLowerCase();
                                return font.includes('sf pro') || font.includes('-apple-system') || font.includes('helvetica neue');
                            })
                        },
                        
                        // Extract interactive buttons and CTAs with enhanced styling
                        buttons: Array.from(document.querySelectorAll('button, .btn, .button, input[type="button"], input[type="submit"], a[class*="btn"], a[class*="button"], .cta, [class*="cta"]')).map(btn => ({
                            tagName: btn.tagName.toLowerCase(),
                            text: btn.textContent?.trim() || btn.value || btn.alt || '',
                            className: btn.className || '',
                            id: btn.id || '',
                            href: btn.href || '',
                            type: btn.type || '',
                            ariaLabel: btn.getAttribute('aria-label') || '',
                            style: {
                                backgroundColor: window.getComputedStyle(btn).backgroundColor,
                                color: window.getComputedStyle(btn).color,
                                border: window.getComputedStyle(btn).border,
                                borderRadius: window.getComputedStyle(btn).borderRadius,
                                padding: window.getComputedStyle(btn).padding,
                                margin: window.getComputedStyle(btn).margin,
                                fontSize: window.getComputedStyle(btn).fontSize,
                                fontWeight: window.getComputedStyle(btn).fontWeight,
                                textTransform: window.getComputedStyle(btn).textTransform,
                                textDecoration: window.getComputedStyle(btn).textDecoration,
                                display: window.getComputedStyle(btn).display,
                                alignItems: window.getComputedStyle(btn).alignItems,
                                justifyContent: window.getComputedStyle(btn).justifyContent,
                                boxShadow: window.getComputedStyle(btn).boxShadow,
                                transition: window.getComputedStyle(btn).transition,
                                cursor: window.getComputedStyle(btn).cursor,
                                minWidth: window.getComputedStyle(btn).minWidth,
                                height: window.getComputedStyle(btn).height,
                                lineHeight: window.getComputedStyle(btn).lineHeight
                            },
                            boundingRect: btn.getBoundingClientRect(),
                            isClickable: btn.onclick !== null || btn.href || btn.type === 'button' || btn.type === 'submit',
                            parentContext: btn.closest('.card, .product, article, section, header, .hero, .banner')?.className || '',
                            isAppleStyle: btn.textContent?.trim().toLowerCase().includes('learn more') || 
                                         btn.textContent?.trim().toLowerCase().includes('buy') ||
                                         btn.className.includes('more') || btn.className.includes('cta')
                        })).filter(btn => btn.text || btn.href),
                        
                        // Extract call-to-action elements and links with Apple patterns
                        ctaElements: Array.from(document.querySelectorAll('a')).filter(a => {
                            const text = a.textContent?.trim().toLowerCase() || '';
                            return text.includes('learn more') || text.includes('buy') || text.includes('shop') || 
                                   text.includes('get started') || text.includes('try') || text.includes('download') ||
                                   text.includes('explore') || text.includes('discover') || text.includes('view') ||
                                   text.includes('watch') || text.includes('see') || text.includes('order');
                        }).map(cta => ({
                            text: cta.textContent?.trim() || '',
                            href: cta.href.startsWith('http') ? cta.href : new URL(cta.href, window.location.href).href,
                            className: cta.className || '',
                            id: cta.id || '',
                            ariaLabel: cta.getAttribute('aria-label') || '',
                            style: {
                                backgroundColor: window.getComputedStyle(cta).backgroundColor,
                                color: window.getComputedStyle(cta).color,
                                border: window.getComputedStyle(cta).border,
                                borderRadius: window.getComputedStyle(cta).borderRadius,
                                padding: window.getComputedStyle(cta).padding,
                                margin: window.getComputedStyle(cta).margin,
                                textDecoration: window.getComputedStyle(cta).textDecoration,
                                fontWeight: window.getComputedStyle(cta).fontWeight,
                                fontSize: window.getComputedStyle(cta).fontSize,
                                display: window.getComputedStyle(cta).display,
                                alignItems: window.getComputedStyle(cta).alignItems,
                                justifyContent: window.getComputedStyle(cta).justifyContent,
                                boxShadow: window.getComputedStyle(cta).boxShadow,
                                transition: window.getComputedStyle(cta).transition,
                                cursor: window.getComputedStyle(cta).cursor,
                                lineHeight: window.getComputedStyle(cta).lineHeight,
                                textTransform: window.getComputedStyle(cta).textTransform
                            },
                            boundingRect: cta.getBoundingClientRect(),
                            parentContext: cta.closest('.card, .product, article, section, header, .hero, .banner')?.className || '',
                            hasIcon: !!cta.querySelector('svg, i, .icon, [class*="icon"]'),
                            isAppleButton: cta.textContent?.trim().toLowerCase() === 'learn more >' || 
                                          cta.textContent?.trim().toLowerCase() === 'buy' ||
                                          cta.className.includes('more') || cta.className.includes('button')
                        })),

                        colors: Array.from(new Set(Array.from(document.querySelectorAll("*")).map(el => 
                            window.getComputedStyle(el).color
                        ).filter(c => c && c !== "rgba(0, 0, 0, 0)"))).slice(0, 20),
                        
                        viewport: {
                            width: window.innerWidth,
                            height: window.innerHeight,
                            documentHeight: document.documentElement.scrollHeight,
                            documentWidth: document.documentElement.scrollWidth
                        }
                    };
                    return data;
                }
            """)
        except Exception as e:
            logger.error(f"Failed to extract page data with JavaScript: {str(e)}")
            return {'html': '', 'headings': [], 'links': [], 'articles': []}
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
 