import requests
import base64
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# M-Pesa credentials
consumer_key = os.getenv("MPESA_CONSUMER_KEY")
consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
business_shortcode = os.getenv("MPESA_SHORTCODE")
lipa_na_mpesa_passkey = os.getenv("MPESA_PASSKEY")

# Get environment setting
environment = os.getenv("MPESA_ENVIRONMENT")  # 'live' or 'sandbox'

# Define base URL based on environment
base_url = 'https://api.safaricom.co.ke' if environment == 'live' else 'https://sandbox.safaricom.co.ke'

def get_access_token():
    access_token_url = f'{base_url}/oauth/v1/generate?grant_type=client_credentials'
    try:
        response = requests.get(access_token_url, auth=(consumer_key, consumer_secret))
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        print(f"Error obtaining access token: {e}")
        return None

def query_payment_status(checkout_request_id):
    access_token = get_access_token()
    if not access_token:
        return {"ResponseCode": "1", "ResponseDescription": "Failed to obtain access token"}

    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    # Password
    password = base64.b64encode((business_shortcode + lipa_na_mpesa_passkey + timestamp).encode()).decode('utf-8')

    # Prepare the request data
    data = {
        'BusinessShortCode': business_shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id
    }

    # Transaction status API URL
    api_url = f'{base_url}/mpesa/stkpushquery/v1/query'

    # Headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    try:
        # Send the request
        response = requests.post(api_url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying payment status: {e}")
        return {"ResponseCode": "1", "ResponseDescription": "Failed to query payment status"}

if __name__ == "__main__":
    # Example usage
    checkout_request_id = input("Enter CheckoutRequestID: ")
    response = query_payment_status(checkout_request_id)
    print(response)
