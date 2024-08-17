import os
import json
import logging
import re
import csv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler
from dotenv import load_dotenv

# Import functions from stkpush.py and query.py
from stkpush import process_stkpush  # Replace with the actual function name
from query import query_payment_status  # Updated function name

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

# Load offers from JSON file
with open('offers.json', 'r') as f:
    offers = json.load(f)

updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Define states for ConversationHandler
OFFER, DURATION, SELECT_OFFER, PHONE = range(4)

# Initialize the CSV file
CSV_FILE = 'transactions.csv'

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['phone', 'offer', 'duration', 'status', 'timestamp'])

init_csv()

# Function to validate phone number
def validate_phone_number(phone_number: str) -> bool:
    pattern = re.compile(r'^2547\d{8}$')
    return pattern.match(phone_number) is not None

# Function to insert a transaction record
def insert_transaction(phone, offer, duration, status):
    with open(CSV_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([phone, offer, duration, status, datetime.now()])

# Function to check rate limiting
def check_rate_limit(phone):
    with open(CSV_FILE, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if (row['phone'] == phone and 
                row['status'] == 'successful' and 
                datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S.%f') >= datetime.now() - timedelta(days=1)):
                return True
    return False

def start(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [InlineKeyboardButton("Data", callback_data='data')],
        [InlineKeyboardButton("Minutes", callback_data='minutes')],
        [InlineKeyboardButton("Data+Minutes", callback_data='combined')],
        [InlineKeyboardButton("Sms", callback_data='sms')],
        [InlineKeyboardButton("Cancel", callback_data='cancel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        'Hello! Welcome to Bingwa Sokoni Offers.\n'
        'Note that this can only be purchased once a day per phone number.\n'
        'Which offer would you like?', 
        reply_markup=reply_markup
    )
    return OFFER

def offer_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == 'cancel':
        query.edit_message_text(text="Thank you! The session has been canceled.")
        return ConversationHandler.END

    context.user_data['offer_type'] = query.data
    options = {
        'data': ['24 hours', '7 days', '1 hour', '30 days', 'till midnight'],
        'minutes': ['till midnight', '7 days', '30 days'],
        'combined': ['30 days'],
        'sms': ['24 hours', '7 days', '30 days'],
    }
    keyboard = [[InlineKeyboardButton(option, callback_data=f'{query.data}:{option}')] for option in options.get(query.data, [])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=f'Great choice! Please select the duration for your {query.data} offer:', reply_markup=reply_markup)
    return DURATION

def duration_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    offer_type, duration = query.data.split(':')
    context.user_data['offer_type'] = offer_type
    context.user_data['duration'] = duration

    selected_offers = offers.get(offer_type, {}).get(duration, {'details': ['Offer not available']})

    keyboard = [[InlineKeyboardButton(detail, callback_data=f'{offer_type}:{duration}:{index}')] for index, detail in enumerate(selected_offers['details'])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=f'You selected {duration}. Please select an offer:', reply_markup=reply_markup)
    return SELECT_OFFER

def option_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    offer_type, duration, selected_index = query.data.split(':')
    context.user_data['offer_type'] = offer_type
    context.user_data['duration'] = duration
    context.user_data['selected_index'] = selected_index

    selected_offer = offers[offer_type][duration]['details'][int(selected_index)]
    context.user_data['selected_offer'] = selected_offer
    query.edit_message_text(text=f'You selected the offer: {selected_offer}')
    query.message.reply_text('Please enter your phone number:')
    return PHONE

def phone_number(update: Update, context: CallbackContext) -> int:
    phone_number = update.message.text

    if not validate_phone_number(phone_number):
        update.message.reply_text('Invalid phone number. Please enter a valid number starting with 2547.')
        return PHONE

    context.user_data['phone_number'] = phone_number
    offer_type = context.user_data['offer_type']
    duration = context.user_data['duration']
    selected_offer = context.user_data['selected_offer']

    # Check rate limiting
    if check_rate_limit(phone_number):
        update.message.reply_text('You have already subscribed to an offer today with this number. Please try again tomorrow.')
        return ConversationHandler.END

    # Extract the amount from the selected offer
    money = selected_offer.split('@Ksh ')[1].split()[0]

    # Call the function from stkpush.py directly
    response_data = process_stkpush(money, phone_number)

    # Provide feedback to the user
    if response_data.get("ResponseCode") == "0":
        CheckoutRequestID = response_data["CheckoutRequestID"]
        update.message.reply_text('Payment request sent! Please check your phone.')
        
        # Schedule a job to check payment status after 25 seconds
        context.job_queue.run_once(
            check_payment_status, 
            35, 
            context={
                'chat_id': update.message.chat_id, 
                'CheckoutRequestID': CheckoutRequestID,
                'offer_type': offer_type,
                'duration': duration,
                'selected_offer': selected_offer,
                'phone_number': phone_number,
            }, 
            name=str(update.message.chat_id)
        )
        
        # Insert the transaction into the CSV file
        insert_transaction(phone_number, offer_type, duration, 'pending')

    else:
        update.message.reply_text('Error initiating payment. Please try again.')

    return ConversationHandler.END

def check_payment_status(context: CallbackContext):
    chat_id = context.job.context['chat_id']
    admin_chat_id = ADMIN_CHAT_ID  # Retrieve admin chat ID from .env
    CheckoutRequestID = context.job.context['CheckoutRequestID']
    offer_type = context.job.context['offer_type']
    duration = context.job.context['duration']
    selected_offer = context.job.context['selected_offer']
    phone_number = context.job.context['phone_number']

    if not CheckoutRequestID:
        context.bot.send_message(chat_id=chat_id, text="No payment to check.")
        return

    # Call the function from query.py directly
    response_data = query_payment_status(CheckoutRequestID)

    # Log the full response data for debugging
    logging.info(f"Payment status response: {response_data}")

    result_code = response_data.get("ResultCode")

    if result_code == '0':
        message = (
            f"Payment successful!\n"
            f"Package: {selected_offer}\n"
            f"Duration: {duration}\n"
            f"Phone Number: {phone_number}\n"
            f"Use Till {MPESA_SHORTCODE} for offline transactions\n"
            f"======================\n"
            f"Thank you!"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}\nUser Phone Number: {phone_number}")

        # Update the transaction status in the CSV file
        insert_transaction(phone_number, offer_type, duration, 'successful')

    elif result_code == '1032':
        message = (
            f"Transaction canceled by user.\n"
            f"Phone Number: {phone_number}"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}")

        # Update the transaction status in the CSV file
        insert_transaction(phone_number, offer_type, duration, 'canceled')

    elif result_code == '1':
        message = (
            f"Payment failed or was not completed. Try again.\n"
            f"Phone Number: {phone_number}"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}")

        # Update the transaction status in the CSV file
        insert_transaction(phone_number, offer_type, duration, 'failed')

    else:
        context.bot.send_message(chat_id=chat_id, text="Unexpected error. Contact support.")

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Thank you! The session has been canceled.')
    return ConversationHandler.END

# Conversation handler for the bot
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        OFFER: [CallbackQueryHandler(offer_selection)],
        DURATION: [CallbackQueryHandler(duration_selection)],
        SELECT_OFFER: [CallbackQueryHandler(option_selection)],
        PHONE: [MessageHandler(Filters.text & ~Filters.command, phone_number)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

dispatcher.add_handler(conv_handler)

# Start the bot
updater.start_polling()
updater.idle()
