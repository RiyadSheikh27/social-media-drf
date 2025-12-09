# posts/moderation.py
from better_profanity import profanity
import requests
import base64
from io import BytesIO
from PIL import Image
import tempfile
import os

# Initialize profanity filter
profanity.load_censor_words()


def check_text_content(text):
    """
    Check if text contains profanity or inappropriate content
    Returns: (is_safe, reason)
    """
    if not text:
        return True, None
    
    # Check for profanity
    if profanity.contains_profanity(text):
        return False, "Text contains inappropriate language"
    
    return True, None


def check_image_content(image_file):
    """
    Check if image contains NSFW content using Hugging Face API (Free)
    Returns: (is_safe, reason)
    """
    if not image_file:
        return True, None
    
    try:
        # Read image file
        if hasattr(image_file, 'read'):
            image_data = image_file.read()
            image_file.seek(0)  # Reset file pointer
        else:
            with open(image_file, 'rb') as f:
                image_data = f.read()
        
        # Use Hugging Face Inference API (Free, no API key needed for public models)
        API_URL = "https://api-inference.huggingface.co/models/Falconsai/nsfw_image_detection"
        
        response = requests.post(
            API_URL,
            data=image_data,
            headers={"Content-Type": "application/octet-stream"},
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            
            # Results format: [{"label": "nsfw", "score": 0.99}, {"label": "normal", "score": 0.01}]
            for result in results:
                if result.get('label') == 'nsfw' and result.get('score', 0) > 0.7:
                    return False, "Image contains inappropriate content"
            
            return True, None
        else:
            # If API is loading or fails, allow the post (don't block due to service issues)
            print(f"NSFW API response: {response.status_code}")
            return True, None
            
    except Exception as e:
        # If detection fails, log error but allow the post
        print(f"NSFW detection error: {e}")
        return True, None


def moderate_post(title, content, media_files=None):
    """
    Moderate entire post content
    Returns: (is_approved, rejection_reason)
    """
    # Check title
    is_safe, reason = check_text_content(title)
    if not is_safe:
        return False, reason
    
    # Check content
    is_safe, reason = check_text_content(content)
    if not is_safe:
        return False, reason
    
    # Check images if present
    if media_files:
        for media_file in media_files:
            is_safe, reason = check_image_content(media_file)
            if not is_safe:
                return False, reason
    
    return True, None