import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from bs4 import BeautifulSoup
import csv
import json
import re
import time
import os
import sys
from datetime import datetime
import requests
from urllib.parse import urljoin, urlparse

class MMAFightScraper:
    """
    LulSec MMA Fight Scraper - Hardcore Data Plunder Edition
    Scrapes fightodds.io for UFC events and matchups
    Outputs: MMAFights.csv (overwrites each run)
    Outputs: MMAFights.json (overwrites each run)
    """
    
    def __init__(self):
        self.driver = None
        self.base_url = "https://fightodds.io"
        self.events_data = {}
        self.fights_data = []
        self.session = requests.Session()
        
        # Configure session headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def initialize_driver(self):
        """Initialize undetected Chrome driver with stealth settings"""
        print("🔧 Initializing stealth Chrome driver...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"   🔄 Chrome initialization attempt {attempt + 1}/{max_retries}")
                
                # Create fresh ChromeOptions for each attempt
                fresh_options = uc.ChromeOptions()
                fresh_options.add_argument('--headless')
                fresh_options.add_argument('--no-sandbox')
                fresh_options.add_argument('--disable-dev-shm-usage')
                fresh_options.add_argument('--disable-gpu')
                fresh_options.add_argument('--disable-extensions')
                fresh_options.add_argument('--disable-plugins')
                fresh_options.add_argument('--disable-images')
                fresh_options.add_argument('--disable-blink-features=AutomationControlled')
                fresh_options.add_argument('--window-size=1920,1080')
                fresh_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                # Additional stealth settings
                fresh_options.add_argument('--disable-background-timer-throttling')
                fresh_options.add_argument('--disable-backgrounding-occluded-windows')
                fresh_options.add_argument('--disable-renderer-backgrounding')
                fresh_options.add_argument('--disable-features=TranslateUI')
                fresh_options.add_argument('--disable-ipc-flooding-protection')
                fresh_options.add_argument('--hide-scrollbars')
                fresh_options.add_argument('--mute-audio')
                
                self.driver = uc.Chrome(options=fresh_options)
                
                # Remove webdriver property
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                print("   ✅ Chrome initialized successfully")
                return True
                
            except Exception as e:
                print(f"   ❌ Chrome init attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    print("   💀 All Chrome initialization attempts failed!")
                    return False
                time.sleep(5)
        
        return False
    
    def load_page_with_retry(self, url, max_retries=3):
        """Load page with retry logic and Cloudflare bypass"""
        for attempt in range(max_retries):
            try:
                print(f"   🔄 Loading {url} - attempt {attempt + 1}/{max_retries}")
                self.driver.get(url)
                time.sleep(10)  # Wait for Cloudflare and page load
                
                # Check if we're past Cloudflare
                page_source = self.driver.page_source
                if 'cloudflare' in page_source.lower() and 'checking your browser' in page_source.lower():
                    print(f"   ⏳ Still in Cloudflare challenge on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(15)
                        continue
                    else:
                        print("   ❌ Failed to bypass Cloudflare after all attempts")
                        return None
                else:
                    print("   ✅ Page loaded successfully")
                    return page_source
                    
            except TimeoutException:
                print(f"   ⏰ Page load timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    print("   ❌ Page failed to load after all attempts")
                    return None
            except WebDriverException as e:
                print(f"   ❌ WebDriver error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    return None
        
        return None
    
    def extract_ufc_events(self):
        """Extract all UFC events from the upcoming events page"""
        print("\n🔍 Phase 1: Extracting UFC Events")
        print("-" * 40)
        
        events_url = f"{self.base_url}/upcoming-mma-events/ufc"
        page_source = self.load_page_with_retry(events_url)
        
        if not page_source:
            print("   ❌ Failed to load events page")
            return {}
        
        soup = BeautifulSoup(page_source, 'html.parser')
        events = {}
        
        try:
            # Look for event cards/links
            event_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/mma-events/')]")
            
            for element in event_elements:
                event_name = element.text.strip()
                event_url = element.get_attribute('href')
                
                if event_name and event_url and 'UFC' in event_name.upper():
                    clean_name = self.clean_event_name(event_name)
                    if clean_name:
                        # Extract event ID from URL
                        event_id_match = re.search(r'/mma-events/(\d+)/', event_url)
                        if event_id_match:
                            event_id = event_id_match.group(1)
                            
                            # Construct fights URL
                            event_slug = clean_name.lower().replace(' ', '-').replace(':', '').replace('.', '')
                            fights_url = f"{self.base_url}/mma-events/{event_id}/{event_slug}/fights"
                            
                            # Extract event date
                            event_date = self.extract_event_date(clean_name)
                            
                            events[clean_name] = {
                                'event_url': event_url,
                                'fights_url': fights_url,
                                'event_id': event_id,
                                'event_name': clean_name,
                                'event_date': event_date
                            }
                            print(f"   ✅ Found UFC event: {clean_name}")
            
            # Also look for event patterns in text
            page_text = soup.get_text()
            
            # UFC event patterns
            ufc_patterns = [
                r'UFC\s+Fight\s+Night[^<]*?vs\.[^<]*?(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+',
                r'UFC\s+\d+[^<]*?vs\.[^<]*?(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+',
                r'UFC\s+Fight\s+Night[^<]*?vs\.[^<]*?',
                r'UFC\s+\d+[^<]*?vs\.[^<]*?'
            ]
            
            for pattern in ufc_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    clean_match = self.clean_event_name(match)
                    if clean_match and clean_match not in events and 'UFC' in clean_match:
                        # Try to find the event ID in the page source
                        event_id_match = re.search(r'/mma-events/(\d+)/[^"]*' + re.escape(clean_match.lower().replace(' ', '-')), page_text)
                        if event_id_match:
                            event_id = event_id_match.group(1)
                            event_slug = clean_match.lower().replace(' ', '-').replace(':', '').replace('.', '')
                            fights_url = f"{self.base_url}/mma-events/{event_id}/{event_slug}/fights"
                            
                            # Extract event date
                            event_date = self.extract_event_date(clean_match)
                            
                            events[clean_match] = {
                                'event_url': f"{self.base_url}/mma-events/{event_id}/{clean_match.lower().replace(' ', '-').replace(':', '')}/",
                                'fights_url': fights_url,
                                'event_id': event_id,
                                'event_name': clean_match,
                                'event_date': event_date
                            }
                            print(f"   ✅ Found UFC event via pattern: {clean_match}")
        
        except Exception as e:
            print(f"   ❌ Error extracting UFC events: {str(e)}")
        
        print(f"   📅 Total events found: {len(events)}")
        return events
    
    def extract_event_fights(self, event_name, fights_url):
        """Extract fight matchups from a specific event"""
        print(f"   🥊 Extracting fights from: {event_name}")
        
        try:
            page_source = self.load_page_with_retry(fights_url)
            if not page_source:
                print(f"      ❌ Failed to load fights page for {event_name}")
                return []
            
            soup = BeautifulSoup(page_source, 'html.parser')
            fights = []
            
            # Define fighter vs fighter patterns
            vs_patterns = [
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+vs\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+VS\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+versus\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            ]
            
            # Look for fight cards/matches
            fight_elements = soup.find_all(['div', 'tr'], class_=re.compile(r'fight|match|card', re.I))
            
            for element in fight_elements:
                fight_text = element.get_text(strip=True)
                
                for pattern in vs_patterns:
                    matches = re.findall(pattern, fight_text)
                    for match in matches:
                        fighter1, fighter2 = match
                        
                        # Clean fighter names
                        fighter1 = self.clean_fighter_name(fighter1)
                        fighter2 = self.clean_fighter_name(fighter2)
                        
                        if fighter1 and fighter2 and len(fighter1) > 2 and len(fighter2) > 2:
                            # Get event date from events data
                            event_date = self.events_data.get(event_name, {}).get('event_date', '')
                            
                            fight_data = {
                                'event_name': event_name,
                                'event_date': event_date,
                                'fighter1': fighter1,
                                'fighter2': fighter2,
                                'fight_url': fights_url,
                                'extraction_date': datetime.now().isoformat()
                            }
                            fights.append(fight_data)
                            print(f"      ✅ Found fight: {fighter1} vs {fighter2}")
            
            # Also look for table-based fight data
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        cell_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                        
                        # Look for vs patterns in table cells
                        for pattern in vs_patterns:
                            matches = re.findall(pattern, cell_text)
                            for match in matches:
                                fighter1, fighter2 = match
                                fighter1 = self.clean_fighter_name(fighter1)
                                fighter2 = self.clean_fighter_name(fighter2)
                                
                                if fighter1 and fighter2 and len(fighter1) > 2 and len(fighter2) > 2:
                                    # Check if this fight is already added
                                    existing = any(f['fighter1'] == fighter1 and f['fighter2'] == fighter2 for f in fights)
                                    if not existing:
                                        # Get event date from events data
                                        event_date = self.events_data.get(event_name, {}).get('event_date', '')
                                        
                                        fight_data = {
                                            'event_name': event_name,
                                            'event_date': event_date,
                                            'fighter1': fighter1,
                                            'fighter2': fighter2,
                                            'fight_url': fights_url,
                                            'extraction_date': datetime.now().isoformat()
                                        }
                                        fights.append(fight_data)
                                        print(f"      ✅ Found fight in table: {fighter1} vs {fighter2}")
            
            print(f"      📊 Total fights found: {len(fights)}")
            return fights
            
        except Exception as e:
            print(f"      ❌ Error extracting fights from {event_name}: {str(e)}")
            return []
    
    def clean_event_name(self, event_text):
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
    
    def extract_event_date(self, event_name):
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
            # UFC Fight Night 257: Walker vs. Zhang (extract the number)
            r'UFC\s+(?:Fight\s+Night\s+)?(\d+):',
            # UFC 320: Ankalaev vs. Pereira 2
            r'UFC\s+(\d+):',
            # Look for dates at the end of event names
            r'(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d+$',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+$'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, event_name, re.IGNORECASE)
            if match:
                date_str = match.group(0).strip()
                
                # Special handling for UFC numbered events
                if 'UFC' in date_str and ':' in date_str:
                    # Extract just the number for UFC events
                    number_match = re.search(r'UFC\s+(?:Fight\s+Night\s+)?(\d+):', date_str, re.IGNORECASE)
                    if number_match:
                        return f"UFC {number_match.group(1)}"
                
                # Clean up the date string
                date_str = re.sub(r'^\d+:\s*', '', date_str)  # Remove leading numbers and colon
                return date_str
        
        return None
    
    def clean_fighter_name(self, fighter_name):
        """Clean fighter name by removing extra text and formatting"""
        if not fighter_name:
            return None
        
        # Remove HTML tags
        clean_name = re.sub(r'<[^>]+>', '', fighter_name)
        
        # Remove extra whitespace
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Remove common unwanted patterns
        unwanted_patterns = [
            r'^\d+\.\s*',  # Remove leading numbers
            r'\s+vs\.?\s+.*$',  # Remove vs and everything after
            r'\s+VS\s+.*$',  # Remove VS and everything after
            r'\s+versus\s+.*$',  # Remove versus and everything after
            r'\s+Odds$',  # Remove "Odds" at the end
            r'[^\w\s\-\.]',  # Remove special characters except spaces, hyphens, dots
        ]
        
        for pattern in unwanted_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        # Clean up any remaining artifacts
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Only return if it looks like a real fighter name
        if len(clean_name) > 2 and len(clean_name) < 50:
            return clean_name
        
        return None
    
    def create_output_files(self):
        """Create CSV and JSON output files"""
        print("\n🔍 Phase 3: Creating Output Files")
        print("-" * 40)
        
        if not self.fights_data:
            print("   ❌ No fight data to export")
            return
        
        # Create CSV file
        csv_file = "MMAFights.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write headers
            headers = ['Event', 'EventDate', 'Fighter1', 'Fighter2', 'FightURL', 'ExtractionDate']
            writer.writerow(headers)
            
            # Write fight data
            for fight in self.fights_data:
                row = [
                    fight['event_name'],
                    fight['event_date'],
                    fight['fighter1'],
                    fight['fighter2'],
                    fight['fight_url'],
                    fight['extraction_date']
                ]
                writer.writerow(row)
        
        # Create JSON file with fresh timestamp
        json_file = "MMAFights.json"
        current_timestamp = datetime.now().isoformat()
        json_data = {
            'extraction_timestamp': current_timestamp,
            'extraction_run_id': f"lulsec_mma_{int(time.time())}",
            'total_fights': len(self.fights_data),
            'total_events': len(self.events_data),
            'events': self.events_data,
            'fights': self.fights_data
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
        
        print(f"   ✅ MMAFights.csv created/updated")
        print(f"   ✅ MMAFights.json created/updated")
        print(f"   📊 Total fights: {len(self.fights_data)}")
        print(f"   📅 Total events: {len(self.events_data)}")
        print(f"   🕐 Extraction timestamp: {current_timestamp}")
        print(f"   🆔 Run ID: lulsec_mma_{int(time.time())}")
    
    def run_scraper(self):
        """Main scraper execution method"""
        print("🏴‍☠️ LulSec MMA Fight Scraper - Hardcore Data Plunder Edition")
        print("=" * 60)
        print("🎯 EXTRACTING UFC EVENTS AND FIGHTS TO MMAFights.csv & .json")
        print("=" * 60)
        
        try:
            # Initialize Chrome driver
            if not self.initialize_driver():
                print("💀 Failed to initialize Chrome driver")
                return False
            
            # Extract UFC events
            self.events_data = self.extract_ufc_events()
            
            if not self.events_data:
                print("❌ No UFC events found")
                return False
            
            # Extract fights from each event
            print("\n🔍 Phase 2: Extracting Fights from Events")
            print("-" * 40)
            
            for event_name, event_data in self.events_data.items():
                fights = self.extract_event_fights(event_name, event_data['fights_url'])
                self.fights_data.extend(fights)
            
            # Create output files
            self.create_output_files()
            
            return True
            
        except KeyboardInterrupt:
            print("\n🛑 Scraping interrupted by user")
            return False
        except Exception as main_error:
            print(f"\n💥 Main scraping error: {str(main_error)}")
            print("   🔧 This might be a network, browser, or parsing issue")
            return False
        finally:
            try:
                if self.driver:
                    self.driver.quit()
                    print("   🔒 Chrome driver closed")
            except Exception as cleanup_error:
                print(f"   ⚠️  Driver cleanup warning: {str(cleanup_error)}")

def main():
    """Main execution function"""
    # Check for debug mode from environment variable
    debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    scraper = MMAFightScraper()
    success = scraper.run_scraper()
    
    if success:
        print(f"\n🎯 FINAL RESULTS:")
        print(f"   Total fights: {len(scraper.fights_data)}")
        print(f"   Total events: {len(scraper.events_data)}")
        print(f"   File: MMAFights.csv")
        print(f"   File: MMAFights.json")
        print(f"   Debug mode: {debug_mode}")
        print("\nFor the lulz! 🏴‍☠️")
    else:
        print(f"\n❌ SCRAPING FAILED")
        print(f"   Debug mode: {debug_mode}")
        print("   Check logs for errors")
        sys.exit(1)

if __name__ == "__main__":
    main() 