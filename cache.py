"""
Aggressive Caching Strategy - THE MOAT
Reduces cost from $0.36 → $0.01 at scale

Cache Layers:
- L1 Zips: Permanent cache
- L2 Domains: 90 days
- L3 Companies: 30 days
- L3.5 ICP Scores: 60 days
- L4 CEOs: Permanent cache
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# L1: ZIPCODE CACHE (Permanent)
# ============================================================================

async def get_or_fetch_zips(location: str, fetch_fn):
    """
    Get zipcodes from cache or fetch new
    Cache: Permanent (zips never change)
    """
    cache_key = f"zips:{location.lower()}"

    # Check cache (custom table or use domains table with type field)
    result = supabase.table("domains").select("data").eq("domain", cache_key).execute()

    if result.data:
        # Cache hit
        return result.data[0]["data"]["zips"]

    # Cache miss - fetch
    zips = await fetch_fn(location)

    # Store in cache (permanent)
    supabase.table("domains").upsert({
        "domain": cache_key,
        "data": {"zips": zips}
    }).execute()

    return zips

# ============================================================================
# L2: DOMAIN CACHE (90 days)
# ============================================================================

async def get_or_fetch_domains(zip_code: str, icp: dict, fetch_fn):
    """
    Get domains from cache or fetch new
    Cache: 90 days (domains change slowly)
    """
    # Create cache key (hash ICP to avoid huge keys)
    icp_hash = hashlib.md5(json.dumps(icp, sort_keys=True).encode()).hexdigest()[:8]
    cache_key = f"domains:{zip_code}:{icp_hash}"

    # Check cache
    result = supabase.table("domains").select("data", "last_updated").eq("domain", cache_key).execute()

    if result.data:
        cached = result.data[0]
        last_updated = datetime.fromisoformat(cached["last_updated"])

        # Check if cache is still fresh (90 days)
        if datetime.utcnow() - last_updated < timedelta(days=90):
            return cached["data"]["domains"]

    # Cache miss or expired - fetch
    domains = await fetch_fn(zip_code, icp)

    # Store in cache
    supabase.table("domains").upsert({
        "domain": cache_key,
        "data": {"domains": domains},
        "last_updated": datetime.utcnow().isoformat()
    }).execute()

    return domains

# ============================================================================
# L3: COMPANY SIGNALS CACHE (30 days)
# ============================================================================

async def get_or_fetch_company(domain: str, fetch_fn):
    """
    Get company signals from cache or fetch new
    Cache: 30 days (company info changes monthly)
    """
    # Check cache
    result = supabase.table("companies").select("signals", "last_updated").eq("domain", domain).execute()

    if result.data:
        cached = result.data[0]
        last_updated = datetime.fromisoformat(cached["last_updated"])

        # Check if cache is fresh (30 days)
        if datetime.utcnow() - last_updated < timedelta(days=30):
            return cached["signals"]

    # Cache miss or expired - fetch
    signals = await fetch_fn(domain)

    # Store in cache
    supabase.table("companies").upsert({
        "domain": domain,
        "signals": signals,
        "last_updated": datetime.utcnow().isoformat()
    }).execute()

    return signals

# ============================================================================
# L3.5: ICP SCORE CACHE (60 days)
# ============================================================================

async def get_or_compute_icp_score(domain: str, icp: dict, compute_fn):
    """
    Get ICP score from cache or compute new
    Cache: 60 days (ICP matches don't change often)
    """
    # Create cache key (include ICP hash)
    icp_hash = hashlib.md5(json.dumps(icp, sort_keys=True).encode()).hexdigest()[:8]
    cache_key = f"icp_score:{domain}:{icp_hash}"

    # Check company signals cache for ICP scores
    result = supabase.table("companies").select("signals", "last_updated").eq("domain", cache_key).execute()

    if result.data:
        cached = result.data[0]
        last_updated = datetime.fromisoformat(cached["last_updated"])

        # Check if cache is fresh (60 days)
        if datetime.utcnow() - last_updated < timedelta(days=60):
            return cached["signals"].get("score", 0)

    # Cache miss or expired - compute
    score = await compute_fn(domain, icp)

    # Store in cache
    supabase.table("companies").upsert({
        "domain": cache_key,
        "signals": {"score": score},
        "last_updated": datetime.utcnow().isoformat()
    }).execute()

    return score

# ============================================================================
# L4: CEO CACHE (Permanent)
# ============================================================================

async def get_or_fetch_ceo(domain: str, company_name: str, fetch_fn):
    """
    Get CEO from cache or fetch new
    Cache: Permanent (CEOs are people, we keep them)
    """
    # Check cache
    result = supabase.table("ceos").select("ceo_data").eq("domain", domain).execute()

    if result.data:
        # Cache hit
        return result.data[0]["ceo_data"]

    # Cache miss - fetch
    ceo = await fetch_fn(company_name, domain)

    if ceo:
        # Store in cache (permanent)
        supabase.table("ceos").upsert({
            "domain": domain,
            "ceo_data": ceo,
            "found_at": datetime.utcnow().isoformat()
        }).execute()

    return ceo

# ============================================================================
# CACHE STATS (for monitoring)
# ============================================================================

async def get_cache_stats():
    """Get cache statistics"""
    # Count entries
    domains_count = supabase.table("domains").select("id", count="exact").execute()
    companies_count = supabase.table("companies").select("id", count="exact").execute()
    ceos_count = supabase.table("ceos").select("id", count="exact").execute()

    # Fresh entries (last 30 days)
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()

    domains_fresh = supabase.table("domains").select("id", count="exact").gte("last_updated", cutoff).execute()
    companies_fresh = supabase.table("companies").select("id", count="exact").gte("last_updated", cutoff).execute()

    return {
        "domains": {
            "total": domains_count.count,
            "fresh": domains_fresh.count
        },
        "companies": {
            "total": companies_count.count,
            "fresh": companies_fresh.count
        },
        "ceos": {
            "total": ceos_count.count
        }
    }

# ============================================================================
# CACHE INVALIDATION (manual override)
# ============================================================================

async def invalidate_domain_cache(domain: str):
    """Force invalidate a domain's cache"""
    supabase.table("companies").delete().eq("domain", domain).execute()

async def invalidate_ceo_cache(domain: str):
    """Force invalidate a CEO's cache"""
    supabase.table("ceos").delete().eq("domain", domain).execute()

async def clear_old_cache(days: int = 90):
    """Clear cache older than X days"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Delete old domains
    supabase.table("domains").delete().lt("last_updated", cutoff).execute()

    # Delete old companies
    supabase.table("companies").delete().lt("last_updated", cutoff).execute()

    return {"message": f"Cleared cache older than {days} days"}
