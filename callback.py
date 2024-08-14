from flask import Flask, request, jsonify
import json
from dbconnection import create_connection  # Import the function from dbconnection.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

@app.route('/callback', methods=['POST'])
def callback():
    # Read the incoming JSON data
    stk_callback_response = request.get_data(as_text=True)

    # Log the response to a file
    with open('Mpesastkresponse.json', 'a') as log_file:
        log_file.write(stk_callback_response + '\n')

    # Parse the JSON data
    data = json.loads(stk_callback_response)
    
    # Extract required fields
    body = data.get('Body', {})
    stk_callback = body.get('stkCallback', {})
    merchant_request_id = stk_callback.get('MerchantRequestID')
    checkout_request_id = stk_callback.get('CheckoutRequestID')
    result_code = stk_callback.get('ResultCode')
    result_desc = stk_callback.get('ResultDesc')
    callback_metadata = stk_callback.get('CallbackMetadata', {})
    items = callback_metadata.get('Item', [])
    
    # Extract relevant fields from items
    amount = next((item['Value'] for item in items if item['Id'] == 1), None)
    transaction_id = next((item['Value'] for item in items if item['Id'] == 2), None)
    user_phone_number = next((item['Value'] for item in items if item['Id'] == 4), None)
    
    # Check if the transaction was successful
    if result_code == 0:
        # Store the transaction details in the database
        conn = create_connection()
        if conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO transactions 
                (MerchantRequestID, CheckoutRequestID, ResultCode, Amount, MpesaReceiptNumber, PhoneNumber) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (merchant_request_id, checkout_request_id, result_code, amount, transaction_id, user_phone_number)
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()
        else:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500

    return jsonify({"status": "success", "message": "Callback processed successfully"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
