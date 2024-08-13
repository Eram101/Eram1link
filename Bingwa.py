from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
updater = Updater(token='6767053413:AAEkzi5j5sitNg5sraQ54PELtsbx6czR8bY', use_context=True)
dispatcher = updater.dispatcher

# Define states for ConversationHandler
OFFER, DURATION, SELECT_OFFER, PHONE = range(4)

# Define offers globally
offers = {
    'data': {
        '3 hours': {'id': 1, 'details': ['1.5GB @Ksh 50']},
        '7 days': {'id': 2, 'details': ['350MB @Ksh 49', '2.5GB @Ksh 295', '6GB @Ksh 699']},
        '1 hour': {'id': 3, 'details': ['1GB @Ksh 19']},
        '24 hours': {'id': 4, 'details': ['250MB @Ksh 18', '1GB @Ksh 99']},
        'till midnight': {'id': 5, 'details': ['1.25GB @Ksh 55']}
    },
    'minutes': {
        '1 hour': {'id': 6, 'details': ['1GB @Ksh 19']},
        '48 hours': {'id': 7, 'details': ['400 minutes @Ksh 50']}
    },
    'combined': {
        '30 days': {'id': 8, 'details': ['8GB+400 minutes @Ksh 1000']},
        '7 days': {'id': 9, 'details': ['2GB+100 minutes @Ksh 300']}
    },
    'sms': {
        '1 day': {'id': 10, 'details': ['20 SMS @Ksh 5', '200 SMS @Ksh 10']},
        '7 days': {'id': 11, 'details': ['1000 SMS @Ksh 29']},
        '30 days': {'id': 12, 'details': ['1500 SMS @Ksh 96', '3500 SMS @Ksh 198']}
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
    update.message.reply_text('Hello! Welcome to Bingwa Sokoni Offers.\nNote that this can only be purchased once a day.\nWhich offer would you like?', reply_markup=reply_markup)
    return OFFER

def offer_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == 'cancel':
        query.edit_message_text(text="Thank you! The session has been canceled.")
        return ConversationHandler.END

    context.user_data['offer_type'] = query.data
    options = {
        'data': ['3 hours', '7 days', '1 hour', '24 hours', 'till midnight'],
        'minutes': ['1 hour', '48 hours'],
        'combined': ['30 days', '7 days'],
        'sms': ['1 day', '7 days', '30 days'],
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

    keyboard = [[InlineKeyboardButton(f"{detail} (ID: {offers[offer_type][duration]['id']})", callback_data=f'{offer_type}:{duration}:{offers[offer_type][duration]["id"]}')] for detail in selected_offers['details']]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=f'You selected {duration}. Please select an offer:', reply_markup=reply_markup)
    return SELECT_OFFER

def option_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    offer_type, duration, offer_id = query.data.split(':')
    context.user_data['offer_type'] = offer_type
    context.user_data['duration'] = duration
    context.user_data['offer_id'] = offer_id

    selected_offer = query.message.text.split('\n')[0].replace('You selected the offer: ', '')
    query.edit_message_text(text=f'You selected the offer: {selected_offer}')
    query.message.reply_text('Please enter your phone number:')
    return PHONE

def phone_number(update: Update, context: CallbackContext) -> int:
    phone_number = update.message.text
    context.user_data['phone_number'] = phone_number

    offer_type = context.user_data['offer_type']
    duration = context.user_data['duration']
    offer_id = context.user_data['offer_id']
    selected_offer = [o for o in offers[offer_type][duration]['details'] if str(offers[offer_type][duration]['id']) == offer_id][0]

    update.message.reply_text(f'Thank you! Here is your summary:\n'
                              f'Offer Type: {offer_type}\n'
                              f'Duration: {duration}\n'
                              f'Offer: {selected_offer}\n'
                              f'Phone Number: {phone_number}')
    return ConversationHandler.END

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
