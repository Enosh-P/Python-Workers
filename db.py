"""
Database operations for venue scraping tasks.
Connects to the same PostgreSQL database as Next.js.
"""

import psycopg2
import psycopg2.extras
import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Get a database connection using environment variables.
    
    Returns:
        psycopg2 connection object
    """
    # Support both DATABASE_URL and individual connection parameters
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'onlycouples'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '')
        )


def find_pending_tasks(limit: int = 10) -> List[Dict]:
    """
    Find pending venue scraping tasks.
    
    Args:
        limit: Maximum number of tasks to return
        
    Returns:
        List of task dictionaries
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT * FROM venue_scraping_tasks
            WHERE status = 'pending' AND cancel_flag = FALSE
            ORDER BY created_at ASC
            LIMIT %s
        """, (limit,))
        
        tasks = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert to list of dicts
        return [dict(task) for task in tasks]
        
    except Exception as e:
        logger.error(f"Error finding pending tasks: {str(e)}")
        raise


def update_task_status(task_id: str, status: str, venue_data: Optional[Dict] = None, error_message: Optional[str] = None):
    """
    Update a scraping task's status and data.
    
    Args:
        task_id: Task ID
        status: New status ('processing', 'ready', 'failed')
        venue_data: Extracted venue data (JSON)
        error_message: Error message if failed
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        updates = []
        values = []
        
        updates.append("status = %s")
        values.append(status)
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        if venue_data is not None:
            updates.append("venue_data = %s")
            values.append(json.dumps(venue_data))
        
        if error_message is not None:
            updates.append("error_message = %s")
            values.append(error_message)
        
        if status == 'ready' or status == 'failed':
            updates.append("processed_at = CURRENT_TIMESTAMP")
        
        values.append(task_id)
        
        query = f"""
            UPDATE venue_scraping_tasks
            SET {', '.join(updates)}
            WHERE id = %s
        """
        
        cur.execute(query, values)
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Updated task {task_id} to status: {status}")
        
    except Exception as e:
        logger.error(f"Error updating task status: {str(e)}")
        raise


def check_cancel_flag(task_id: str) -> bool:
    """
    Check if a task has been canceled.
    
    Args:
        task_id: Task ID
        
    Returns:
        True if canceled, False otherwise
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT cancel_flag FROM venue_scraping_tasks
            WHERE id = %s
        """, (task_id,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return result[0] if result else False
        
    except Exception as e:
        logger.error(f"Error checking cancel flag: {str(e)}")
        return False


def create_venue_item(space_id: int, venue_data: Dict, venue_url: str = None) -> str:
    """
    Create a venue_item in the venue_items table from extracted venue data.
    
    Args:
        space_id: Space ID
        venue_data: Extracted venue data matching VENUE_SCHEMA
        
    Returns:
        Created venue item ID
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Map VENUE_SCHEMA to venue_items columns
        venue_id = f"venue_{int(datetime.now().timestamp() * 1000)}_{space_id}"
        
        # Format address from location (combine city, area, state)
        location = venue_data.get('location', {})
        address_parts = []
        # Add area if available
        if location.get('area'):
            address_parts.append(location['area'])
        # Add city if available
        if location.get('city'):
            address_parts.append(location['city'])
        # Add state if available
        if location.get('state'):
            address_parts.append(location['state'])
        # Join with commas: "Area, City, State" or "City, State" or just "State"
        address = ', '.join(address_parts) if address_parts else None
        
        # Format notes
        notes_parts = []
        if venue_data.get('rating'):
            notes_parts.append(f"Rating: {venue_data['rating']}")
        if venue_data.get('guest_capacity'):
            capacity = venue_data['guest_capacity']
            capacity_parts = []
            if capacity.get('seated'):
                capacity_parts.append(f"Seated: {capacity['seated']}")
            if capacity.get('floating'):
                capacity_parts.append(f"Floating: {capacity['floating']}")
            if capacity_parts:
                notes_parts.append(f"Capacity: {', '.join(capacity_parts)}")
        if venue_data.get('spaces_available'):
            notes_parts.append(f"Spaces: {', '.join(venue_data['spaces_available'])}")
        if venue_data.get('rooms_available'):
            notes_parts.append(f"Rooms: {venue_data['rooms_available']}")
        notes = ' | '.join(notes_parts) if notes_parts else None
        
        # Get price
        price = None
        if venue_data.get('price_per_plate_starting'):
            price_data = venue_data['price_per_plate_starting']
            price = price_data.get('non_veg') or price_data.get('veg')
        
        # Map venue_type to category
        category = None
        if venue_data.get('venue_type') and len(venue_data['venue_type']) > 0:
            first_type = venue_data['venue_type'][0].lower()
            category_map = {
                'beach': 'beach',
                'indoor': 'indoor',
                'farm': 'farm',
                'garden': 'garden',
                'ballroom': 'ballroom',
                'outdoor': 'outdoor',
                'barn': 'barn',
                'estate': 'estate',
                'resort': 'resort',
            }
            category = category_map.get(first_type, 'other')
        
        # Get images and prioritize .jpg/.jpeg files
        images = venue_data.get('cover_image_url', [])
        if not isinstance(images, list):
            images = []
        
        # Sort images to prioritize .jpg and .jpeg extensions
        def prioritize_jpg(url):
            """Return sort key: 0 for .jpg/.jpeg, 1 for others"""
            url_lower = url.lower()
            if url_lower.endswith('.jpg') or url_lower.endswith('.jpeg'):
                return 0
            return 1
        
        images = sorted(images, key=prioritize_jpg)
        
        # Get rating, spaces_available, and phone_number
        rating = venue_data.get('rating')
        spaces_available = venue_data.get('spaces_available', [])
        if not isinstance(spaces_available, list):
            spaces_available = []
        phone_number = venue_data.get('phone_number')
        
        # Insert into venue_items (including venue_data JSONB, rating, spaces_available, link, and phone_number)
        cur.execute("""
            INSERT INTO venue_items (
                id, space_id, name, address, price, available_dates, images, notes, category,
                is_finalized, is_favorite, venue_data, rating, spaces_available, link, phone_number, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
        """, (
            venue_id,
            space_id,
            venue_data.get('name', 'Unknown Venue'),
            address,
            price,
            [],  # available_dates
            images,
            notes,
            category,
            False,  # is_finalized
            False,  # is_favorite
            json.dumps(venue_data),  # Store full VENUE_SCHEMA as JSONB
            rating,  # rating column
            spaces_available,  # spaces_available array
            venue_url,  # link column - original URL used to scrape
            phone_number,  # phone_number column
        ))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Created venue item {result[0]} for space {space_id}")
        
        return result[0]
        
    except Exception as e:
        logger.error(f"Error creating venue item: {str(e)}")
        raise

