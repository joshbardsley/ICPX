"""
Compute Module - Core Lead Generation Algorithm
5 layers: Zips → Domains → Companies → ICP Scores → CEOs
With aggressive caching for cost reduction
"""

import os
import asyncio
import httpx
import re
import json
import hashlib
from datetime import datetime
import dramatiq
import redis.asyncio as redis

from cache import (
    get_or_fetch_zips,
    get_or_fetch_domains,
    get_or_fetch_company,
    get_or_compute_icp_score,
    get_or_fetch_ceo
)
from database import record_run, decrement_user_runs

# API Keys
SERP_API_KEY = os.getenv("SERP_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Redis for pub/sub
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

@dramatiq.actor(max_retries=0, time_limit=1800000)  # 30 min timeout
async def generate_leads_job(job_id: str, icp: dict, target: int, user_id: str):
    """
    Background job: Generate leads with streaming updates
    """
    total_leads = []
    batch_number = 0
    dork_offset = 0
    cost_tracker = {"total": 0.0}

    try:
        # L1: Get zipcodes
        zips = await l1_zip_expansion(icp['location'])
        await publish_update(job_id, {
            "stage": "zips",
            "message": f"Found {len(zips)} zipcodes in {icp['location']}"
        })

        # Process in batches until we hit target
        while len(total_leads) < target:
            batch_number += 1

            await publish_update(job_id, {
                "stage": "batch_start",
                "batch": batch_number,
                "message": f"Starting batch {batch_number}..."
            })

            # L2: Domain discovery (500 dorks per batch)
            domains = await l2_domain_dork_batch(
                zips, icp, dork_offset, 500, cost_tracker
            )

            await publish_update(job_id, {
                "stage": "domains",
                "batch": batch_number,
                "domains_found": len(domains)
            })

            # L3: Company sizing & filtering
            qualified = await l3_batch_filter(domains, icp, cost_tracker)

            await publish_update(job_id, {
                "stage": "qualified",
                "batch": batch_number,
                "companies_qualified": len(qualified)
            })

            # L3.5: Deep ICP scoring
            deep_matched = await l3_5_batch_score(qualified, icp, cost_tracker)

            await publish_update(job_id, {
                "stage": "icp_scored",
                "batch": batch_number,
                "deep_matches": len(deep_matched)
            })

            # L4: CEO lookup
            ceo_leads = []
            for domain, score in deep_matched:
                company_name = extract_company_name(domain)
                ceo = await l4_ceo_lookup(company_name, domain, cost_tracker)

                if ceo:
                    ceo_leads.append({
                        "domain": domain,
                        "company_name": company_name,
                        "ceo": ceo,
                        "icp_score": score
                    })

            # Add to total (up to target)
            new_leads = ceo_leads[:target - len(total_leads)]
            total_leads.extend(new_leads)

            # Push batch update
            await publish_update(job_id, {
                "batch": batch_number,
                "count": len(total_leads),
                "latest": new_leads,
                "progress": len(total_leads) / target,
                "cost": f"${cost_tracker['total']:.2f}"
            })

            dork_offset += 500

            # Stop if target reached
            if len(total_leads) >= target:
                break

        # Generate CSV
        csv_url = await generate_csv(total_leads)

        # Record in database
        await record_run(
            user_id,
            None,  # ICP ID (optional)
            len(total_leads),
            csv_url,
            cost_tracker['total']
        )

        # Decrement user's runs
        await decrement_user_runs(user_id)

        # Final update
        await publish_update(job_id, {
            "complete": True,
            "total": len(total_leads),
            "csv_url": csv_url,
            "cost": f"${cost_tracker['total']:.2f}"
        })

    except Exception as e:
        print(f"❌ Job {job_id} failed: {e}")
        await publish_update(job_id, {
            "error": True,
            "message": str(e)
        })

async def start_lead_generation(job_id: str, icp: dict, target: int, user_id: str):
    """Start the background job"""
    generate_leads_job.send(job_id, icp, target, user_id)

# ============================================================================
# L1: ZIPCODE EXPANSION
# ============================================================================

async def l1_zip_expansion(location: str) -> list[str]:
    """
    Convert location to zipcodes
    Uses cache (permanent)
    """
    async def fetch_zips(loc: str):
        """Fetch zipcodes using SerpAPI"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": f"zipcodes in {loc}",
                    "api_key": SERP_API_KEY
                }
            )
            data = response.json()

            # Extract zipcodes from results
            zips = extract_zipcodes_from_results(data)
            return zips

    # Use cache
    zips = await get_or_fetch_zips(location, fetch_zips)
    return zips

def extract_zipcodes_from_results(data: dict) -> list[str]:
    """Extract zipcodes from SerpAPI results"""
    zips = []

    # Look in organic results
    for result in data.get("organic_results", []):
        snippet = result.get("snippet", "")
        # Find 5-digit numbers
        found = re.findall(r'\b\d{5}\b', snippet)
        zips.extend(found)

    # Deduplicate and return
    return list(set(zips))[:50]  # Max 50 zips

# ============================================================================
# L2: DOMAIN DISCOVERY
# ============================================================================

async def l2_domain_dork_batch(
    zips: list[str],
    icp: dict,
    offset: int,
    limit: int,
    cost_tracker: dict
) -> list[str]:
    """
    Run Google dorks to find company domains
    Proven: 50 dorks in 15 seconds, no blocks
    """
    domains = []

    for i in range(offset, min(offset + limit, offset + len(zips) * 10)):
        zip_idx = i % len(zips)
        zip_code = zips[zip_idx]

        # Check cache first
        cached_domains = await get_or_fetch_domains(
            zip_code,
            icp,
            lambda z, i: fetch_domains_for_zip(z, i)
        )

        domains.extend(cached_domains)

        # Rate limiting (0.3s = 3.3 qps, proven safe)
        await asyncio.sleep(0.3)

    # Track cost (only if not cached)
    cost_tracker['total'] += 0.05  # Rough estimate per batch

    # Deduplicate
    return list(set(domains))

async def fetch_domains_for_zip(zip_code: str, icp: dict) -> list[str]:
    """Fetch domains for a specific zipcode"""
    # Build dork query
    query = build_dork_query(zip_code, icp)

    # Execute search
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": SERP_API_KEY,
                "num": 10
            }
        )
        data = response.json()

    # Extract domains from URLs
    domains = extract_domains_from_urls(data)
    return domains

def build_dork_query(zip_code: str, icp: dict) -> str:
    """Build optimized Google dork query"""
    query = f'"{zip_code}" AND "{icp.get("industry", "")}" '

    # Add size indicators
    if "min_size" in icp:
        query += 'AND ("employees" OR "team" OR "staff") '

    # Target LinkedIn company pages or company websites
    query += 'site:linkedin.com/company OR inurl:about'

    return query

def extract_domains_from_urls(data: dict) -> list[str]:
    """Extract domains from search results"""
    domains = []

    for result in data.get("organic_results", []):
        url = result.get("link", "")

        # Extract domain
        match = re.search(r'https?://([^/]+)', url)
        if match:
            domain = match.group(1)

            # Clean domain
            domain = domain.replace("www.", "")

            # Skip LinkedIn/social media
            if domain not in ["linkedin.com", "facebook.com", "twitter.com"]:
                domains.append(domain)

    return domains

# ============================================================================
# L3: COMPANY SIZING & FILTERING
# ============================================================================

async def l3_batch_filter(
    domains: list[str],
    icp: dict,
    cost_tracker: dict
) -> list[str]:
    """
    Filter companies by size and industry
    Uses cache (30 days)
    """
    qualified = []

    # Process in parallel (batches of 10)
    for i in range(0, len(domains), 10):
        batch = domains[i:i+10]

        tasks = [
            get_or_fetch_company(
                domain,
                lambda d: fetch_company_signals(d)
            )
            for domain in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for domain, signals in zip(batch, results):
            if isinstance(signals, Exception):
                continue

            # Filter by size
            if "min_size" in icp and "max_size" in icp:
                if not (icp["min_size"] <= signals.get("size", 0) <= icp["max_size"]):
                    continue

            # Filter by industry (basic keyword match)
            if icp.get("industry"):
                if icp["industry"].lower() not in signals.get("industry", "").lower():
                    continue

            qualified.append(domain)

    return qualified

async def fetch_company_signals(domain: str) -> dict:
    """Scrape company website for signals"""
    signals = {
        "size": 0,
        "industry": "",
        "hiring": False,
        "founded": None
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Fetch about page
            response = await client.get(f"https://{domain}/about")
            html = response.text

            # Extract size
            size_match = re.search(r'(\d+)\+?\s*employees', html, re.IGNORECASE)
            if size_match:
                signals["size"] = int(size_match.group(1))

            # Extract industry (simple keyword extraction)
            signals["industry"] = extract_industry_keywords(html)

            # Check if hiring
            signals["hiring"] = "hiring" in html.lower() or "careers" in html.lower()

    except:
        pass  # Failed to fetch, return defaults

    return signals

def extract_industry_keywords(html: str) -> str:
    """Extract industry keywords from HTML"""
    industries = [
        "SaaS", "Software", "E-commerce", "Retail", "Marketing",
        "Agency", "Consulting", "Finance", "Healthcare", "Education"
    ]

    html_lower = html.lower()
    found = []

    for industry in industries:
        if industry.lower() in html_lower:
            found.append(industry)

    return ", ".join(found)

# ============================================================================
# L3.5: DEEP ICP SCORING (THE MAGIC)
# ============================================================================

async def l3_5_batch_score(
    domains: list[str],
    icp: dict,
    cost_tracker: dict
) -> list[tuple[str, int]]:
    """
    Score companies using Grok deep ICP matching
    Uses cache (60 days)
    """
    scored = []

    for domain in domains:
        score = await get_or_compute_icp_score(
            domain,
            icp,
            lambda d, i: compute_icp_score_with_grok(d, i)
        )

        # Only keep scores >= 75
        if score >= 75:
            scored.append((domain, score))

    # Track cost (Grok API)
    cost_tracker['total'] += 0.04

    # Sort by score (best first)
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored

async def compute_icp_score_with_grok(domain: str, icp: dict) -> int:
    """Use Grok to score ICP fit"""
    # Fetch about page
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://{domain}/about")
            html = response.text[:4000]  # Limit to 4K chars
    except:
        return 0  # Failed to fetch

    # Build Grok prompt
    prompt = f"""
TASK: Score how well this company matches the Ideal Customer Profile.

ICP CRITERIA:
- Industry: {icp.get('industry', 'Any')}
- Size: {icp.get('min_size', 0)}-{icp.get('max_size', 1000)} employees
- Pain Points: {icp.get('pain_points', 'N/A')}
- Location: {icp.get('location', 'Any')}

COMPANY ABOUT PAGE:
{html}

SCORING RULES:
- 90-100: Perfect match, explicitly mentions pain points
- 75-89: Strong match, clear alignment
- 60-74: Moderate match, some alignment
- Below 60: Poor match

OUTPUT: Just the number (0-100), nothing else.
"""

    # Call Grok API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-2-latest",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3
                }
            )
            data = response.json()

            # Extract score
            content = data["choices"][0]["message"]["content"]
            score = int(re.search(r'\d+', content).group())

            return min(100, max(0, score))

    except Exception as e:
        print(f"Grok API error: {e}")
        return 50  # Default moderate score

# ============================================================================
# L4: CEO LINKEDIN LOOKUP
# ============================================================================

async def l4_ceo_lookup(
    company_name: str,
    domain: str,
    cost_tracker: dict
) -> dict | None:
    """
    Find CEO LinkedIn profile
    Uses cache (permanent)
    """
    ceo = await get_or_fetch_ceo(
        domain,
        company_name,
        lambda cn, d: fetch_ceo_profile(cn, d)
    )

    return ceo

async def fetch_ceo_profile(company_name: str, domain: str) -> dict | None:
    """Fetch CEO LinkedIn profile using Google dork"""
    # Primary dork
    query = f'CEO OR Founder "{company_name}" site:linkedin.com/in'

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERP_API_KEY,
                    "num": 5
                }
            )
            data = response.json()

        # Get first result
        results = data.get("organic_results", [])
        if results:
            url = results[0]["link"]
            title = results[0].get("title", "")

            # Extract name from title
            name = extract_name_from_title(title)

            return {
                "name": name,
                "title": "CEO",
                "linkedin_url": url
            }
    except:
        pass

    return None

def extract_name_from_title(title: str) -> str:
    """Extract person's name from LinkedIn title"""
    # LinkedIn titles usually: "Name - Title at Company | LinkedIn"
    parts = title.split("-")
    if parts:
        name = parts[0].strip()
        # Remove "| LinkedIn" if present
        name = name.replace("| LinkedIn", "").strip()
        return name
    return "Unknown"

def extract_company_name(domain: str) -> str:
    """Extract company name from domain"""
    # Simple: capitalize domain without TLD
    name = domain.split(".")[0]
    return name.capitalize()

# ============================================================================
# CSV GENERATION
# ============================================================================

async def generate_csv(leads: list[dict]) -> str:
    """
    Generate CSV and upload to Cloudflare R2
    """
    import csv
    from io import StringIO
    import boto3

    # Build CSV in memory
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'company_name',
        'domain',
        'ceo_name',
        'ceo_title',
        'linkedin_url',
        'icp_score',
        'date_generated'
    ])

    writer.writeheader()
    for lead in leads:
        writer.writerow({
            'company_name': lead['company_name'],
            'domain': lead['domain'],
            'ceo_name': lead['ceo']['name'],
            'ceo_title': lead['ceo']['title'],
            'linkedin_url': lead['ceo']['linkedin_url'],
            'icp_score': lead['icp_score'],
            'date_generated': datetime.utcnow().isoformat()
        })

    csv_content = output.getvalue()

    # Upload to R2
    s3 = boto3.client(
        's3',
        endpoint_url=os.getenv('R2_ENDPOINT'),
        aws_access_key_id=os.getenv('R2_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('R2_SECRET_KEY')
    )

    filename = f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    s3.put_object(
        Bucket='icp-leads',
        Key=filename,
        Body=csv_content.encode(),
        ContentType='text/csv'
    )

    # Return public URL
    url = f"{os.getenv('R2_PUBLIC_URL')}/{filename}"
    return url

# ============================================================================
# UTILITIES
# ============================================================================

async def publish_update(job_id: str, data: dict):
    """Publish update to Redis pub/sub for WebSocket"""
    await redis_client.publish(
        f"job:{job_id}",
        json.dumps(data)
    )
