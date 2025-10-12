# accounts/utils.py
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
import base64

def verify_google_token(id_token_str):
    """
    Verifies Google ID token and returns the user's email if valid.
    """
    try:
        idinfo = id_token.verify_oauth2_token(id_token_str, requests.Request())
        email = idinfo.get('email')
        email_verified = idinfo.get('email_verified')
        if not email or not email_verified:
            return None
        return email
    except ValueError:
        return None

def verify_apple_token(id_token_str):
    """
    Verifies Apple ID token and returns user's email if valid.
    """
    try:
        decoded = jwt.decode(id_token_str, options={"verify_signature": False})
        email = decoded.get('email')
        if not email:
            return None
        return email
    except Exception:
        return None
