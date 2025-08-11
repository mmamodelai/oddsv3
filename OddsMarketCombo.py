import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import requests
import csv
import json
import re
import time
import os
import sys
from datetime import datetime
import platform
from urllib.parse import urljoin
try:
    import winreg  # type: ignore
except Exception:
    winreg = None

# Ensure UTF-8 stdout on Windows CI to avoid UnicodeEncodeError with emojis/tokens
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def odds_market_combo(debug_mode=False):
    """
    LulSec OddsMarketCombo - Clean UFC odds extraction
    Outputs: OddsMarketCombo.csv (overwrites each run)
    Outputs: OddsMarketCombo.json (overwrites each run)
    """
    print("🏴‍☠️ LulSec OddsMarketCombo - fightodds.io")
    print("=" * 50)
    print("🎯 EXTRACTING ALL UFC EVENTS TO OddsMarketCombo.csv & .json")
    print("=" * 50)
    if debug_mode:
        print("🔍 DEBUG MODE ENABLED - Enhanced logging active")
        print("=" * 50)
    
    # Chrome configuration will be created fresh for each retry attempt
    
    # Try to initialize Chrome with retry logic
    max_retries = 3
    driver = None
    
    for attempt in range(max_retries):
        try:
            print(f"   🔄 Chrome initialization attempt {attempt + 1}/{max_retries}")

            # Create fresh ChromeOptions for each attempt
            in_ci = os.getenv('GITHUB_ACTIONS', 'false').lower() == 'true'
            force_headless = os.getenv('HEADLESS', '0') == '1'
            fresh_options = uc.ChromeOptions()
            if in_ci or force_headless:
                try:
                    fresh_options.add_argument('--headless=new')
                except Exception:
                    fresh_options.add_argument('--headless')
            for arg in [
                '--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-extensions',
                '--disable-plugins','--disable-images','--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080','--disable-background-timer-throttling','--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding','--disable-features=TranslateUI','--disable-ipc-flooding-protection',
                '--hide-scrollbars','--mute-audio','--disable-web-security','--allow-running-insecure-content',
                '--disable-features=VizDisplayCompositor'
            ]:
                fresh_options.add_argument(arg)
            fresh_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.169 Safari/537.36')

            # Try undetected Chrome directly
            try:
                version_main_hint = None
                if platform.system() == 'Windows' and winreg is not None:
                    try:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Google\\Chrome\\BLBeacon") as key:
                            version, _ = winreg.QueryValueEx(key, 'version')
                            version_main_hint = int(version.split('.')[0])
                    except Exception:
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\\Google\\Chrome\\BLBeacon") as key:
                                version, _ = winreg.QueryValueEx(key, 'version')
                                version_main_hint = int(version.split('.')[0])
                        except Exception:
                            version_main_hint = None
                driver = uc.Chrome(options=fresh_options, version_main=version_main_hint) if version_main_hint else uc.Chrome(options=fresh_options)
            except Exception as uc_error:
                print(f"   ⚠️  UC direct init failed: {uc_error}")
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                chromedriver_base = ChromeDriverManager().install()
                chromedriver_path = chromedriver_base if chromedriver_base.lower().endswith('.exe') else os.path.join(os.path.dirname(chromedriver_base), 'chromedriver.exe')
                print(f"   📦 Using ChromeDriver: {chromedriver_path}")
                service = Service(chromedriver_path)
                wm_options = uc.ChromeOptions()
                for arg in [
                    '--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-extensions',
                    '--disable-plugins','--disable-images','--disable-blink-features=AutomationControlled',
                    '--window-size=1920,1080','--disable-background-timer-throttling','--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding','--disable-features=TranslateUI','--disable-ipc-flooding-protection',
                    '--hide-scrollbars','--mute-audio','--disable-web-security','--allow-running-insecure-content',
                    '--disable-features=VizDisplayCompositor'
                ]:
                    wm_options.add_argument(arg)
                if in_ci or force_headless:
                    try:
                        wm_options.add_argument('--headless=new')
                    except Exception:
                        wm_options.add_argument('--headless')
                driver = uc.Chrome(service=service, options=wm_options)

            try:
                driver.set_page_load_timeout(60)
            except Exception:
                pass
            # Suppress undetected_chromedriver noisy destructor on Windows
            try:
                setattr(driver, '__del__', lambda: None)
            except Exception:
                pass
            print("   ✅ Chrome initialized successfully")
            break
        except Exception as e:
            print(f"   ❌ Chrome init attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                print("   💀 All Chrome initialization attempts failed!")
                print("   🔧 This might be a Chrome/driver/profile issue")
                return []
            time.sleep(5)
    
    if not driver:
        print("   ❌ Chrome driver initialization failed - cannot proceed")
        return []
        
    try:
        # Remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("\n🔍 Phase 1: Loading UFC Events Page")
        print("-" * 40)
        
        # Navigate to the real UFC events page with retry logic
        max_page_retries = 3
        page_loaded = False
        
        for page_attempt in range(max_page_retries):
            try:
                print(f"   🔄 Loading page attempt {page_attempt + 1}/{max_page_retries}")
                driver.get("https://fightodds.io/upcoming-mma-events/ufc")
                time.sleep(10)  # Wait for Cloudflare and page load
                
                # Check if we're past Cloudflare
                page_source = driver.page_source
                if 'cloudflare' in page_source.lower() and 'checking your browser' in page_source.lower():
                    print(f"   ⏳ Still in Cloudflare challenge on attempt {page_attempt + 1}")
                    if page_attempt < max_page_retries - 1:
                        time.sleep(15)  # Wait longer before retry
                        continue
                    else:
                        print("   ❌ Failed to bypass Cloudflare after all attempts")
                        return []
                else:
                    page_loaded = True
                    break
                    
            except TimeoutException:
                print(f"   ⏰ Page load timeout on attempt {page_attempt + 1}")
                if page_attempt == max_page_retries - 1:
                    print("   ❌ Page failed to load after all attempts")
                    return []
            except WebDriverException as e:
                print(f"   ❌ WebDriver error on attempt {page_attempt + 1}: {str(e)}")
                if page_attempt == max_page_retries - 1:
                    return []
        
        if not page_loaded:
            print("   ❌ Failed to load page successfully")
            return []
        
        print("   ✅ Past Cloudflare - extracting events...")
        
        # Phase 2: Extract all UFC events from the page
        print("\n🔍 Phase 2: Extracting All UFC Events")
        print("-" * 40)
        
        # Try to reveal all events (click 'More Events' and scroll)
        try:
            for _ in range(5):
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    more_btns = driver.find_elements(By.XPATH, "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'more events')]")
                    if not more_btns:
                        break
                    clicked_any = False
                    for btn in more_btns:
                        try:
                            btn.click()
                            clicked_any = True
                            time.sleep(1)
                        except Exception:
                            continue
                    if not clicked_any:
                        break
                except Exception:
                    break
        except Exception:
            pass

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Validate that the odds page header/token matches this event (e.g., 'UFC 319')
        try:
            header_txt = ''
            title_el = soup.find('title')
            if title_el and title_el.get_text():
                header_txt = title_el.get_text(' ', strip=True)
            if not header_txt:
                h = soup.find(['h1','h2'])
                if h:
                    header_txt = h.get_text(' ', strip=True)
            token = event_name
            mnum = re.search(r'(UFC\s+\d+)', event_name, re.I)
            if mnum:
                token = mnum.group(1)
            if token and token.upper() not in (header_txt or '').upper():
                print(f"      ⚠️ Skipping odds page (header mismatch): expected token '{token}', got '{header_txt[:100]}'")
                debug_save_html(event_id, 'odds_header_mismatch', page_source)
                return []
        except Exception:
            pass

        # Note: header token validation is performed per-event during odds extraction
        ufc_events = extract_ufc_events_from_page(driver, soup)
        # Fallback: also try the generic upcoming events page if few were found
        if len(ufc_events) < 5:
            try:
                driver.get("https://fightodds.io/upcoming-mma-events")
                time.sleep(5)
                generic_source = driver.page_source
                generic_soup = BeautifulSoup(generic_source, 'html.parser')
                extra_events = extract_ufc_events_from_page(driver, generic_soup)
                # Merge
                for k, v in extra_events.items():
                    if k not in ufc_events:
                        ufc_events[k] = v
            except Exception:
                pass
        print(f"   📅 Found {len(ufc_events)} UFC events")

        # Optional: load pre-scraped FIGHTS index from MMAFights.csv to enforce rosters and dates
        fights_index_by_id = load_fights_index_from_csv('MMAFights.csv')
        if fights_index_by_id:
            print(f"   🗂️  Loaded fights index for {len(fights_index_by_id)} events from MMAFights.csv")
            # Merge any events from fights index that were missed during discovery
            for eid, meta in fights_index_by_id.items():
                name = meta.get('event')
                if not name:
                    continue
                if name not in ufc_events:
                    ufc_events[name] = {
                        'event_url': meta.get('event_url',''),
                        'odds_url': meta.get('odds_url',''),
                        'event_id': eid,
                        'event_date': meta.get('event_date','')
                    }
            print(f"   ➕ After merge from fights index: {len(ufc_events)} events")
        
        # Phase 3: Extract fighter data from each event
        print("\n🔍 Phase 3: Extracting Fighter Data from Each Event")
        print("-" * 40)
        
        all_fighter_data = []
        
        for event_name, event_data in ufc_events.items():
            print(f"   🎯 Extracting: {event_name}")
            
            # Get odds page URL and event date
            odds_url = event_data['odds_url']
            event_date = event_data.get('event_date', '')
            try:
                event_fighters = extract_event_fighters_from_odds(
                    driver,
                    odds_url,
                    event_name,
                    event_date,
                    event_data.get('event_url',''),
                    event_id=event_data.get('event_id'),
                    fights_index_by_id=fights_index_by_id
                )
                all_fighter_data.extend(event_fighters)
                print(f"      ✅ Found {len(event_fighters)} fighters")
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
        
        # Phase 4: Create OddsMarketCombo.csv and .json
        print("\n🔍 Phase 4: Creating OddsMarketCombo Files")
        print("-" * 40)
        
        if not all_fighter_data:
            print("   ❌ No fighter data extracted - cannot create files")
            return []
            
        if all_fighter_data:
            # De-duplicate by (Event, Fighter)
            dedup_map = {}
            for f in all_fighter_data:
                dedup_key = (f.get('event',''), f.get('fighter',''))
                if dedup_key not in dedup_map:
                    dedup_map[dedup_key] = f
            all_fighter_data = list(dedup_map.values())

            # Prevent cross-event bleed: ensure a fighter belongs to only one event
            fighter_seen_event = {}
            filtered = []
            for f in all_fighter_data:
                name = f.get('fighter','')
                ev = f.get('event','')
                if name not in fighter_seen_event:
                    fighter_seen_event[name] = ev
                    filtered.append(f)
                else:
                    if fighter_seen_event[name] != ev:
                        print(f"   🚫 Cross-event bleed: '{name}' already under '{fighter_seen_event[name]}', dropping from '{ev}'")
            all_fighter_data = filtered

            # Union of sportsbooks across all fighters for stable headers
            sportsbooks = []
            seen_books = set()
            for f in all_fighter_data:
                for b in f.get('odds', {}).keys():
                    if b not in seen_books:
                        seen_books.add(b)
                        sportsbooks.append(b)
            
            # Always overwrite OddsMarketCombo.csv
            csv_file = "OddsMarketCombo.csv"
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Create headers with EventDate column
                headers = ['Fighter', 'Event', 'EventDate', 'FightOrder', 'Source'] + sportsbooks
                writer.writerow(headers)
                
                # Write all fighter data
                for fighter_data in all_fighter_data:
                    row = [
                        fighter_data['fighter'],
                        fighter_data['event'],
                        fighter_data.get('event_date', ''),
                        fighter_data.get('fight_order', ''),
                        fighter_data['source']
                    ]
                    
                    for sportsbook in sportsbooks:
                        odds = fighter_data['odds'].get(sportsbook, '')
                        row.append(odds)
                    
                    writer.writerow(row)
            
            # Create JSON backup with fresh timestamp
            json_file = "OddsMarketCombo.json"
            current_timestamp = datetime.now().isoformat()
            json_data = {
                'extraction_timestamp': current_timestamp,
                'extraction_run_id': f"lulsec_{int(time.time())}",
                'total_fighters': len(all_fighter_data),
                'total_events': len(ufc_events),
                'sportsbooks': sportsbooks,
                'events': ufc_events,
                'fighters': all_fighter_data
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
            
            print(f"   ✅ OddsMarketCombo.csv created/updated")
            print(f"   ✅ OddsMarketCombo.json created/updated")
            print(f"   📊 Total fighters: {len(all_fighter_data)}")
            print(f"   📅 Total events: {len(ufc_events)}")
            print(f"   🕐 Extraction timestamp: {current_timestamp}")
            print(f"   🆔 Run ID: lulsec_{int(time.time())}")
        
        return all_fighter_data
        
    except KeyboardInterrupt:
        print("\n🛑 Extraction interrupted by user")
        return []
    except Exception as main_error:
        print(f"\n💥 Main extraction error: {str(main_error)}")
        print("   🔧 This might be a network, browser, or parsing issue")
        return []
    finally:
        try:
            if driver:
                driver.quit()
                print("   🔒 Chrome driver closed")
        except Exception as cleanup_error:
            print(f"   ⚠️  Driver cleanup warning: {str(cleanup_error)}")

def extract_ufc_events_from_page(driver, soup):
    """Extract all UFC events from the events page, with dates.

    Uses static HTML via BeautifulSoup to avoid stale element references, then
    optionally opens individual event pages to fetch accurate dates.
    """
    ufc_events = {}

    try:
        # Parse anchors from static HTML
        event_links = soup.select("a[href*='/mma-events/']")
        seen_ids = set()
        for a in event_links:
            try:
                href = a.get('href')
                event_url = urljoin("https://fightodds.io/", href) if href else None
                if not event_url:
                    continue
                # Extract event ID
                event_id_match = re.search(r'/mma-events/(\d+)/', event_url)
                if not event_id_match:
                    continue
                event_id = event_id_match.group(1)
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                # Derive slug from URL and a readable name if needed
                slug_match = re.search(r"/mma-events/\d+/([^/]+)/", event_url)
                slug_segment = slug_match.group(1) if slug_match else ''
                link_text_name = (a.get_text(strip=True) or '').strip()
                inferred_name = link_text_name or slug_segment.replace('-', ' ').title()
                if 'UFC' not in inferred_name.upper() and 'ufc' not in slug_segment:
                    continue
                clean_name = clean_event_name(inferred_name) or inferred_name

                # Always derive odds URL directly from the canonical event URL to prevent redirects
                base_event_url = event_url.rstrip('/')
                odds_url = f"{base_event_url}/odds"

                # Extract event date: row vicinity, then event page
                event_date = ''
                try:
                    parent = a.find_parent(['tr','div','li','section'])
                    if parent:
                        row_text = parent.get_text(" ", strip=True)
                        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?', row_text, re.I)
                        if not date_match:
                            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2}(?:,\s*\d{4})?', row_text, re.I)
                        if date_match:
                            event_date = normalize_event_date_string(date_match.group(0)) or ''
                except Exception:
                    pass
                if not event_date:
                    event_date = extract_event_date_from_event_page(driver, event_url) or extract_event_date(clean_name) or ''

                if clean_name not in ufc_events:
                    ufc_events[clean_name] = {
                        'event_url': event_url,
                        'odds_url': odds_url,
                        'event_id': event_id,
                        'event_date': event_date
                    }
                    print(f"   ✅ Found UFC event: {clean_name} ({event_date})")
            except Exception:
                continue

        # Secondary: pattern scan in full text for any missed events
        page_text = soup.get_text(" ")
        ufc_patterns = [
            r'UFC\s+Fight\s+Night[^\n]*?vs\.[^\n]*?(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+',
            r'UFC\s+\d+[^\n]*?vs\.[^\n]*?(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+',
            r'UFC\s+Fight\s+Night[^\n]*?vs\.[^\n]*?',
            r'UFC\s+\d+[^\n]*?vs\.[^\n]*?'
        ]
        for pattern in ufc_patterns:
            for match in re.findall(pattern, page_text, re.IGNORECASE):
                clean_match = clean_event_name(match)
                if not clean_match or clean_match in ufc_events:
                    continue
                # Attempt to find event id via any link containing the slug
                slug = clean_match.lower().replace(' ', '-').replace(':', '')
                link = soup.find('a', href=re.compile(rf"/mma-events/(\d+)/{re.escape(slug)}"))
                event_id = None
                event_url = None
                if link and link.get('href'):
                    href2 = link.get('href')
                    m = re.search(r'/mma-events/(\d+)/', href2)
                    if m:
                        event_id = m.group(1)
                        event_url = urljoin("https://fightodds.io/", href2)
                if not event_id:
                    continue
                # Always derive odds URL directly from the canonical event URL to prevent redirects
                base_event_url = event_url.rstrip('/')
                odds_url = f"{base_event_url}/odds"
                # Try to parse date near the link first
                event_date = ''
                try:
                    parent = link.find_parent(['tr','div','li','section']) if link else None
                    if parent:
                        row_text = parent.get_text(" ", strip=True)
                        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?', row_text, re.I)
                        if not date_match:
                            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2}(?:,\s*\d{4})?', row_text, re.I)
                        if date_match:
                            event_date = normalize_event_date_string(date_match.group(0)) or ''
                except Exception:
                    pass

                if not event_date:
                    event_date = extract_event_date_from_event_page(driver, event_url) or extract_event_date(clean_match) or ''
                ufc_events[clean_match] = {
                    'event_url': event_url,
                    'odds_url': odds_url,
                    'event_id': event_id,
                    'event_date': event_date
                }
                print(f"   ✅ Found UFC event via pattern: {clean_match} ({event_date})")

    except Exception as e:
        print(f"   ❌ Error extracting UFC events: {str(e)}")

    return ufc_events

def extract_event_date_from_event_page(driver, event_url):
    """Open an event page and try to extract a normalized YYYY-MM-DD date from JSON-LD/meta or header."""
    try:
        driver.get(event_url)
        time.sleep(5)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # 1) JSON-LD datePublished/startDate
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.get_text(strip=True))
                if isinstance(data, dict):
                    for key in ['startDate', 'datePublished', 'dateCreated', 'date']:
                        if key in data and data[key]:
                            normalized = normalize_event_date_string(str(data[key]))
                            if normalized:
                                return normalized
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            for key in ['startDate', 'datePublished', 'dateCreated', 'date']:
                                if key in item and item[key]:
                                    normalized = normalize_event_date_string(str(item[key]))
                                    if normalized:
                                        return normalized
            except Exception:
                pass

        # 2) Meta tags
        for meta_name in ['event_date', 'date', 'pubdate', 'og:pubdate', 'article:published_time']:
            meta = soup.find('meta', attrs={'name': meta_name}) or soup.find('meta', attrs={'property': meta_name})
            if meta and meta.get('content'):
                normalized = normalize_event_date_string(meta['content'])
                if normalized:
                    return normalized

        # 3) Visible text patterns (header/subtitle)
        header = soup.find(['h1','h2','h3'])
        header_text = header.get_text(' ', strip=True) if header else ''
        text_blob = ' '.join([header_text, soup.get_text(' ', strip=True)[:2000]])
        for pattern in [
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s*\d{4}',
            r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}(?:,\s*\d{4})?'
        ]:
            m = re.search(pattern, text_blob)
            if m:
                normalized = normalize_event_date_string(m.group(0))
                if normalized:
                    return normalized

        return ''
    except Exception:
        return ''

def normalize_event_date_string(date_str):
    """Normalize various date strings into YYYY-MM-DD if possible."""
    date_str = date_str.strip()
    fmts = [
        '%B %d, %Y', '%b %d, %Y',  # January 25, 2025 / Jan 25, 2025
        '%Y-%m-%d',                # 2025-01-25
        '%b %d %Y', '%B %d %Y',    # Jan 25 2025
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(date_str.replace('\u00a0',' '), fmt)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # Fallback: Month DD (no year) → infer this or next year
    try:
        m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})', date_str, re.I)
        if m:
            month_name = m.group(1).rstrip('.')
            day = int(m.group(2))
            month_num = datetime.strptime(month_name[:3], '%b').month
            year = datetime.now().year
            candidate = datetime(year, month_num, day)
            # If this date already passed by > 7 days, assume next year
            if (candidate - datetime.now()).days < -7:
                candidate = datetime(year + 1, month_num, day)
            return candidate.strftime('%Y-%m-%d')
    except Exception:
        pass
    return ''

def get_event_token(event_name: str) -> str:
    """Return a short identifying token for the event, like 'UFC 319' if present, else the full name."""
    try:
        m = re.search(r'(UFC\s+\d+)', event_name, re.I)
        return m.group(1) if m else event_name
    except Exception:
        return event_name

def debug_save_html(event_id: str | None, kind: str, html: str) -> None:
    """Best-effort dump of HTML for debugging scoped-table/odds issues."""
    try:
        if not html:
            return
        os.makedirs('debug_html', exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        eid = event_id or 'unknown'
        path = os.path.join('debug_html', f"{eid}_{kind}_{stamp}.html")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass

def normalize_fighter_name_for_match(name: str) -> str:
    """Normalize fighter names for comparison across roster/odds tables.

    Lowercase, remove punctuation, collapse whitespace. Keeps alphabetic tokens.
    """
    try:
        s = name.lower()
        # Replace non-letters with space
        s = re.sub(r"[^a-z\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s
    except Exception:
        return name.strip().lower()

def match_name_to_roster(candidate_name: str, roster_names: set[str]) -> str | None:
    """Return the canonical roster name that best matches candidate_name, or None.

    Matching strategy: normalize both names and compare token overlap; accept if
    one set is subset of the other, or Jaccard >= 0.6.
    """
    if not candidate_name or not roster_names:
        return None
    cand_norm = normalize_fighter_name_for_match(candidate_name)
    cand_tokens = set(cand_norm.split())
    if not cand_tokens:
        return None
    best_name = None
    best_score = 0.0
    for roster_name in roster_names:
        r_norm = normalize_fighter_name_for_match(roster_name)
        r_tokens = set(r_norm.split())
        if not r_tokens:
            continue
        inter = len(cand_tokens & r_tokens)
        union = len(cand_tokens | r_tokens)
        jacc = inter / union if union else 0.0
        subset_ok = cand_tokens.issubset(r_tokens) or r_tokens.issubset(cand_tokens)
        score = jacc + (0.2 if subset_ok else 0.0)
        if score > best_score:
            best_score = score
            best_name = roster_name
    if best_score >= 0.6:
        return best_name
    return None

def extract_event_fighters_from_odds(driver, odds_url, event_name, event_date='', event_url_hint='', event_id=None, fights_index_by_id=None):
    """Extract fighter data from the odds page of an event, with fight order.

    Fight order is inferred by reading the dedicated 'FIGHTS' tab card list in order
    and assigning descending numbers with main event = 1, co-main = 2, etc.
    Cancelled fights are tagged with FightOrder = 0.
    """
    try:
        driver.get(odds_url)
        time.sleep(5)
        # Attempt to expand/scroll to load all fights/odds rows
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
        except Exception:
            pass

        # Try clicking potential expanders to reveal all fights/odds
        try:
            def click_candidates():
                clicked = 0
                scripts = [
                    "return Array.from(document.querySelectorAll('button, a')).filter(el => /show|expand|more|lines|odds/i.test(el.innerText)).slice(0,50);",
                    'return Array.from(document.querySelectorAll("[aria-expanded=\'false\'], .expand, .toggle, .collapsed")).slice(0,50);'
                ]
                for js in scripts:
                    try:
                        elements = driver.execute_script(js)
                        for el in elements or []:
                            try:
                                el.click()
                                clicked += 1
                                time.sleep(0.2)
                            except Exception:
                                pass
                    except Exception:
                        pass
                return clicked

            # Iterate a few rounds to progressively expand content
            for _ in range(3):
                num = click_candidates()
                if num == 0:
                    break
                time.sleep(1)
        except Exception:
            pass
        
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Attempt to load the FIGHTS page HTML via the same driver to capture card order and roster
        fight_order_map = {}
        event_fighter_roster = set()
        # If we have a prebuilt index for this event_id, prefer that roster and order
        if fights_index_by_id and event_id and event_id in fights_index_by_id:
            pre = fights_index_by_id[event_id]
            event_fighter_roster = set(pre['roster'])
            fight_order_map = pre.get('order_map', {})
        try:
            fights_url = None
            # Construct directly by replacing '/odds' with '/fights'
            if odds_url.endswith('/odds'):
                fights_url = odds_url[:-5] + 'fights'
            if not fights_url:
                # Fallback: discover via nav link
                for a in soup.select('a[href]'):
                    if a.get_text(strip=True).upper() == 'FIGHTS':
                        href = a.get('href')
                        fights_url = href if href.startswith('http') else urljoin(odds_url, href)
                        break
            if fights_url and not event_fighter_roster:
                # Prefer loading FIGHTS in the same undetected driver to bypass Cloudflare
                last_err = None
                for attempt in range(3):
                    try:
                        driver.get(fights_url)
                        time.sleep(5)
                        fights_html = driver.page_source or ''
                        if fights_html:
                            # Basic Cloudflare check
                            if 'cloudflare' in fights_html.lower() and 'checking your browser' in fights_html.lower():
                                last_err = 'cloudflare challenge'
                                time.sleep(5 + attempt * 5)
                                continue
                            fights_soup = BeautifulSoup(fights_html, 'html.parser')
                            fight_order_map = extract_fight_order_from_card(fights_soup)
                            event_fighter_roster = parse_fight_card_names(fights_soup)
                            # Debug sample of roster
                            try:
                                sample_roster = list(event_fighter_roster)[:8]
                                if sample_roster:
                                    print(f"      👥 Roster sample: {sample_roster}")
                            except Exception:
                                pass
                            break
                        else:
                            last_err = 'empty page'
                    except Exception as e:
                        last_err = str(e)
                    time.sleep(2)
                if not event_fighter_roster:
                    print(f"      ⚠️ FIGHTS roster missing for '{event_name}' ({last_err or 'no data'}) - skipping event")
                    debug_save_html(event_id, 'fights_missing_roster', driver.page_source)
                    return []
        except Exception:
            print(f"      ⚠️ FIGHTS page parse error for '{event_name}' - skipping event")
            return []

        # Try to refresh event_date from the odds page header if missing
        if not event_date:
            try:
                header = soup.find(['h1','h2','h3'])
                header_text = header.get_text(' ', strip=True) if header else ''
                # Look around the header area for a nearby date label
                container = header.parent if header else soup
                vicinity = container.get_text(' ', strip=True)[:400]
                for pattern in [
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}',
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s*\d{4}',
                    r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}(?:,\s*\d{4})?'
                ]:
                    m = re.search(pattern, vicinity)
                    if m:
                        event_date = normalize_event_date_string(m.group(0)) or event_date
                        break
            except Exception:
                pass
        
        # Extract sportsbook headers
        sportsbooks = extract_sportsbook_headers(soup)

        # Prefer a table located via event header proximity to avoid cross-event bleed
        # Canonicalize event header token to help locate the correct table; prefer hint
        event_token = event_url_hint or event_name
        mnum = re.search(r'(UFC\s+\d+)', event_name, re.I)
        if mnum:
            event_token = mnum.group(1)
        event_table = find_event_table_for_event(soup, event_token)
        if event_table is not None:
            fighters = extract_fighter_odds_from_table(event_table, sportsbooks)
        else:
            # No scoped table; scan all tables but keep strict roster filter afterwards
            debug_save_html(event_id, 'odds_no_scoped_table', page_source)
            fighters = []
            try:
                for tbl in soup.find_all('table'):
                    fighters.extend(extract_fighter_odds_from_table(tbl, sportsbooks))
            except Exception:
                pass
        # Debug sample of extracted fighter names
        try:
            sample_candidates = [f.get('fighter','') for f in fighters[:8]]
            if sample_candidates:
                print(f"      🧪 Odds table sample: {sample_candidates}")
        except Exception:
            pass
        
        # Build base roster entries (ensures every matchup appears even if odds not yet listed)
        base_entries = []
        for name in sorted(event_fighter_roster):
            entry = {'fighter': name, 'odds': {}}
            ord_val = fight_order_map.get(name.strip().lower()) if fight_order_map else None
            if ord_val is not None:
                entry['fight_order'] = ord_val
            base_entries.append(entry)

        # Filter scraped odds rows by roster using fuzzy token match; then merge into base entries
        pre_count = len(fighters)
        roster_set = set(event_fighter_roster)
        filtered_with_odds = []
        for f in fighters:
            cand = f.get('fighter','')
            match = match_name_to_roster(cand, roster_set)
            if match:
                f['fighter'] = match
                filtered_with_odds.append(f)
        kept = len(filtered_with_odds)
        skipped = pre_count - kept
        print(f"      📋 Roster size: {len(event_fighter_roster)} | Fighters kept: {kept} | Skipped (not on card): {skipped}")

        # Merge odds into base roster entries
        odds_by_name = { f['fighter']: f.get('odds', {}) for f in filtered_with_odds }
        fighters = []
        for entry in base_entries:
            name = entry['fighter']
            if name in odds_by_name:
                entry['odds'] = odds_by_name[name]
            fighters.append(entry)

        # If we still have zero odds rows but the event page might have per-fight odds links, try pair-specific discovery within the fights page
        if not odds_by_name and fights_url:
            try:
                # Reuse fights_soup if available; otherwise fetch again quickly
                if 'fights_soup' not in locals():
                    driver.get(fights_url)
                    time.sleep(3)
                    fights_html2 = driver.page_source or ''
                    fights_soup2 = BeautifulSoup(fights_html2, 'html.parser')
                else:
                    fights_soup2 = fights_soup

                # Find anchors for individual fight odds pages within the fights card
                pair_links = []
                for a in fights_soup2.select('a[href]'):
                    href = a.get('href') or ''
                    txt = (a.get_text(' ', strip=True) or '').lower()
                    if 'odds' in txt or re.search(r'/mma-events/\d+/.+?/odds', href):
                        abs_url = href if href.startswith('http') else urljoin(odds_url, href)
                        pair_links.append(abs_url)
                pair_links = list(dict.fromkeys(pair_links))[:12]

                # For each pair link, try to parse a tiny scoped table and merge if fighters match roster
                for link in pair_links:
                    try:
                        driver.get(link)
                        time.sleep(2)
                        sub_html = driver.page_source or ''
                        sub_soup = BeautifulSoup(sub_html, 'html.parser')
                        sub_table = sub_soup.find('table')
                        if not sub_table:
                            continue
                        sub_sportsbooks = extract_sportsbook_headers(sub_soup)
                        sub_fighters = extract_fighter_odds_from_table(sub_table, sub_sportsbooks)
                        # Merge only if both fighters are in roster
                        for sf in sub_fighters:
                            match = match_name_to_roster(sf.get('fighter',''), roster_set)
                            if match:
                                entry = next((e for e in fighters if e['fighter']==match), None)
                                if entry:
                                    entry['odds'].update(sf.get('odds', {}))
                    except Exception:
                        continue
            except Exception:
                pass

        # Add event info to each fighter
        for fighter in fighters:
            fighter['event'] = event_name
            # Prefer event date from fights index if provided
            fighter['event_date'] = event_date or (fights_index_by_id.get(event_id, {}).get('event_date') if fights_index_by_id and event_id else '')
            fighter['source'] = 'fightodds.io'
            # Attach fight order if available (match by fighter name occurrence)
            try:
                name = fighter['fighter']
                key = name.strip().lower()
                order = None
                if fight_order_map:
                    order = fight_order_map.get(key)
                if order is not None:
                    fighter['fight_order'] = order
            except Exception:
                pass

        # Fallback: if fight order missing for any fighter, assign by table order (pairs top-down)
        try:
            needs_order = any('fight_order' not in f or f['fight_order'] == '' for f in fighters)
            if needs_order and len(fighters) >= 2:
                order_counter = 1
                for idx in range(0, len(fighters), 2):
                    if idx < len(fighters):
                        fighters[idx]['fight_order'] = fighters[idx].get('fight_order', order_counter) or order_counter
                    if idx + 1 < len(fighters):
                        fighters[idx + 1]['fight_order'] = fighters[idx + 1].get('fight_order', order_counter) or order_counter
                    order_counter += 1
        except Exception:
            pass
        
        return fighters
    
    except Exception as e:
        print(f"   ❌ Error extracting from {odds_url}: {str(e)}")
        return []

def extract_sportsbook_headers(soup):
    """Extract sportsbook column headers from the table"""
    sportsbooks = []
    
    # Look for table headers
    table_headers = soup.find_all('th')
    for header in table_headers:
        text = header.get_text(strip=True)
        if text and text not in ['Fighters', ''] and len(text) > 1:
            sportsbooks.append(text)

    # Also look for sportsbook logos/alt text in header rows
    if not sportsbooks:
        header_rows = soup.select('thead tr, tr.header')
        for row in header_rows:
            for img in row.find_all('img', alt=True):
                alt = img.get('alt', '').strip()
                if alt and alt.lower() not in ['fighters']:
                    sportsbooks.append(alt)
    
    # If no headers found, try common sportsbook names
    if not sportsbooks:
        common_sportsbooks = [
            'BetOnline', 'Bovada', 'Bet105', 'Jazz', '4Cx', 'MyBookie', 
            'Bookmaker', 'BetAnySports', 'BetUS', 'DraftKings', 'FanDuel',
            'Pinnacle', 'Betway', 'ESPN', 'Circa', 'Stake', 'BetRivers',
            'BetMGM', 'Caesars'
        ]
        sportsbooks = common_sportsbooks
    else:
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for name in sportsbooks:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        sportsbooks = deduped
    
    return sportsbooks

def find_event_table_for_event(soup, event_name):
    """Find an odds table scoped to the event header section.

    Strategy:
    - Build tokens: full name and short token (e.g., 'UFC 319').
    - Locate heading node containing a token; search within sibling/section containers for the first table.
    - Avoid returning the page-global largest table.
    """
    tokens = [event_name]
    short = get_event_token(event_name)
    if short and short not in tokens:
        tokens.append(short)

    def nearest_table_from_node(node):
        try:
            # Search in parent → its following siblings → the node's next siblings
            parent = node.find_parent()
            if parent:
                tbl = parent.find('table') or parent.find_next('table')
                if tbl:
                    return tbl
            sib = node.parent
            if sib:
                tbl = sib.find('table') or sib.find_next('table')
                if tbl:
                    return tbl
        except Exception:
            return None
        return None

    for token in tokens:
        try:
            el = soup.find(string=re.compile(re.escape(token), re.I))
            if el:
                tbl = nearest_table_from_node(el)
                if tbl:
                    return tbl
        except Exception:
            continue
    return None

def extract_fighter_odds_from_table(table, sportsbooks):
    fighter_data = []
    rows = table.find_all('tr')
    seen = set()
    for row in rows[1:]:
        cells = row.find_all(['td','th'])
        if len(cells) > 1:
            fighter_name = cells[0].get_text(strip=True)
            if fighter_name and len(fighter_name) > 2 and fighter_name.lower() not in ['fighters','fighter']:
                if fighter_name in seen:
                    continue
                seen.add(fighter_name)
                record = {'fighter': fighter_name, 'odds': {}}
                for i, sportsbook in enumerate(sportsbooks, 1):
                    if i < len(cells):
                        odds_cell = cells[i].get_text(strip=True)
                        m = re.search(r'([+-]\d+)', odds_cell)
                        record['odds'][sportsbook] = m.group(1) if m else ''
                fighter_data.append(record)
    return fighter_data

def extract_fight_order_from_card(soup):
    """Parse the fight card page to determine fight order per fighter name.

    Strategy:
    - Identify sections labeled MAIN CARD, PRELIMINARY CARD, CANCELLED FIGHTS
    - Collect rows in displayed order; assign order numbers from top to bottom:
      main event = 1, co-main = 2, etc. Prelims continue incrementing.
    - Cancelled fights get order 0.
    """
    order_map = {}

    # Collect blocks with headings
    blocks = []
    for heading_text, weight in [
        ('MAIN CARD', 0),
        ('PRELIMINARY', 1),
        ('CANCELLED', 2)
    ]:
        for el in soup.find_all(string=re.compile(heading_text, re.I)):
            # Try to find the container that holds rows after this heading
            parent = el.find_parent(['div','table','tbody','section'])
            if parent and parent not in blocks:
                blocks.append(parent)

    # Fallback: use any table-like rows if headings not found
    if not blocks:
        blocks = [soup]

    # Extract fights in order
    next_order = 1
    for block in blocks:
        rows = []
        # Common structure on fightodds card: table-like with two fighter columns
        for row in block.find_all(['tr','div'], recursive=True):
            text = row.get_text(' ', strip=True)
            if not text or 'vs' not in text.lower():
                continue
            # Identify two fighter spans/links within the row
            names = []
            # Prefer anchor/text elements for fighters
            for name_el in row.select('a, span, div'):
                name_txt = name_el.get_text(' ', strip=True)
                # Heuristics to exclude buttons/labels
                if name_txt and len(name_txt) > 2 and name_txt.lower() not in ['odds','news','breakdown','info','fights']:
                    names.append(name_txt)
                if len(names) >= 2:
                    break
            if len(names) >= 2:
                rows.append((names[0], names[1]))

        # If we have rows, assign orders
        for fighter_a, fighter_b in rows:
            # Skip obviously non-fight rows
            if not fighter_a or not fighter_b:
                continue
            # Determine cancelled by presence of 'cancel' near row text
            row_text = f"{fighter_a} vs {fighter_b}"
            is_cancelled = bool(re.search(r'cancel', row_text, re.I))
            order_value = 0 if is_cancelled else next_order
            # Normalize keys to lower-case for matching
            order_map[fighter_a.strip().lower()] = order_value
            order_map[fighter_b.strip().lower()] = order_value
            if not is_cancelled:
                next_order += 1

    return order_map

def parse_fight_card_names(soup):
    """Extract a set of fighter names from the event's fight card page.

    Implementation reuses the scoped blocks and parsing logic of
    `extract_fight_order_from_card` to avoid capturing site navigation or
    unrelated text. Returns a set of normalized lower-case names.
    """
    try:
        order_map = extract_fight_order_from_card(soup)
        return set(order_map.keys())
    except Exception:
        return set()

def extract_fighter_odds(soup, sportsbooks):
    """Extract fighter data with odds from each sportsbook"""
    fighter_data = []
    
    # Find the main odds table
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        for row in rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            
            if len(cells) > 1:
                # First cell should be fighter name
                fighter_name = cells[0].get_text(strip=True)
                
                if fighter_name and len(fighter_name) > 2:
                    fighter_odds = {
                        'fighter': fighter_name,
                        'odds': {}
                    }
                    
                    # Extract odds for each sportsbook
                    for i, sportsbook in enumerate(sportsbooks, 1):
                        if i < len(cells):
                            odds_cell = cells[i].get_text(strip=True)
                            # Clean odds value
                            odds_match = re.search(r'([+-]\d+)', odds_cell)
                            if odds_match:
                                fighter_odds['odds'][sportsbook] = odds_match.group(1)
                            else:
                                fighter_odds['odds'][sportsbook] = ''
                    
                    fighter_data.append(fighter_odds)
    
    return fighter_data

def extract_fighter_odds_scoped(soup, sportsbooks):
    """Extract fighter odds but scope to visible event blocks to avoid duplicate carryover.

    Heuristic: start after the first header cell that says 'Fighters' and stop
    when the next header row or 'More Events' section appears.
    """
    fighter_data = []
    odds_tables = soup.find_all('table')
    if not odds_tables:
        return fighter_data
    # Use the first sizeable table
    table = max(odds_tables, key=lambda t: len(t.find_all('tr')))
    rows = table.find_all('tr')
    seen = set()
    # Skip header
    for row in rows[1:]:
        cells = row.find_all(['td','th'])
        # break if row resembles a new event header
        row_text = row.get_text(' ', strip=True)
        if re.search(r'UFC\s+\d+|UFC\s+Fight\s+Night', row_text, re.I):
            break
        if len(cells) > 1:
            fighter_name = cells[0].get_text(strip=True)
            if fighter_name and len(fighter_name) > 2 and fighter_name.lower() not in ['fighters']:
                if fighter_name in seen:
                    continue
                seen.add(fighter_name)
                record = { 'fighter': fighter_name, 'odds': {} }
                for i, sportsbook in enumerate(sportsbooks, 1):
                    if i < len(cells):
                        odds_cell = cells[i].get_text(strip=True)
                        m = re.search(r'([+-]\d+)', odds_cell)
                        record['odds'][sportsbook] = m.group(1) if m else ''
                fighter_data.append(record)
    return fighter_data

def clean_event_name(event_text):
    """Clean event name by removing HTML tags and extra text"""
    if not event_text:
        return None
    
    # Remove HTML tags
    clean_text = re.sub(r'<[^>]+>', '', event_text)
    
    # Remove extra whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Remove common unwanted text
    unwanted_patterns = [
        r'FightersBetOnlineBovada.*$',
        r'EVENT INFOFIGHT CARD.*$',
        r'More Events.*$',
        r'LoginRegister.*$',
        r'Track Lines Breakdown.*$',
        r'You must be 18.*$',
        r'ONEONE Friday Fights.*$',
        r'July 2512.*$',
        r'July 249.*$'
    ]
    
    for pattern in unwanted_patterns:
        clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
    
    # Clean up any remaining artifacts
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Only return if it looks like a real event name
    if len(clean_text) > 10 and 'UFC' in clean_text.upper():
        return clean_text
    
    return None

def extract_event_date(event_name):
    """Extract event date from event name"""
    if not event_name:
        return None
    
    # Date patterns to look for - more specific patterns
    date_patterns = [
        # UFC 319: Du Plessis vs. Chimaev - JAN 25
        r'(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+',
        # UFC Fight Night: Taira vs. Park - January 25
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+',
        # UFC Fight Night: Oct. 18
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.\s+\d+',
        # Look for dates at the end of event names
        r'(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+$',
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+$'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, event_name, re.IGNORECASE)
        if match:
            date_str = match.group(0).strip()
            return date_str
    
    return None

def load_fights_index_from_csv(csv_path: str):
    """Load MMAFights.csv to build an index by event_id containing:
    - roster: list of unique fighter names on that card
    - order_map: name(lower)->fight_order (1..N based on row order per event)
    - event_date: propagated date if present
    Requires that fight_url contains /mma-events/{id}/.
    """
    try:
        if not os.path.exists(csv_path):
            return {}
        index = {}
        with open(csv_path, 'r', encoding='utf-8') as f:
            header_line = f.readline()
            if not header_line:
                return {}
            header = [h.strip() for h in header_line.strip().split(',')]
            def idx(col):
                return header.index(col) if col in header else -1
            i_event = idx('Event')
            i_date = idx('EventDate')
            i_f1 = idx('Fighter1')
            i_f2 = idx('Fighter2')
            i_url = idx('FightURL')
            order_counter_by_event = {}
            for raw in f:
                line = raw.rstrip('\n')
                # naive CSV split that respects simple quoted commas
                parts = [p.strip() for p in re.split(r',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', line)]
                if max(i_event, i_date, i_f1, i_f2, i_url) >= len(parts):
                    continue
                fight_url = parts[i_url]
                m = re.search(r'/mma-events/(\d+)/', fight_url)
                if not m:
                    continue
                eid = m.group(1)
                event_name = parts[i_event]
                event_date = parts[i_date]
                f1 = parts[i_f1]
                f2 = parts[i_f2]
                if eid not in index:
                    # Derive canonical event_url/odds_url from the first fight_url seen
                    base_event_url = fight_url.rstrip('/')
                    if base_event_url.endswith('/fights'):
                        base_event_url = base_event_url[:-7]
                    odds_url = f"{base_event_url}/odds"
                    index[eid] = {
                        'event': event_name,
                        'event_date': event_date,
                        'roster': [],
                        'order_map': {},
                        'event_url': base_event_url,
                        'odds_url': odds_url
                    }
                    order_counter_by_event[eid] = 1
                order_val = order_counter_by_event[eid]
                order_counter_by_event[eid] = order_val + 1
                for fn in [f1, f2]:
                    if fn and fn not in index[eid]['roster']:
                        index[eid]['roster'].append(fn)
                        index[eid]['order_map'][fn.strip().lower()] = order_val
            return index
    except Exception:
        return {}

if __name__ == "__main__":
    # Check for debug mode from environment variable
    debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    results = odds_market_combo(debug_mode=debug_mode)
    if results:
        print(f"\n🎯 FINAL RESULTS:")
        print(f"   Total fighters: {len(results)}")
        print(f"   File: OddsMarketCombo.csv")
        print(f"   Debug mode: {debug_mode}")
        print("\nFor the lulz! 🏴‍☠️")
    else:
        print(f"\n❌ EXTRACTION FAILED")
        print(f"   Debug mode: {debug_mode}")
        print("   Check logs for errors")
        sys.exit(1) 