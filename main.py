import os
import json
import logging
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

# Load offers from JSON file
with open('offers.json', 'r') as f:
    offers = json.load(f)

updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Define states for ConversationHandler
OFFER, DURATION, SELECT_OFFER, PHONE = range(4)

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
        'Note that this can only be purchased once a day.\n'
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
    query.message.reply_text('Please enter your phone number in this format\n 254xxxxxxxxxx:')
    return PHONE

def phone_number(update: Update, context: CallbackContext) -> int:
    phone_number = update.message.text

    # Ensure the phone number starts with '254'
    if not phone_number.startswith('254'):
        phone_number = '254' + phone_number.lstrip('0')

    context.user_data['phone_number'] = phone_number

    offer_type = context.user_data['offer_type']
    duration = context.user_data['duration']
    selected_index = context.user_data['selected_index']
    selected_offer = context.user_data['selected_offer']

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
            25, 
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
    else:
        update.message.reply_text('Error initiating payment. Please try again.')

    return ConversationHandler.END


def check_payment_status(context: CallbackContext):
    chat_id = context.job.context['chat_id']
    admin_chat_id = os.getenv('ADMIN_CHAT_ID')  # Retrieve admin chat ID from .env
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

    elif result_code == '1032':
        message = (
            f"Transaction canceled by user.\n"
            f"Phone Number: {phone_number}"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}")

    elif result_code == '1037':
        message = (
            f"Transaction timed out.\n"
            f"Phone Number: {phone_number}"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}")

    elif result_code == '1':  # Assuming '1' represents insufficient funds
        message = (
            f"Transaction failed due to insufficient funds.\n"
            f"Phone Number: {phone_number}"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}")

    else:
        message = (
            f"Payment failed.\n"
            f"Phone Number: {phone_number}"
        )
        context.bot.send_message(chat_id=chat_id, text=message)
        context.bot.send_message(chat_id=admin_chat_id, text=f"ADMIN COPY:\n{message}")

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Session canceled. Thank you!')
    return ConversationHandler.END

def main() -> None:
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            OFFER: [CallbackQueryHandler(offer_selection, pattern='^(data|minutes|combined|sms|cancel)$')],
            DURATION: [CallbackQueryHandler(duration_selection)],
            SELECT_OFFER: [CallbackQueryHandler(option_selection)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command, phone_number)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
