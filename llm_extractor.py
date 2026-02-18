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
        validated_data['cover_image_url'] = scraped_content.get('images', [])
        if len(validated_data["cover_image_url"]) > 3:
            validated_data["cover_image_url"] = validated_data["cover_image_url"][:3]
        
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

# Schemas for other section types
FOOD_SCHEMA = {
    "name": "String - caterer/vendor name",
    "menu_items": "[String] - list of menu items or dishes",
    "price_min": "Number - minimum price per person",
    "price_max": "Number - maximum price per person",
    "notes": "String - any additional notes",
    "images": "[String] - list of image URLs"
}

MUSIC_SCHEMA = {
    "name": "String - band/DJ/entertainer name",
    "type": "String - one of: band, dj, playlist, dance, performer, mc, lighting, sound_system, other",
    "songs": "[String] - list of songs or sample tracks",
    "price": "Number - price",
    "images": "[String] - list of image URLs"
}

PHOTOGRAPHER_SCHEMA = {
    "name": "String - photographer name",
    "price": "Number - price",
    "images": "[String] - list of image URLs",
    "notes": "String - any additional notes"
}

GIFT_SCHEMA = {
    "product_name": "String - product name",
    "price": "Number - product price",
    "image_url": "String - main product image URL",
    "product_url": "String - product page URL",
    "notes": "String - optional notes"
}


def _extract_with_llm(scraped_content: Dict, schema: Dict, schema_name: str, instructions: str) -> Optional[Dict]:
    """Generic LLM extraction with schema and prompt."""
    try:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        client = Groq(api_key=api_key)
        text = scraped_content.get('text', '')[:10000]
        metadata = scraped_content.get('metadata', {})
        images = scraped_content.get('images', [])[:10]
        schema_json = json.dumps(schema, indent=2)
        prompt = f"""Extract {schema_name} information from the following website content and return it as JSON matching this exact schema:

{schema_json}

Website Content:
Title: {metadata.get('title', 'N/A')}
Description: {metadata.get('description', 'N/A')}
Text Content: {text[:10000]}

{instructions}

Return ONLY valid JSON matching the schema. Use null for missing fields. For arrays, use empty array [] if none found.
"""
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": f"You are an expert at extracting structured data from websites. Always return valid JSON matching the exact schema provided."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_completion_tokens=4096,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error extracting {schema_name} data: {str(e)}")
        return None


def extract_food_data(scraped_content: Dict[str, any]) -> Optional[Dict]:
    """Extract structured food/caterer data from scraped content."""
    instructions = """1. Extract the caterer or food vendor name.
2. Extract menu items or dishes.
3. Extract price range (min/max per person) if available.
4. Extract any notes."""
    data = _extract_with_llm(scraped_content, FOOD_SCHEMA, "food/caterer", instructions)
    if not data or not data.get('name'):
        return None
    data['images'] = scraped_content.get('images', [])[:5]
    data['link'] = scraped_content.get('url', '')
    return data


def extract_music_data(scraped_content: Dict[str, any]) -> Optional[Dict]:
    """Extract structured music/entertainment data from scraped content."""
    instructions = """1. Extract the band, DJ, or entertainer name.
2. Set type to one of: band, dj, playlist, dance, performer, mc, lighting, sound_system, other.
3. Extract sample songs or tracks if available.
4. Extract price if available."""
    data = _extract_with_llm(scraped_content, MUSIC_SCHEMA, "music/entertainment", instructions)
    if not data or not data.get('name'):
        return None
    data['images'] = scraped_content.get('images', [])[:5]
    data['link'] = scraped_content.get('url', '')
    return data


def extract_photographer_data(scraped_content: Dict[str, any]) -> Optional[Dict]:
    """Extract structured photographer data from scraped content."""
    instructions = """1. Extract the photographer name or studio name.
2. Extract price if available.
3. Extract any notes."""
    data = _extract_with_llm(scraped_content, PHOTOGRAPHER_SCHEMA, "photographer", instructions)
    if not data or not data.get('name'):
        return None
    data['images'] = scraped_content.get('images', [])[:5]
    data['link'] = scraped_content.get('url', '')
    return data


def extract_gift_data(scraped_content: Dict[str, any]) -> Optional[Dict]:
    """Extract structured gift/product data from scraped content (product pages)."""
    instructions = """1. Extract the product name.
2. Extract the product price if available.
3. Extract the main product image URL from the images list.
4. For product pages (e.g. Amazon, Etsy, etc.), focus on product name, price, and image."""
    data = _extract_with_llm(scraped_content, GIFT_SCHEMA, "gift/product", instructions)
    if not data or not data.get('product_name'):
        # Fallback: scrape may have failed (e.g. Amazon blocks bots). Ask LLM using URL only.
        url = scraped_content.get('url', '')
        if url:
            logger.info(f"Scrape yielded no useful gift data, falling back to URL-only LLM extraction: {url}")
            data = _extract_gift_from_url(url)
        if not data or not data.get('product_name'):
            return None
    images = scraped_content.get('images', [])
    if images and not data.get('image_url'):
        data['image_url'] = images[0]
    data['product_url'] = data.get('product_url') or scraped_content.get('url', '')
    data['images'] = images[:5]
    return data


def _extract_gift_from_url(url: str) -> Optional[Dict]:
    """Fallback: ask the LLM to identify a product from its URL alone (e.g. Amazon ASIN in URL)."""
    try:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        client = Groq(api_key=api_key)
        schema_json = json.dumps(GIFT_SCHEMA, indent=2)
        prompt = f"""I have a product page URL but could not scrape its content. Based on the URL alone, extract as much product information as you can and return JSON matching this schema:

{schema_json}

Product URL: {url}

Instructions:
1. Many product URLs contain the product name (e.g. Amazon URLs have the product title in the path).
2. Extract the product name from the URL slug/path.
3. Set price to null if you cannot determine it.
4. Set image_url to null.
5. Set product_url to the provided URL.
6. If the URL is from a known retailer (Amazon, Etsy, Target, Walmart, etc.), note the retailer in the notes field.

Return ONLY valid JSON. Use null for fields you cannot determine."""

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are an expert at identifying products from URLs. Extract what you can from URL patterns, slugs, and path segments. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_completion_tokens=2048,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        if data and data.get('product_name'):
            data['product_url'] = url
            logger.info(f"URL-only extraction succeeded: {data.get('product_name')}")
            return data
        return None
    except Exception as e:
        logger.error(f"URL-only gift extraction failed: {str(e)}")
        return None

