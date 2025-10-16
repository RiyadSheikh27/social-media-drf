import requests
import jwt
from jwt.algorithms import RSAAlgorithm
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def verify_google_access_token(access_token):
    """
    Verify Google OAuth access token and return user email.
    Uses Google's tokeninfo endpoint to validate the access token.
    """
    try:
        # Call Google's tokeninfo endpoint
        response = requests.get(
            'https://www.googleapis.com/oauth2/v3/tokeninfo',
            params={'access_token': access_token},
            timeout=10
        )
        
        logger.info(f"Google tokeninfo response status: {response.status_code}")
        logger.info(f"Google tokeninfo response: {response.text}")
        
        if response.status_code != 200:
            return None
        
        token_info = response.json()
        
        # Check if token is valid
        if 'email' not in token_info:
            logger.error(f"Email not found in token_info: {token_info}")
            return None
        
        # Optionally verify the token is for your app
        # if 'aud' in token_info:
        #     expected_audience = settings.GOOGLE_OAUTH_CLIENT_ID
        #     if token_info['aud'] != expected_audience:
        #         return None
        
        # Check if email is verified
        email_verified = token_info.get('email_verified')
        if email_verified == 'true' or email_verified is True or email_verified == True:
            return token_info['email'].lower()
        
        logger.error(f"Email not verified: {token_info}")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Google token verification request error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Google token verification error: {str(e)}")
        return None


def get_google_user_info(access_token):
    """
    Get user info from Google using access token.
    This directly fetches user information from Google's userinfo endpoint.
    This is the PRIMARY method for Google OAuth with access tokens.
    """
    try:
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        logger.info(f"Google userinfo response status: {response.status_code}")
        logger.info(f"Google userinfo response: {response.text}")
        
        if response.status_code != 200:
            return None
        
        user_info = response.json()
        
        # Check if email is verified
        if user_info.get('verified_email'):
            return {
                'email': user_info.get('email', '').lower(),
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'given_name': user_info.get('given_name', ''),
                'family_name': user_info.get('family_name', ''),
                'verified_email': user_info.get('verified_email')
            }
        
        logger.error(f"Email not verified in user_info: {user_info}")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Error fetching Google user info request: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error fetching Google user info: {str(e)}")
        return None


def verify_apple_access_token(access_token):
    """
    Verify Apple OAuth access token and return user email.
    Apple uses JWT tokens, so we need to decode and verify the token.
    """
    try:
        # Get Apple's public keys
        response = requests.get('https://appleid.apple.com/auth/keys', timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to get Apple keys: {response.status_code}")
            return None
        
        apple_keys = response.json()
        
        # Decode the token header to get the key id (kid)
        unverified_header = jwt.get_unverified_header(access_token)
        kid = unverified_header.get('kid')
        
        if not kid:
            logger.error("No kid found in Apple token header")
            return None
        
        # Find the matching public key
        public_key = None
        for key in apple_keys.get('keys', []):
            if key.get('kid') == kid:
                public_key = RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            logger.error(f"No matching public key found for kid: {kid}")
            return None
        
        # Verify and decode the token
        decoded_token = jwt.decode(
            access_token,
            public_key,
            algorithms=['RS256'],
            audience=getattr(settings, 'APPLE_OAUTH_CLIENT_ID', None),
            options={'verify_exp': True}
        )
        
        logger.info(f"Apple decoded token: {decoded_token}")
        
        # Extract email from the token
        email = decoded_token.get('email')
        
        # Check if email is verified (Apple tokens have email_verified field)
        if decoded_token.get('email_verified') in ['true', True]:
            return email.lower() if email else None
        
        # Some Apple tokens might not have email_verified field
        # In that case, just return the email if present
        return email.lower() if email else None
        
    except jwt.ExpiredSignatureError:
        logger.error("Apple token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Apple token validation error: {str(e)}")
        return None
    except requests.RequestException as e:
        logger.error(f"Apple token verification request error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Apple token verification error: {str(e)}")
        return None


def get_apple_user_info(access_token):
    """
    Get user info from Apple using access token.
    Note: Apple's access tokens are actually ID tokens (JWT).
    """
    try:
        # Decode without verification first to check structure
        decoded_token = jwt.decode(access_token, options={"verify_signature": False})
        
        logger.info(f"Apple decoded token (unverified): {decoded_token}")
        
        return {
            'email': decoded_token.get('email', '').lower(),
            'email_verified': decoded_token.get('email_verified'),
            'sub': decoded_token.get('sub')  # Apple user ID
        }
        
    except Exception as e:
        logger.error(f"Error decoding Apple token: {str(e)}")
        return None