"""
Groq LLM integration for extracting structured venue data from scraped content.
"""

import json
import logging
import re
from typing import Dict, Optional
from groq import Groq
import os

logger = logging.getLogger(__name__)

# VENUE_SCHEMA structure
VENUE_SCHEMA = {
    "name": "String",
    "location": {
        "city": "String",
        "area": "String",
        "state": "String"
    },
    "rating": "String",
    "guest_capacity": {
        "seated": "Number",
        "floating": "Number"
    },
    "price_per_plate_starting": {
        "veg": "Number",
        "non_veg": "Number"
    },
    "venue_type": "[String]",
    "spaces_available": ["Indoor", "Outdoor"],
    "rooms_available": "Number",
    "cover_image_url": "List of String Links",
    "phone_number": "String"
}


def extract_venue_data(scraped_content: Dict[str, any]) -> Optional[Dict]:
    """
    Extract structured venue data from scraped content using Groq LLM.
    
    Args:
        scraped_content: Dictionary with 'text', 'images', and 'metadata' keys
        
    Returns:
        Dictionary matching VENUE_SCHEMA structure, or None if extraction fails
    """
    try:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        client = Groq(api_key=api_key)
        
        # Prepare prompt
        prompt = create_extraction_prompt(scraped_content)
        
        logger.info("Calling Groq LLM for venue data extraction")
        
        # Call Groq API
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",  # or another Groq model
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting structured data from venue websites. Always return valid JSON matching the exact schema provided."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_completion_tokens=8192,
            top_p=1,
            reasoning_effort="medium",
            stream=False,  
            response_format={"type": "json_object"}
        )
        
        # Parse response
        content = response.choices[0].message.content
        venue_data = json.loads(content)
        
        # Validate structure
        validated_data = validate_venue_data(venue_data)
        # validated_data['cover_image_url'] = scraped_content.get('images', [])
        
        logger.info(f"Successfully extracted venue data: {validated_data.get('name', 'Unknown')}")
        
        return validated_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from LLM response: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error extracting venue data with LLM: {str(e)}")
        return None


def create_extraction_prompt(scraped_content: Dict[str, any]) -> str:
    """
    Create a prompt for the LLM to extract venue data.
    
    Args:
        scraped_content: Dictionary with scraped content
        
    Returns:
        Formatted prompt string
    """
    text = scraped_content.get('text', '')[:10000]  # Limit text length
    metadata = scraped_content.get('metadata', {})
    images = scraped_content.get('images', [])[:10]  # Get more images since we're filtering better
    
    prompt = f"""Extract venue information from the following website content and return it as JSON matching this exact schema:

{VENUE_SCHEMA_JSON}

Website Content:
Title: {metadata.get('title', 'N/A')}
Description: {metadata.get('description', 'N/A')}
Text Content: {text[:10000]}

Available Images (prioritized by relevance - first images are near venue name): {', '.join(images[:10])}

Instructions:
1. Extract the venue name
2. Extract location information (city, area, state) if available
3. Extract rating if mentioned
4. Extract guest capacity (seated and floating) if available
5. Extract price per plate (veg and non-veg) if available
6. Extract venue type(s) - can be multiple (e.g., ["indoor", "outdoor", "beach", "garden", "farm", "ballroom", "outdoor", "barn", "estate", "resort", "other"])
7. Extract available spaces (Indoor, Outdoor, or both)
8. Extract number of rooms if available
9. Extract venue relevant image URLs from the images list:
   - Prioritize images that similar to the venue name in the page structure
10. Extract phone number if available (format: digits only, with optional country code, e.g., "+1234567890" or "1234567890")

Return ONLY valid JSON matching the schema. Use null for missing fields. For arrays, use empty array [] if none found.
"""
    
    return prompt


def validate_phone_number(phone: str) -> Optional[str]:
    """
    Validate and clean phone number.
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Cleaned phone number string or None if invalid
    """
    if not phone:
        return None
    
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(phone).strip())
    
    # Remove leading + if present (we'll add it back if it's an international number)
    has_plus = cleaned.startswith('+')
    if has_plus:
        cleaned = cleaned[1:]
    
    # Check if it's all digits
    if not cleaned.isdigit():
        return None
    
    # Validate length (minimum 7 digits, maximum 15 digits for international)
    if len(cleaned) < 7 or len(cleaned) > 15:
        return None
    
    # Return with + prefix if it was there, or if it's 10+ digits (likely international)
    if has_plus or len(cleaned) >= 10:
        return f"+{cleaned}"
    
    return cleaned


def validate_venue_data(data: Dict) -> Dict:
    """
    Validate and clean extracted venue data.
    
    Args:
        data: Raw extracted data
        
    Returns:
        Validated and cleaned data
    """
    validated = {
        "name": data.get("name", "").strip() if data.get("name") else "",
        "location": {
            "city": data.get("location", {}).get("city", "") if isinstance(data.get("location"), dict) else "",
            "area": data.get("location", {}).get("area", "") if isinstance(data.get("location"), dict) else "",
            "state": data.get("location", {}).get("state", "") if isinstance(data.get("location"), dict) else ""
        },
        "rating": str(data.get("rating", "")) if data.get("rating") else None,
        "guest_capacity": {
            "seated": int(data.get("guest_capacity", {}).get("seated", 0)) if isinstance(data.get("guest_capacity"), dict) and data.get("guest_capacity", {}).get("seated") else None,
            "floating": int(data.get("guest_capacity", {}).get("floating", 0)) if isinstance(data.get("guest_capacity"), dict) and data.get("guest_capacity", {}).get("floating") else None
        },
        "price_per_plate_starting": {
            "veg": float(data.get("price_per_plate_starting", {}).get("veg", 0)) if isinstance(data.get("price_per_plate_starting"), dict) and data.get("price_per_plate_starting", {}).get("veg") else None,
            "non_veg": float(data.get("price_per_plate_starting", {}).get("non_veg", 0)) if isinstance(data.get("price_per_plate_starting"), dict) and data.get("price_per_plate_starting", {}).get("non_veg") else None
        },
        "venue_type": data.get("venue_type", []) if isinstance(data.get("venue_type"), list) else [],
        "spaces_available": data.get("spaces_available", []) if isinstance(data.get("spaces_available"), list) else [],
        "rooms_available": int(data.get("rooms_available", 0)) if data.get("rooms_available") else None,
        "cover_image_url": data.get("cover_image_url", []) if isinstance(data.get("cover_image_url"), list) else [],
        "phone_number": validate_phone_number(data.get("phone_number", "")) if data.get("phone_number") else None
    }
    
    # Prioritize .jpg/.jpeg images in cover_image_url
    if validated.get("cover_image_url"):
        def prioritize_jpg(url):
            """Return sort key: 0 for .jpg/.jpeg, 1 for others"""
            url_lower = str(url).lower()
            if url_lower.endswith('.jpg') or url_lower.endswith('.jpeg'):
                return 0
            return 1
        validated["cover_image_url"] = sorted(validated["cover_image_url"], key=prioritize_jpg)
        if len(validated["cover_image_url"]) > 3:
            validated["cover_image_url"] = validated["cover_image_url"][:3]
    
    # Ensure name is not empty
    if not validated["name"]:
        validated["name"] = "Unknown Venue"
    
    return validated


# VENUE_SCHEMA as JSON string for prompt
VENUE_SCHEMA_JSON = json.dumps(VENUE_SCHEMA, indent=2)

