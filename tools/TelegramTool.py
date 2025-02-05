from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type
from langchain.callbacks.manager import CallbackManagerForToolRun
from telegram import Bot
import asyncio
import logging
from datetime import datetime
"""
Step-by-Step Guide to Set Up and Configure Your Telegram Bot:

1. **Create a New Bot:**
   - Open Telegram and search for "BotFather".
   - Start a chat with BotFather and send the command `/newbot`.
   - Follow the prompts to set your bot's name and username.
   - After creation, BotFather will provide a unique token. Save this token securely.

2. **Configure Bot to Allow Group Messages:**
   - In the chat with BotFather, send the command `/setprivacy`.
   - Select your bot from the list of bots you own.
   - Choose the option to disable privacy mode. This setting allows your bot to receive all messages in group chats.

3. **Access Bot Updates:**
   - Use the following URL to access updates, replacing `<bot_token>` with your bot's token:
     `https://api.telegram.org/bot<bot_token>/getUpdates`
   - This URL will return the latest updates sent to your bot, including messages and commands.
"""


class TelegramInput(BaseModel):
    """Input for Telegram message sender."""
    message: str = Field(
        description="Message to be sent through Telegram"
    )
    chat_id: str = Field(
        description="Telegram chat ID where the message will be sent"
    )

class TelegramTool(BaseTool):
    """Tool for sending messages through Telegram."""
    name: str = "telegram_sender"
    description: str = """Useful for sending messages through Telegram.
    Requires a message and a chat ID. Returns success status and message details."""
    args_schema: Type[BaseModel] = TelegramInput
    bot: Bot = None
    
    def __init__(self, bot_token: str):
        """Initialize the Telegram bot with the provided token."""
        super().__init__()
        self.bot = Bot(token=bot_token)
        
    def _run(
        self,
        message: str,
        chat_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        """Run the tool synchronously."""
        try:
            # Get the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(self._send_message(message, chat_id))
            return result
            
        except Exception as e:
            logging.error(f"Error sending Telegram message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def _send_message(self, message: str, chat_id: str) -> dict:
        """Send message through Telegram bot."""
        try:
            # Send the message
            async with self.bot:
                sent_message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='HTML'  # Supports HTML formatting
                )
            
            return {
                'success': True,
                'message_id': sent_message.message_id,
                'chat_id': chat_id,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error sending Telegram message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def _arun(
        self,
        message: str,
        chat_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> dict:
        """Run the tool asynchronously."""
        return await self._send_message(message, chat_id)
