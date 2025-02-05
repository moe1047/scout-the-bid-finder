from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from typing import Dict, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
import logging
import json
import time
from typing import Optional
from fake_useragent import UserAgent
import random
from datetime import datetime, timedelta

class SomaliJobsInput(BaseModel):
    """Input for SomaliJobs scraper."""
    url: str = Field(
        default="https://somalijobs.com/tenders",
        description="URL to scrape. Defaults to SomaliJobs tenders page"
    )
    min_items: int = Field(
        default=30,
        description="Minimum number of items to scrape before stopping"
    )
    wait_time: int = Field(
        default=5,
        description="Maximum time to wait for elements to load (seconds)"
    )

class SomaliJobsScraper(BaseTool):
    """Tool for scraping tender information from SomaliJobs."""
    name: str = "somalijobs_scraper"
    description: str = """Useful for scraping tender information from SomaliJobs website.
    Returns a list of tenders with their titles, advertisers, dates, locations, and URLs.
    Use this when you need to gather information about current tenders in Somalia."""
    args_schema: Type[BaseModel] = SomaliJobsInput
    
    # Add class attributes for Pydantic
    chrome_options: Options
    
    def __init__(self):
        # Generate random user agent
        ua = UserAgent()
        user_agent = ua.random
        
        # Set up Chrome options for headless browsing with enhanced privacy
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--enable-javascript')
        
        # Privacy-focused options
        chrome_options.add_argument(f'user-agent={user_agent}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--incognito')  # Use incognito mode
        chrome_options.add_argument('--disable-plugins-discovery')
        chrome_options.add_argument('--disable-bundled-ppapi-flash')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-translate')
        #chrome_options.add_argument('--proxy-server=socks5://your-proxy-address:port')
        
        # Initialize parent class with our attributes
        super().__init__(chrome_options=chrome_options)

    def _run(
        self, 
        url: str = "https://somalijobs.com/tenders",
        min_items: int = 40,
        wait_time: int = 15,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> Dict:
        """Run the tool."""
        driver = None
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(url)
            
            # Wait for initial content to load
            time.sleep(5)
            
            # Wait for the container to be present
            wait = WebDriverWait(driver, wait_time)
            container = wait.until(EC.presence_of_element_located((By.ID, "tenders-listing-data-container")))
            
            # Keep track of the number of items
            last_count = 0
            attempts = 0
            max_attempts = 20  # Increased from 10 to 20
            
            while attempts < max_attempts:
                # Scroll multiple times with small delays
                for _ in range(3):  # Scroll 3 times before checking
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Wait for content to load
                
                items = driver.find_elements(By.CLASS_NAME, "jobs-listing-container")
                current_count = len(items)
                
                if current_count >= min_items:
                    if run_manager:
                        run_manager.on_text(f"Found {current_count} items - target reached!")
                    break
                
                if current_count == last_count:
                    attempts += 1
                    if run_manager:
                        run_manager.on_text(f"No new items loaded. Attempt {attempts} of {max_attempts}")
                else:
                    attempts = 0  # Reset attempts if we found new items
                    
                last_count = current_count
                
                # Add random delay between scrolls
                time.sleep(random.uniform(2, 4))
                
                if run_manager:
                    run_manager.on_text(f"Currently loaded items: {current_count}")
            
            html_content = container.get_attribute('outerHTML')
            #print("HTML content:")
            #print(html_content)
            tenders_data = self._html_to_json(html_content)
            
            return {
                'success': True,
                'items_found': current_count,
                'tenders': tenders_data
            }
            
        except Exception as e:
            logging.error(f"Error scraping URL: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if driver:
                driver.quit()

    async def _arun(self, url: str, min_items: int = 30, wait_time: int = 10) -> Dict:
        """Run the tool asynchronously."""
        raise NotImplementedError("SomaliJobsScraper does not support async")

    def _html_to_json(self, html_content: str) -> list:
        """Converts HTML content to structured JSON data."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tenders = []
            base_url = "https://somalijobs.com"
            
            def convert_date(date_str: str) -> str:
                """Convert various date formats to YYYY-MM-DD."""
                today = datetime.now()
                
                try:
                    if date_str.lower() == 'today':
                        return today.strftime('%Y-%m-%d')
                    elif date_str.lower() == 'yesterday':
                        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
                    else:
                        # Handle "Jan, 28" format
                        # If the month is from a previous year, adjust the year accordingly
                        date_parts = date_str.replace(',', '').split()
                        if len(date_parts) == 2:
                            month, day = date_parts
                            parsed_date = datetime.strptime(f"{month} {day}", "%b %d")
                            # Set the year
                            current_month = today.month
                            parsed_month = parsed_date.month
                            
                            # If the parsed month is ahead of current month, it must be from previous year
                            year = today.year if parsed_month <= current_month else today.year - 1
                            return datetime(year, parsed_date.month, parsed_date.day).strftime('%Y-%m-%d')
                        
                        return date_str  # Return original if format is not recognized
                except Exception as e:
                    logging.error(f"Error converting date {date_str}: {str(e)}")
                    return date_str
            
            listings = soup.find_all('a', class_='jobs-listing-container')
            
            for listing in listings:
                tender = {
                    "title": "",
                    "organization": "",
                    "posted_date": "",
                    "closing_date": "",
                    "location": "",
                    "url": "",
                    "source": "somalijobs.com",
                    "tender_content": ""
                }
                
                title_elem = listing.find('h2', class_='jobs-listing-title')
                if title_elem:
                    tender['title'] = title_elem.text.strip().lower()
                
                company_elem = listing.find('div', class_='jobs-listing-card').find('span', class_='uppercase')
                if company_elem:
                    tender['organization'] = company_elem.text.strip().lower()
                
                cards = listing.find_all('div', class_='jobs-listing-card')
                for card in cards:
                    span_text = card.find('span').text.strip()
                    
                    if any(month in span_text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Today', 'Yesterday']):
                        tender['posted_date'] = convert_date(span_text)
                    elif span_text != tender.get('organization', ''):
                        tender['location'] = span_text
                
                relative_url = listing.get('href', '')
                if relative_url:
                    tender['url'] = base_url + relative_url
                
                tenders.append(tender)
            
            return tenders
            
        except Exception as e:
            logging.error(f"Error converting HTML to JSON: {str(e)}")
            return []

# Example usage
if __name__ == "__main__":
    scraper = SomaliJobsScraper()
    try:
        # Create input dictionary matching the schema
        tool_input = {
            "url": "https://somalijobs.com/tenders",
            "min_items": 30,
            "wait_time": 15
        }
        result = scraper.run(tool_input)
        if result['success']:
            print(f"\nSuccessfully scraped {result['items_found']} tenders!")
            print("\nScraped Data:")
            print(json.dumps(result['tenders'], indent=2, ensure_ascii=False))
        else:
            print("Error:", result.get('error', 'Unknown error'))
    except Exception as e:
        print(f"Error: {str(e)}")