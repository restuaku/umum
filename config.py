"""
Configuration and University Management
Loads 2,826 verified US universities and handles SheerID organization search
"""
import json
import random
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHEERID_BASE_URL = "https://services.sheerid.com"
SHEERID_ORG_SEARCH_API = "https://orgsearch.sheerid.net/rest/organization/search"

# Load universities from JSON
try:
    with open('verified_universities.json', 'r', encoding='utf-8') as f:
        ALL_UNIVERSITIES = json.load(f)
    logger.info(f"✅ Loaded {len(ALL_UNIVERSITIES)} universities")
except FileNotFoundError:
    logger.error("❌ verified_universities.json not found!")
    ALL_UNIVERSITIES = []

# Cache for SheerID search results
SHEERID_CACHE = {}

def search_school_in_sheerid(school_name, city, state):
    """
    Search university in SheerID organization database
    
    Returns:
        dict: School info with 'found', 'id', 'idExtended', 'name' if found
    """
    # Check cache
    cache_key = f"{school_name}|{state}"
    if cache_key in SHEERID_CACHE:
        return SHEERID_CACHE[cache_key]
    
    try:
        params = {
            'name': school_name,
            'country': 'US'
        }
        
        response = requests.get(SHEERID_ORG_SEARCH_API, params=params, timeout=10)
        results = response.json()
        
        # Filter: type == UNIVERSITY only
        for org in results:
            if org.get('type') == 'UNIVERSITY':
                org_name = org.get('name', '').lower()
                search_name = school_name.lower()
                
                # Simple name matching
                if search_name[:20] in org_name or org_name[:20] in search_name:
                    result = {
                        'id': str(org['id']),
                        'idExtended': str(org['idExtended']),
                        'name': org['name'],
                        'city': city,
                        'state': state,
                        'found': True
                    }
                    
                    # Cache result
                    SHEERID_CACHE[cache_key] = result
                    return result
        
        # Not found
        result = {'found': False}
        SHEERID_CACHE[cache_key] = result
        return result
        
    except Exception as e:
        logger.error(f"❌ SheerID search error: {e}")
        return {'found': False}

def get_random_verified_school(max_attempts=20):
    """
    Get random university that exists in both IPEDS and SheerID
    
    Args:
        max_attempts: Maximum number of random attempts
    
    Returns:
        dict: School info with 'id', 'idExtended', 'name', 'city', 'state'
    """
    # Known working fallback schools
    fallback_schools = [
        {'id': '243744', 'idExtended': '243744', 'name': 'Stanford University', 'city': 'Stanford', 'state': 'CA'},
        {'id': '166027', 'idExtended': '166027', 'name': 'Harvard University', 'city': 'Cambridge', 'state': 'MA'},
        {'id': '166683', 'idExtended': '166683', 'name': 'Massachusetts Institute of Technology', 'city': 'Cambridge', 'state': 'MA'},
        {'id': '214777', 'idExtended': '214777', 'name': 'University of California-Berkeley', 'city': 'Berkeley', 'state': 'CA'},
        {'id': '2285', 'idExtended': '2285', 'name': 'New York University', 'city': 'New York', 'state': 'NY'},
        {'id': '3499', 'idExtended': '3499', 'name': 'University of California-Los Angeles', 'city': 'Los Angeles', 'state': 'CA'},
    ]
    
    if not ALL_UNIVERSITIES:
        logger.warning("⚠️ No universities loaded, using fallback")
        return random.choice(fallback_schools)
    
    # Try random universities
    for attempt in range(max_attempts):
        school = random.choice(ALL_UNIVERSITIES)
        
        logger.info(f"🔍 Attempt {attempt + 1}/{max_attempts}: {school['name'][:40]}")
        
        result = search_school_in_sheerid(school['name'], school['city'], school['state'])
        
        if result['found']:
            logger.info(f"✅ Found in SheerID: {result['name']}")
            return result
    
    # Fallback
    logger.warning("⚠️ Using fallback school after max attempts")
    return random.choice(fallback_schools)
