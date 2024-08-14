import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

consumer_key = os.getenv("MPESA_CONSUMER_KEY")
consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")

api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

def get_access_token():
    try:
        response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error obtaining access token: {e}")
        return None

if __name__ == "__main__":
    token = get_access_token()
    if token:
        print(f"Access Token: {token}")
    else:
        print("Failed to get access token.")