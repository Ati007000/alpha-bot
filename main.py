import os
import logging
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
API_TOKEN = os.getenv('API_TOKEN')

# Define command handlers

def start(update, context):
    update.message.reply_text('Hello! Welcome to the Crypto Bot.')


def help_command(update, context):
    update.message.reply_text('Help!')

# Main function to start the bot

def main():
    updater = Updater(API_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('help', help_command))
    
    # Start polling
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
