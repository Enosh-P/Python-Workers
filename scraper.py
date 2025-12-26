"""
Web scraper for venue websites.
Extracts text content and images from venue URLs.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

# User agent to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def scrape_venue_page(url: str, timeout: int = 30) -> Dict[str, any]:
    """
    Scrape a venue webpage and extract text content and images.
    
    Args:
        url: The URL of the venue page to scrape
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with 'text', 'images', and 'metadata' keys
    """
    try:
        logger.info(f"Scraping URL: {url}")
        
        # Make request
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "meta", "link"]):
            script.decompose()
        
        # Extract metadata first (may contain venue name)
        metadata = extract_metadata(soup, url)
        
        # Extract text content
        text_content = extract_text(soup)
        
        # Try to extract venue name from metadata or page title
        venue_name = metadata.get('title', '') or metadata.get('og_title', '')
        # Clean up common suffixes (remove site name, separators)
        if venue_name:
            venue_name = venue_name.split('|')[0].split('-')[0].strip()
            # Remove common website suffixes
            for suffix in [' - Home', ' | Home', ' - Venue', ' | Venue']:
                if venue_name.endswith(suffix):
                    venue_name = venue_name[:-len(suffix)].strip()
        
        # Extract images (prioritize those near venue name)
        images = extract_images(soup, url, venue_name)
        
        logger.info(f"Extracted {len(text_content)} characters of text and {len(images)} images")
        
        return {
            'text': text_content,
            'images': images,
            'metadata': metadata,
            'url': url
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error parsing HTML from {url}: {str(e)}")
        raise


def extract_text(soup: BeautifulSoup) -> str:
    """
    Extract and clean text content from HTML.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Cleaned text content
    """
    # Get all text
    text = soup.get_text()
    
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text


from typing import List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

from typing import List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def extract_images(soup: BeautifulSoup, base_url: str, venue_name: str = None) -> List[str]:
    """
    Extract image URLs from HTML with simple prioritization.
    
    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative image URLs
        venue_name: Optional venue name (not currently used, reserved for future)
        
    Returns:
        List of absolute image URLs, prioritized by relevance
    """
    # Keywords that indicate important/hero images (prioritize these)
    PRIORITY_KEYWORDS = ['jpeg', 'jpg', 'resort', 'beach', 'venue', 'upload']
    
    # Patterns to skip (icons, logos, etc.)
    SKIP_PATTERNS = [
        'icon', 'logo', 'favicon', 'sprite', 'button', 'arrow',
        'social', 'share', 'nav', 'menu', 'avatar', 'thumbnail', 
        'png', 'ico'
    ]
    
    priority_images = []
    regular_images = []
    
    # Extract Open Graph image first (usually the best representative image)
    og_img = soup.find('meta', property='og:image')
    if og_img:
        og_url = urljoin(base_url, og_img.get('content', '').strip())
        if og_url and not og_url.startswith('data:'):
            priority_images.append(og_url)
    
    # Find all img tags
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if not src:
            continue
        
        absolute_url = urljoin(base_url, src)
        
        # Skip data URIs
        if absolute_url.startswith('data:'):
            continue
        
        # Skip PNG and ICO files (usually icons/logos)
        url_lower = absolute_url.lower()
        if url_lower.endswith('.png') or url_lower.endswith('.ico'):
            continue
        
        # Check if we should skip this image based on class/id/alt
        img_text = (
            ' '.join(img.get('class', [])) + ' ' + 
            str(img.get('id', '')) + ' ' +
            str(img.get('alt', ''))
        ).lower()
        
        # Also check URL path for skip patterns (but not file extension)
        combined_text = url_lower + ' ' + img_text
        
        if any(pattern in combined_text for pattern in SKIP_PATTERNS):
            continue
        
        # Skip small images
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                if int(width) < 150 or int(height) < 150:
                    continue
            except (ValueError, TypeError):
                pass
        
        # Prioritize images with priority keywords
        if any(keyword in img_text for keyword in PRIORITY_KEYWORDS):
            if absolute_url not in priority_images:
                priority_images.append(absolute_url)
        else:
            if absolute_url not in regular_images:
                regular_images.append(absolute_url)
    
    # Check for background images in style attributes
    for element in soup.find_all(style=True):
        style = element.get('style', '')
        if 'background-image' in style:
            match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
            if match:
                img_url = urljoin(base_url, match.group(1))
                if not img_url.startswith('data:') and img_url not in priority_images + regular_images:
                    regular_images.append(img_url)
    
    # Combine and return: priority images first, then regular images
    result = priority_images + regular_images
    return result[:20]  # Limit to 20 images


def find_common_ancestor(elem1, elem2):
    """Find the common ancestor of two elements."""
    if not elem1 or not elem2:
        return None
    
    ancestors1 = set()
    current = elem1
    while current:
        ancestors1.add(current)
        current = current.parent
        if current and current.name == '[document]':
            break
    
    current = elem2
    while current:
        if current in ancestors1:
            return current
        current = current.parent
        if current and current.name == '[document]':
            break
    
    return None


def get_element_distance(elem1, elem2, max_depth=5):
    """Calculate the DOM distance between two elements."""
    if not elem1 or not elem2:
        return None
    
    # Find common ancestor
    common = find_common_ancestor(elem1, elem2)
    if not common:
        return None
    
    # Calculate depth from common ancestor
    depth1 = 0
    current = elem1
    while current and current != common:
        depth1 += 1
        current = current.parent
        if depth1 > max_depth:
            return None
    
    depth2 = 0
    current = elem2
    while current and current != common:
        depth2 += 1
        current = current.parent
        if depth2 > max_depth:
            return None
    
    return depth1 + depth2


def extract_metadata(soup: BeautifulSoup, url: str) -> Dict[str, any]:
    """
    Extract metadata from HTML (title, description, etc.).
    
    Args:
        soup: BeautifulSoup object
        url: The page URL
        
    Returns:
        Dictionary with metadata
    """
    metadata = {
        'title': '',
        'description': '',
        'url': url
    }
    
    # Extract title
    title_tag = soup.find('title')
    if title_tag:
        metadata['title'] = title_tag.get_text().strip()
    
    # Extract meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        metadata['description'] = meta_desc.get('content', '').strip()
    
    # Extract Open Graph data
    og_title = soup.find('meta', property='og:title')
    if og_title:
        metadata['og_title'] = og_title.get('content', '').strip()
    
    og_desc = soup.find('meta', property='og:description')
    if og_desc:
        metadata['og_description'] = og_desc.get('content', '').strip()
    
    og_image = soup.find('meta', property='og:image')
    if og_image:
        metadata['og_image'] = urljoin(url, og_image.get('content', '').strip())
    
    return metadata

