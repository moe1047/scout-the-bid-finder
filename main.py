from typing import  Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from db.db import DB
from datetime import datetime
from tools.globalTendersScrapper import GlobalTendersScraper
#from tools.website2Scrapper import Website2Scraper
from tools.TelegramTool import TelegramTool
from tools.telegramTemplates.tender1Template import format_tender_message
from os import getenv
load_dotenv()

# ------------------------------------------------------------
# Data Models 
class Tender(BaseModel):
    """Represents a tender with its attributes."""
    id: int = Field(description="Unique identifier for the tender")
    title: str = Field(description="Title of the tender")
    organization: str = Field(description="Organization issuing the tender") 
    posted_date: str = Field(description="Date when tender was posted")
    closing_date: str = Field(description="Deadline for tender submission")
    location: str = Field(description="Geographic location of the tender")
    url: str = Field(description="URL path to tender details")
    source: str = Field(description="Website source of the tender")
    tender_content: str = Field(description="Full content/details of the tender")
    state: str = Field(description="State of the tender")
    is_sent: bool = Field(description="Whether the tender has been sent to the client")

class TenderListing(BaseModel):
    """Collection of tenders."""
    tenders: list[Tender]

class State(TypedDict):
    """Application state definition."""
    human_message: str

# ------------------------------------------------------------
# Language Models Configuration
def initialize_language_models():
    """Initialize and configure language models."""
    return {
        'primary': ChatOpenAI(model="gpt-4o", temperature=0),
    }

# ------------------------------------------------------------
# Prompts
def load_system_prompt() -> str:
    """Load the system prompt from file."""
    with open("prompts/tender_analyst_prompt.md", "r") as file:
        return file.read()

# ------------------------------------------------------------
# Database Operations
class TenderRepository:
    """Handles database operations for tenders."""
    def __init__(self):
        self.db = DB()

    def fetch_waiting_tenders(self, limit: int = 8) -> list[Tender]:
        """Fetch tenders waiting for filtering."""
        try:
            raw_tenders = self.db.get_tenders_by_state("waiting_for_filtering", limit=limit)
            return [self._convert_to_tender(tender) for tender in raw_tenders]
        except Exception as e:
            print(f"[REPOSITORY] Error fetching waiting tenders: {e}")
            return []

    def count_waiting_tenders(self) -> int:
        """Count tenders waiting for filtering.
        
        Returns:
            int: Number of tenders in waiting_for_filtering state
        """
        try:
            return self.db.count_tenders_by_state("waiting_for_filtering")
        except Exception as e:
            print(f"[REPOSITORY] Error counting waiting tenders: {e}")
            return 0

    def update_tender_state(self, tender_id: int, new_state: str) -> None:
        """Update tender state in database."""
        try:
            if not self.db.update_tender_field(tender_id, "state", new_state):
                print(f"[REPOSITORY] Failed to update tender {tender_id} to state {new_state}")
        except Exception as e:
            print(f"[REPOSITORY] Error updating tender state: {e}")

    def insert_new_tender(self, tender_json: dict) -> None:
        """Insert a new tender into the database from a JSON object.
        
        Args:
            tender_json (dict): JSON object containing tender data with keys:
                - title
                - organization
                - posted_date
                - closing_date
                - location
                - url
                - source
                - tender_content
        """
        tender_tuple = (
            tender_json.get('title'),
            tender_json.get('organization'),
            tender_json.get('posted_date'),
            tender_json.get('closing_date'),
            tender_json.get('location'),
            tender_json.get('url'),
            tender_json.get('source'),
            tender_json.get('tender_content'),
        )
        self.db.insert_tender(tender_tuple)

    def tender_exists(self, title: str, posted_date: str) -> bool:
        """Check if a tender with given title and posted date exists.
        
        Args:
            title: The tender title
            posted_date: The tender posted date
            
        Returns:
            bool: True if tender exists, False otherwise
        """
        return self.db.tender_exists(title, posted_date)

    def fetch_qualified_unsent_tenders(self) -> list[Tender]:
        """Fetch qualified tenders that haven't been sent yet."""
        try:
            raw_tenders = self.db.get_tenders_by_state_and_sent(
                state="qualified",
                is_sent=False
            )
            return [self._convert_to_tender(tender) for tender in raw_tenders]
        except Exception as e:
            print(f"[REPOSITORY] Error fetching qualified unsent tenders: {e}")
            return []

    def mark_tender_as_sent(self, tender_id: int) -> None:
        """Mark a tender as sent."""
        try:
            if not self.db.update_tender_field(tender_id, "is_sent", True):
                print(f"[REPOSITORY] Failed to mark tender {tender_id} as sent")
        except Exception as e:
            print(f"[REPOSITORY] Error marking tender as sent: {e}")

    @staticmethod
    def _convert_to_tender(raw_tender: dict) -> Tender:
        """Convert raw database tender to Tender model."""
        return Tender(
            **{
                **raw_tender,
                'posted_date': str(raw_tender.get('posted_date', "")),
                'closing_date': str(raw_tender.get('closing_date', "")),
                'tender_content': str(raw_tender.get('tender_content', ""))
            }
        )
    

# ------------------------------------------------------------
# Workflow Nodes 

def create_tender_filter_node(repo: TenderRepository, llm: ChatOpenAI, system_prompt: str):
    """Create node for filtering tenders."""
    def tender_filter_node(state: State) -> dict:
        # Fetch batch of tenders
        waiting_tenders = repo.fetch_waiting_tenders(limit=8)
        print(f"\n[TENDER FILTER] Processing batch of {len(waiting_tenders)} tenders...")
        
        if not waiting_tenders:
            print("[TENDER FILTER] No tenders to process")
            return state

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["human_message"] + str(waiting_tenders))
        ]

        print("[TENDER FILTER] Invoking LLM for classification...")
        llm_with_structure = llm.with_structured_output(
            TenderListing,
            method="json_schema",
            strict=True
        )

        qualified_tenders = llm_with_structure.invoke(messages)
        print(f"[TENDER FILTER] Found {len(qualified_tenders.tenders)} qualified tenders in this batch")
        
        for tender in waiting_tenders:
            is_qualified = any(qt.id == tender.id for qt in qualified_tenders.tenders)
            new_state = "qualified" if is_qualified else "unqualified"
            repo.update_tender_state(tender.id, new_state)
            print(f"[TENDER FILTER] Tender {tender.id} marked as {new_state}")

        return state
    return tender_filter_node

def should_continue_filtering(state: State) -> Literal["tender_filter", "END"]:
    """Determine if filtering should continue."""
    repo = TenderRepository()
    remaining_tenders = repo.count_waiting_tenders()
    print(f"\n[WORKFLOW] Remaining tenders to process: {remaining_tenders}")
    return "tender_filter" if remaining_tenders > 0 else END

def create_scraper_node(repo: TenderRepository):
    """Create node for scraping tenders from various sources."""
    def scraper_node(state: State) -> dict:
        print("\n[SCRAPER] Starting tender scraping process...")
        
        # Global Tenders Scraping
        try:
            print("[SCRAPER] Initiating scraping from Global Tenders...")
            print("[SCRAPER] This may take several minutes due to wait_time=15 seconds...")
            global_response = GlobalTendersScraper().run({})
            
            if global_response.get('success'):
                scraped_tenders = global_response.get('tenders', [])
                print(f"[SCRAPER] Successfully scraped {len(scraped_tenders)} tenders from Global Tenders")
                process_scraped_tenders(repo, scraped_tenders)
            else:
                print("[SCRAPER] Global Tenders scraping failed")
                
        except Exception as e:
            print(f"[SCRAPER] Error during Global Tenders scraping: {str(e)}")
        
        # Website 2 Scraping
        '''
        try:
            print("\n[SCRAPER] Initiating scraping from Website 2...")
            website2_response = Website2Scraper().run({
                "limit": 20,
                "offset": 0
            })
            
            if website2_response.get('success'):
                website2_tenders = website2_response.get('tenders', [])
                print(f"[SCRAPER] Successfully scraped {len(website2_tenders)} tenders from Website 2")
                process_scraped_tenders(repo, website2_tenders)
            else:
                print("[SCRAPER] Website 2 scraping failed")
                
        except Exception as e:
            print(f"[SCRAPER] Error during Website 2 scraping: {str(e)}")

        '''

            
        return state

    def process_scraped_tenders(repo: TenderRepository, tenders: list) -> None:
        """Process and store scraped tenders."""
        new_tenders = 0
        for tender in tenders:
            if not is_valid_date(tender.get('posted_date')):
                print(f"[SCRAPER] Invalid posted_date found: {tender.get('posted_date')}")
                tender['posted_date'] = ''
            if not is_valid_date(tender.get('closing_date')):
                print(f"[SCRAPER] Invalid closing_date found: {tender.get('closing_date')}")
                tender['closing_date'] = ''
            
            if not repo.tender_exists(tender['title'], tender['posted_date']):
                repo.insert_new_tender(tender)
                new_tenders += 1
        
        print(f"[SCRAPER] Added {new_tenders} new tenders to database")
        
    return scraper_node

def is_valid_date(date_str: str) -> bool:
    """Check if a string represents a valid date."""
    if not date_str:
        return False
    try:
        
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def create_notification_node(repo: TenderRepository, telegram_tool: TelegramTool):
    """Create node for sending notifications about qualified tenders."""
    def notification_node(state: State) -> dict:
        print("\n[NOTIFIER] Starting tender notification process...")
        
        # Step 1: Fetch qualified, unsent tenders
        try:
            qualified_tenders = repo.fetch_qualified_unsent_tenders()
            print(f"[NOTIFIER] Found {len(qualified_tenders)} qualified tenders to notify")
            
            if not qualified_tenders:
                print("[NOTIFIER] No new qualified tenders to notify")
                return state
            
            # Step 2: Format and send notifications
            _send_tender_notifications(qualified_tenders, repo, telegram_tool)
            
        except Exception as e:
            print(f"[NOTIFIER] Error in notification process: {str(e)}")
        
        return state
    
    return notification_node

def _send_tender_notifications(tenders: list, repo: TenderRepository, telegram_tool: TelegramTool) -> None:
    """Format and send notifications for each tender."""
    chat_id = getenv('TELEGRAM_CHAT_ID')
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID environment variable is not set")
    
    for tender in tenders:
        try:
            # Format tender message
            formatted_message = format_tender_message(tender)
            
            # Send message through Telegram
            print(f"[NOTIFIER] Sending notification for tender: {tender.id}")
            result = telegram_tool.run({
                "message": formatted_message,
                "chat_id": chat_id
            })
            
            if result['success']:
                print(f"[NOTIFIER] Successfully sent notification for tender {tender.id}")
                # Update is_sent status in database using mark_tender_as_sent
                repo.mark_tender_as_sent(tender.id)  # Use the correct method
                print(f"[NOTIFIER] Marked tender {tender.id} as sent")
            else:
                print(f"[NOTIFIER] Failed to send notification for tender {tender.id}: {result.get('error')}")
                
        except Exception as e:
            print(f"[NOTIFIER] Error processing tender {tender.id}: {str(e)}")

# ------------------------------------------------------------
# Workflow Configuration
def create_workflow():
    """Create and configure the workflow."""
    models = initialize_language_models()
    system_prompt = load_system_prompt()
    repo = TenderRepository()
    
    # Get bot token from environment variable
    telegram_bot_token = getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
        
    telegram_tool = TelegramTool(bot_token=telegram_bot_token)

    workflow = StateGraph(State)
    
    workflow.add_node("scraper", create_scraper_node(repo))
    workflow.add_node("tender_filter", create_tender_filter_node(repo, models['primary'], system_prompt))
    workflow.add_node("notifier", create_notification_node(repo, telegram_tool))
    
    # Update workflow edges
    workflow.add_edge("scraper", "tender_filter")
    workflow.add_conditional_edges(
        "tender_filter",
        should_continue_filtering,
        {
            "tender_filter": "tender_filter",
            END: "notifier"
        }
    )
    workflow.add_edge("notifier", END)
    
    workflow.set_entry_point("scraper")
    return workflow.compile()

# ------------------------------------------------------------
# Main Execution
if __name__ == "__main__":
    print("\n[MAIN] Starting tender processing workflow...")
    app = create_workflow()
    initial_state = {
        "human_message": """ 
        
        find tenders related to Technology services. 
        
        TECH FOCUS: 
        - Software development/implementation 
        - Enterprise systems (ERP, CRM) 
        - AI solutions 
        - Digital transformation services 
        - Management system 
        
        Exclusion Criteria: 
        - Non-tech related services 
        - Hardware-only procurement 
        - Basic IT support 
        - Below minimum budget threshold
        """
        
    }
    results = app.invoke(initial_state)

    print("\n[MAIN] Workflow completed successfully")
    print(results)