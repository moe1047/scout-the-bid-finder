from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from typing import Dict, Type, Optional
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
import logging
import time
from fake_useragent import UserAgent
from datetime import datetime

class GlobalTendersInput(BaseModel):
    """Input for GlobalTenders scraper."""
    url: str = Field(
        default="https://www.globaltenders.com/free-global-tenders/",
        description="URL to scrape. Defaults to GlobalTenders free tenders page"
    )
    wait_time: int = Field(
        default=10,
        description="Maximum time to wait for elements to load (seconds)"
    )

class GlobalTendersScraper(BaseTool):
    """Tool for scraping tender information from GlobalTenders."""
    name: str = "globaltenders_scraper"
    description: str = """Useful for scraping tender information from GlobalTenders website.
    Returns a list of tenders with their titles, organizations, dates, and URLs."""
    args_schema: Type[BaseModel] = GlobalTendersInput
    
    # Add chrome_options as a class field
    chrome_options: Options = Field(default_factory=Options)
    
    def __init__(self):
        # Initialize parent class first
        super().__init__()
        
        # Generate random user agent
        ua = UserAgent()
        user_agent = ua.random
        
        # Configure Chrome options
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument(f'user-agent={user_agent}')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument('--incognito')

    def _convert_date(self, date_str: str) -> str:
        """Convert date string to YYYY-MM-DD format."""
        try:
            date_obj = datetime.strptime(date_str.strip(), "%d %b %Y")
            return date_obj.strftime("%Y-%m-%d")
        except Exception as e:
            logging.error(f"Error converting date {date_str}: {str(e)}")
            return date_str

    def _parse_tender_row(self, row) -> Dict:
        """Parse a single tender row and return structured data."""
        tender = {
            "title": "",
            "organization": "",
            "posted_date": "",
            "closing_date": "",
            "location": "",
            "url": "",
            "source": "globaltenders.com",
            "tender_content": ""
        }
        
        try:
            # Find all key-value pairs in the row
            divs = row.find_all('div', class_='row')[0].find_all('div')
            data = {}
            
            # Extract key-value pairs
            for i in range(0, len(divs)-2, 2):
                key = divs[i].text.strip().rstrip(':').lower()
                value = divs[i+1].text.strip().lower()
                data[key] = value
            
            # Map the data to our tender format
            tender["title"] = data.get("description", "")
            tender["organization"] = data.get("authority", "")
            tender["location"] = data.get("country", "")
            
            # Handle the closing date
            if "action deadline" in data:
                tender["closing_date"] = self._convert_date(data["action deadline"])
            
            # Get the URL if available
            url_element = row.find('a', class_='btn-sdetail')
            if url_element:
                tender["url"] = url_element.get('href', '')
            
            # Combine relevant information for tender_content
            tender["tender_content"] = f"{data.get('description', '')} - {data.get('notice type', '')}"
            
        except Exception as e:
            logging.error(f"Error parsing tender row: {str(e)}")
        
        return tender

    def _run(
        self,
        url: str = "https://www.globaltenders.com/free-global-tenders/",
        wait_time: int = 10,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> Dict:
        """Run the tool."""
        driver = None
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(url)
            
            # Wait for the table to be present
            wait = WebDriverWait(driver, wait_time)
            table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "gt-table")))
            
            # Get the page source after JavaScript has loaded
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all tender rows
            tender_rows = soup.find_all('tr', id=lambda x: x and x.startswith('tender_GT'))
            
            tenders = []
            for row in tender_rows:
                tender = self._parse_tender_row(row)
                if tender["title"]:  # Only add if we have at least a title
                    tenders.append(tender)
            
            return {
                'success': True,
                'items_found': len(tenders),
                'tenders': tenders
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

    async def _arun(self, url: str, wait_time: int = 10) -> Dict:
        """Run the tool asynchronously."""
        raise NotImplementedError("GlobalTendersScraper does not support async")

# Example usage
if __name__ == "__main__":
    scraper = GlobalTendersScraper()
    try:
        tool_input = {
            "url": "https://www.globaltenders.com/free-global-tenders/",
            "wait_time": 10
        }
        result = scraper.run(tool_input)
        if result['success']:
            print(f"\nSuccessfully scraped {result['items_found']} tenders!")
            print("\nScraped Data:")
            import json
            print(json.dumps(result['tenders'], indent=2, ensure_ascii=False))
        else:
            print("Error:", result.get('error', 'Unknown error'))
    except Exception as e:
        print(f"Error: {str(e)}")