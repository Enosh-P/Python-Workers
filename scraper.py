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
        
        # Extract text content
        text_content = extract_text(soup)
        
        # Extract images
        images = extract_images(soup, url)
        
        # Extract metadata
        metadata = extract_metadata(soup, url)
        
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


def extract_images(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    Extract image URLs from HTML.
    
    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative image URLs
        
    Returns:
        List of absolute image URLs
    """
    images = []
    
    # Find all img tags
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if src:
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, src)
            # Filter out data URIs and very small images
            if not absolute_url.startswith('data:') and absolute_url not in images:
                images.append(absolute_url)
    
    # Also check for background images in style attributes
    for element in soup.find_all(style=True):
        style = element.get('style', '')
        if 'background-image' in style:
            # Extract URL from background-image: url(...)
            import re
            match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
            if match:
                img_url = urljoin(base_url, match.group(1))
                if img_url not in images:
                    images.append(img_url)
    
    return images[:20]  # Limit to 20 images


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

