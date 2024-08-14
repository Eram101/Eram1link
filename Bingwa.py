import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler
import requests

# Hardcoded bot token for testing purposes
BOT_TOKEN = '6767053413:AAEkzi5j5sitNg5sraQ54PELtsbx6czR8bY'
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Define states for ConversationHandler
OFFER, DURATION, SELECT_OFFER, PHONE = range(4)

# Define offers globally
offers = {
    'data': {
        '24 hours': {'details': ['250MB @Ksh 18', '1GB @Ksh 99']},
        '7 days': {'details': ['350MB @Ksh 49', '2.5GB @Ksh 295', '6GB @Ksh 699']},
        '1 hour': {'details': ['1GB @Ksh 19']},
        '30 days': {'details': ['1.25GB @Ksh 250', '10GB @Ksh 998']},
        'till midnight': {'details': ['1.25GB @Ksh 50']}
    },
    'minutes': {
        'till midnight': {'details': ['50 minutes @Ksh 46']},
        '7 days': {'details': ['200 minutes @Ksh 247']},
        '30 days': {'details': ['300 minutes @Ksh 500', '800 minutes @Ksh 1000']}
    },
    'combined': {
        '30 days': {'details': ['8GB + 400 minutes @Ksh 999']}
    },
    'sms': {
        '24 hours': {'details': ['20 SMS @Ksh 5', '200 SMS @Ksh 10']},
        '7 days': {'details': ['1000 SMS @Ksh 29']},
        '30 days': {'details': ['800 SMS @Ksh 1000']}
    }
}

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
    query.edit_message_text(text=f'You selected the offer: {selected_offer}')
    query.message.reply_text('Please enter your phone number in this format\n 254xxxxxxxxxx:')
    return PHONE

def phone_number(update: Update, context: CallbackContext) -> int:
    phone_number = update.message.text
    context.user_data['phone_number'] = phone_number

    offer_type = context.user_data['offer_type']
    duration = context.user_data['duration']
    selected_index = context.user_data['selected_index']
    selected_offer = offers[offer_type][duration]['details'][int(selected_index)]

    # Extract the amount from the selected offer
    money = selected_offer.split('@Ksh ')[1].split()[0]

    # Send request to stkpush.php with the filled-in $money and $phone
    url = "http://localhost/darajaapi/stkpush.php"  # Replace with your actual URL
    data = {
        'money': money,
        'phone': phone_number
    }
    response = requests.post(url, data=data)

    # Provide feedback to the user
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("ResponseCode") == "0":
            CheckoutRequestID = response_data["CheckoutRequestID"]
            update.message.reply_text('Payment request sent! Please check your phone.')
            
            # Schedule a job to check payment status after 60 seconds
            context.job_queue.run_once(
                check_payment_status, 
                60, 
                context={
                    'chat_id': update.message.chat_id, 
                    'CheckoutRequestID': CheckoutRequestID
                }, 
                name=str(update.message.chat_id)
            )
        else:
            update.message.reply_text('Error initiating payment. Please try again.')
    else:
        update.message.reply_text('Error processing payment. Please try again.')

    return ConversationHandler.END

def check_payment_status(context: CallbackContext):
    chat_id = context.job.context['chat_id']
    CheckoutRequestID = context.job.context['CheckoutRequestID']

    if not CheckoutRequestID:
        context.bot.send_message(chat_id=chat_id, text="No payment to check.")
        return

    # Query the payment status
    url = "http://localhost/darajaapi/query.php"  # Replace with your actual URL
    data = {
        'CheckoutRequestID': CheckoutRequestID
    }
    response = requests.post(url, data=data)

    if response.status_code == 200:
        response_data = response.json()

        # Log the full response data for debugging
        logging.info(f"Payment status response: {response_data}")

        result_code = response_data.get("ResultCode")

        if result_code == '0':
            context.bot.send_message(chat_id=chat_id, text="Payment successful!")
        elif result_code == '1032':
            context.bot.send_message(chat_id=chat_id, text="Transaction canceled by user.")
        elif result_code == '1037':
            context.bot.send_message(chat_id=chat_id, text="Transaction timed out.")
        else:
            context.bot.send_message(chat_id=chat_id, text="Payment failed.")
    else:
        logging.error(f"Error checking payment status: {response.text}")
        context.bot.send_message(chat_id=chat_id, text="Error checking payment status.")
        
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
