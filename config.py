"""
Configuration and University Management (OPTIMIZED)
Fast SheerID organization handling for University Bot
"""
import json
import random
import requests
import logging
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHEERID_BASE_URL = "https://services.sheerid.com"
SHEERID_ORG_SEARCH_API = "https://orgsearch.sheerid.net/rest/organization/search"

# Pre-verified universities (hardcoded, NO JSON needed)
VERIFIED_UNIVERSITIES = [
    {'id': '243744', 'idExtended': '243744', 'name': 'Stanford University', 'city': 'Stanford', 'state': 'CA'},
    {'id': '166027', 'idExtended': '166027', 'name': 'Harvard University', 'city': 'Cambridge', 'state': 'MA'},
    {'id': '166683', 'idExtended': '166683', 'name': 'Massachusetts Institute of Technology', 'city': 'Cambridge', 'state': 'MA'},
    {'id': '214777', 'idExtended': '214777', 'name': 'University of California-Berkeley', 'city': 'Berkeley', 'state': 'CA'},
    {'id': '2285', 'idExtended': '2285', 'name': 'New York University', 'city': 'New York', 'state': 'NY'},
    {'id': '3499', 'idExtended': '3499', 'name': 'University of California-Los Angeles', 'city': 'Los Angeles', 'state': 'CA'},
    {'id': '132615', 'idExtended': '132615', 'name': 'University of Michigan-Ann Arbor', 'city': 'Ann Arbor', 'state': 'MI'},
    {'id': '100751', 'idExtended': '100751', 'name': 'The University of Alabama', 'city': 'Tuscaloosa', 'state': 'AL'},
    {'id': '104151', 'idExtended': '104151', 'name': 'Arizona State University Campus Immersion', 'city': 'Tempe', 'state': 'AZ'},
]

# In-memory cache (resets on restart, fast enough)
SHEERID_CACHE = {}

def normalize_school_data(school_data: Dict) -> Dict:
    """
    Normalize school data from SheerID OrgSearch untuk SheerIDVerifier
    
    Args:
        school_data: Raw data dari OrgSearch API
        
    Returns:
        dict: Normalized {'id', 'name', 'city', 'state', 'idExtended'}
    """
    return {
        'id': str(school_data.get('id', '')),
        'name': school_data.get('name', 'Unknown University'),
        'city': school_data.get('city', ''),
        'state': school_data.get('state', 'US'),
        'idExtended': school_data.get('idExtended', str(school_data.get('id', '')))
    }

def search_university_in_sheerid(query: str, university_type: str = "UNIVERSITY") -> list:
    """
    Search university via SheerID OrgSearch API (untuk bot conversation)
    
    Args:
        query: Nama universitas yang dicari
        university_type: UNIVERSITY, COLLEGE, FOUR_YEAR, TWO_YEAR
        
    Returns:
        list: List universities yang match (max 15)
    """
    cache_key = f"{query.lower()}|{university_type}"
    if cache_key in SHEERID_CACHE:
        logger.info(f"📡 Cache hit: {cache_key}")
        return SHEERID_CACHE[cache_key]
    
    try:
        params = {
            'name': query,
            'country': 'US',
            'type': university_type
        }
        
        logger.info(f"📡 SheerID search: {university_type} '{query}'")
        response = requests.get(SHEERID_ORG_SEARCH_API, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ SheerID API error: {response.status_code}")
            return []
        
        results = response.json()
        if not isinstance(results, list):
            logger.error(f"❌ Invalid SheerID response format")
            return []
        
        # Filter & normalize results
        universities = []
        seen_ids = set()
        for org in results:
            org_id = org.get('id')
            if org_id and org_id not in seen_ids:
                seen_ids.add(org_id)
                # Filter UNIVERSITY types only
                org_type = org.get('type', '').upper()
                if org_type in ['UNIVERSITY', 'COLLEGE', 'FOUR_YEAR']:
                    universities.append(normalize_school_data(org))
        
        # Cache & limit results
        universities = universities[:15]
        SHEERID_CACHE[cache_key] = universities
        
        logger.info(f"✅ Found {len(universities)} universities")
        return universities
        
    except Exception as e:
        logger.error(f"❌ SheerID search error: {e}")
        return []

def get_random_verified_school() -> Dict:
    """
    Get random PRE-VERIFIED university (INSTANT, NO API CALLS)
    
    Returns:
        dict: Ready-to-use school data untuk SheerIDVerifier
    """
    school = random.choice(VERIFIED_UNIVERSITIES)
    logger.info(f"🎓 Random school: {school['name']}")
    return school

def get_school_by_id(school_id: str) -> Optional[Dict]:
    """
    Get school by SheerID ID from verified list
    
    Args:
        school_id: SheerID organization ID
        
    Returns:
        dict: School data or None if not found
    """
    for school in VERIFIED_UNIVERSITIES:
        if school['id'] == school_id:
            return school
    return None

# Backward compatibility
def search_school_in_sheerid(school_name: str, city: str, state: str) -> Dict:
    """
    DEPRECATED: Use search_university_in_sheerid() instead
    """
    logger.warning("⚠️ search_school_in_sheerid() deprecated, use search_university_in_sheerid()")
    universities = search_university_in_sheerid(school_name)
    if universities:
        return universities[0]
    return {'found': False}

# Cache management
def clear_cache():
    """Clear SheerID cache (untuk testing)"""
    SHEERID_CACHE.clear()
    logger.info("🧹 Cache cleared")

def get_cache_stats():
    """Get cache statistics"""
    return {
        'total': len(SHEERID_CACHE),
        'universities': sum(1 for v in SHEERID_CACHE.values() if isinstance(v, list) and v)
    }

# Test functions
if __name__ == "__main__":
    print("🧪 Testing config.py...")
    
    # Test random school
    school = get_random_verified_school()
    print(f"✅ Random school: {school['name']} (ID: {school['id']})")
    
    # Test SheerID search
    results = search_university_in_sheerid("Stanford", "UNIVERSITY")
    print(f"✅ Stanford search: {len(results)} results")
    if results:
        print(f"   → {results[0]['name']}")
    
    print(f"📊 Cache stats: {get_cache_stats()}")
