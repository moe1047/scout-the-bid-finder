import requests
from typing import Dict, Type, Optional, ClassVar
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
import logging
from datetime import datetime

class ReliefWebInput(BaseModel):
    """Input for ReliefWeb API scraper."""
    limit: int = Field(
        default=20,
        description="Number of items to fetch per request"
    )
    offset: int = Field(
        default=0,
        description="Starting point for pagination"
    )

class ReliefWebScraper(BaseTool):
    """Tool for fetching tender information from ReliefWeb API."""
    name: str = "reliefweb_scraper"
    description: str = """Useful for fetching tender information from ReliefWeb API.
    Returns a list of tenders with their titles, organizations, dates, and URLs.
    Use this when you need to gather information about current tenders in Somalia."""
    args_schema: Type[BaseModel] = ReliefWebInput
    
    BASE_URL: ClassVar[str] = "https://api.reliefweb.int/v1/jobs"
    headers: ClassVar[Dict[str, str]] = {
        "User-Agent": "scout-bot/1.0",
        "Accept": "application/json"
    }

    def _create_payload(self, limit: int, offset: int) -> Dict:
        """Create the API request payload."""
        return {
            "offset": offset,
            "limit": limit,
            "filter": {
                "conditions": [
                    {
                        "field": "type.id",
                        "value": "264"
                    },
                    {
                        "field": "country.id",
                        "value": "216"
                    }
                ],
                "operator": "AND"
            },
            "preset": "latest",
            "profile": "list"
        }

    def _format_tender(self, item: Dict) -> Dict:
        """Format API response item into standardized tender format."""
        fields = item.get('fields', {})
        
        # Extract dates
        dates = fields.get('date', {})
        closing_date = dates.get('closing', '')
        created_date = dates.get('created', '')
        
        # Format dates to YYYY-MM-DD
        if closing_date:
            closing_date = closing_date.split('T')[0]
        if created_date:
            created_date = created_date.split('T')[0]
            
        # Extract source organization
        source = fields.get('source', [{}])[0].get('name', '')
        
        return {
            "title": fields.get('title', '').lower(),
            "organization": source.lower(),
            "posted_date": created_date,
            "closing_date": closing_date,
            "location": "Somalia",  # Default as per API filter
            "url": fields.get('url', ''),
            "source": "reliefweb.int",
            "tender_content": fields.get('title', '')  # Using title as content since API doesn't provide full description
        }

    def _run(
        self,
        limit: int = 20,
        offset: int = 0,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> Dict:
        """Run the tool."""
        try:
            payload = self._create_payload(limit, offset)
            
            response = requests.post(
                self.BASE_URL,
                json=payload,
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('data'):
                return {
                    'success': False,
                    'error': 'No data returned from API'
                }
            
            tenders = []
            for item in data['data']:
                tender = self._format_tender(item)
                tenders.append(tender)
            
            return {
                'success': True,
                'items_found': len(tenders),
                'tenders': tenders
            }
            
        except requests.exceptions.RequestException as e:
            logging.error(f"API request error: {str(e)}")
            return {
                'success': False,
                'error': f"API request failed: {str(e)}"
            }
        except Exception as e:
            logging.error(f"Error processing data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _arun(self, limit: int = 20, offset: int = 0) -> Dict:
        """Run the tool asynchronously."""
        raise NotImplementedError("ReliefWebScraper does not support async")

# Example usage
if __name__ == "__main__":
    scraper = ReliefWebScraper()
    try:
        # Create input dictionary matching the schema
        tool_input = {
            "limit": 20,
            "offset": 0
        }
        result = scraper.run(tool_input)
        if result['success']:
            print(f"\nSuccessfully fetched {result['items_found']} tenders!")
            print("\nFetched Data:")
            import json
            print(json.dumps(result['tenders'], indent=2, ensure_ascii=False))
        else:
            print("Error:", result.get('error', 'Unknown error'))
    except Exception as e:
        print(f"Error: {str(e)}")
