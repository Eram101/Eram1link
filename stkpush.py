import requests
from requests.auth import HTTPBasicAuth
import base64
import os
import json
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# M-Pesa credentials
consumer_key = os.getenv("MPESA_CONSUMER_KEY")
consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
business_shortcode = os.getenv("MPESA_SHORTCODE")
lipa_na_mpesa_passkey = os.getenv("MPESA_PASSKEY")
callback_url = os.getenv("MPESA_CALLBACK_URL")

# Access token URL
access_token_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'

def get_access_token():
    try:
        response = requests.get(access_token_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        print(f"Error obtaining access token: {e}")
        return None

def process_stkpush(amount, phone_number):
    access_token = get_access_token()
    if not access_token:
        return {"ResponseCode": "1", "ResponseDescription": "Failed to obtain access token"}

    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    # Password
    password = base64.b64encode((business_shortcode + lipa_na_mpesa_passkey + timestamp).encode()).decode('utf-8')

    # Request data
    data = {
        'BusinessShortCode': business_shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': amount,
        'PartyA': phone_number,
        'PartyB': business_shortcode,
        'PhoneNumber': phone_number,
        'CallBackURL': callback_url,
        'AccountReference': 'BingwaSokoni',
        'TransactionDesc': 'Bingwa Sokoni payment'
    }

    # Lipa na Mpesa Online API endpoint
    stk_push_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'

    # Headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    try:
        # Send the request
        response = requests.post(stk_push_url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending STK push request: {e}")
        return {"ResponseCode": "1", "ResponseDescription": "Failed to send STK push request"}

if __name__ == "__main__":
    # Example usage
    phone_number = input("Enter phone number: ")
    amount = input("Enter amount: ")
    response = process_stkpush(amount, phone_number)
    print(response)
