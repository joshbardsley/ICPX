"""
Database Operations - Supabase Client
All database interactions go through here
"""

import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# ICPs
# ============================================================================

async def save_icp(user_id: str, name: str, criteria: dict) -> str:
    """Save an ICP"""
    icp_data = {
        "user_id": user_id,
        "name": name,
        "criteria": criteria
    }

    result = supabase.table("icps").insert(icp_data).execute()

    if not result.data:
        raise Exception("Failed to save ICP")

    return result.data[0]["id"]

async def get_user_icps(user_id: str) -> List[Dict]:
    """Get all ICPs for a user"""
    result = supabase.table("icps").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()

    return result.data

async def get_icp(icp_id: str) -> Optional[Dict]:
    """Get a specific ICP"""
    result = supabase.table("icps").select("*").eq("id", icp_id).execute()

    if result.data:
        return result.data[0]

    return None

async def delete_icp(icp_id: str, user_id: str):
    """Delete an ICP (only if owned by user)"""
    supabase.table("icps").delete().eq("id", icp_id).eq("user_id", user_id).execute()

# ============================================================================
# RUNS
# ============================================================================

async def record_run(
    user_id: str,
    icp_id: Optional[str],
    leads_count: int,
    csv_url: str,
    cost: float
):
    """Record a completed run"""
    run_data = {
        "user_id": user_id,
        "icp_id": icp_id,
        "leads_count": leads_count,
        "csv_url": csv_url,
        "cost": cost
    }

    result = supabase.table("runs").insert(run_data).execute()

    return result.data[0]["id"] if result.data else None

async def get_user_runs(user_id: str, limit: int = 50) -> List[Dict]:
    """Get user's run history"""
    result = supabase.table("runs").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()

    return result.data

async def get_run(run_id: str) -> Optional[Dict]:
    """Get a specific run"""
    result = supabase.table("runs").select("*").eq("id", run_id).execute()

    if result.data:
        return result.data[0]

    return None

# ============================================================================
# USER MANAGEMENT
# ============================================================================

async def get_user(user_id: str) -> Optional[Dict]:
    """Get user by ID"""
    result = supabase.table("users").select("*").eq("id", user_id).execute()

    if result.data:
        return result.data[0]

    return None

async def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    result = supabase.table("users").select("*").eq("email", email).execute()

    if result.data:
        return result.data[0]

    return None

async def update_user(user_id: str, updates: dict):
    """Update user fields"""
    result = supabase.table("users").update(updates).eq("id", user_id).execute()

    return result.data[0] if result.data else None

# ============================================================================
# SUBSCRIPTION CHECKS
# ============================================================================

async def check_user_subscription(user_id: str) -> bool:
    """Check if user has active subscription"""
    result = supabase.table("users").select("subscribed").eq("id", user_id).execute()

    if result.data:
        return result.data[0]["subscribed"]

    return False

async def get_user_runs_remaining(user_id: str) -> int:
    """Get user's remaining runs"""
    result = supabase.table("users").select("runs_remaining").eq("id", user_id).execute()

    if result.data:
        return result.data[0]["runs_remaining"]

    return 0

async def decrement_user_runs(user_id: str):
    """Decrement user's runs_remaining by 1"""
    # Use RPC to atomically decrement
    supabase.rpc("decrement_runs", {"user_id_param": user_id}).execute()

    # Fallback if RPC doesn't exist
    # result = supabase.table("users").select("runs_remaining").eq("id", user_id).execute()
    # if result.data:
    #     current = result.data[0]["runs_remaining"]
    #     supabase.table("users").update({"runs_remaining": max(0, current - 1)}).eq("id", user_id).execute()

# ============================================================================
# ANALYTICS
# ============================================================================

async def get_user_stats(user_id: str) -> Dict:
    """Get user statistics"""
    # Total runs
    runs_result = supabase.table("runs").select("id", count="exact").eq("user_id", user_id).execute()
    total_runs = runs_result.count or 0

    # Total leads generated
    leads_result = supabase.table("runs").select("leads_count").eq("user_id", user_id).execute()
    total_leads = sum([r["leads_count"] for r in leads_result.data]) if leads_result.data else 0

    # Total cost
    cost_result = supabase.table("runs").select("cost").eq("user_id", user_id).execute()
    total_cost = sum([float(r["cost"]) for r in cost_result.data]) if cost_result.data else 0.0

    # User info
    user_result = supabase.table("users").select("subscribed", "runs_remaining", "created_at").eq("id", user_id).execute()
    user_info = user_result.data[0] if user_result.data else {}

    return {
        "total_runs": total_runs,
        "total_leads": total_leads,
        "total_cost": round(total_cost, 2),
        "subscribed": user_info.get("subscribed", False),
        "runs_remaining": user_info.get("runs_remaining", 0),
        "member_since": user_info.get("created_at")
    }

async def get_platform_stats() -> Dict:
    """Get platform-wide statistics (admin only)"""
    # Total users
    users_result = supabase.table("users").select("id", count="exact").execute()
    total_users = users_result.count or 0

    # Active subscriptions
    subs_result = supabase.table("users").select("id", count="exact").eq("subscribed", True).execute()
    active_subs = subs_result.count or 0

    # Total runs
    runs_result = supabase.table("runs").select("id", count="exact").execute()
    total_runs = runs_result.count or 0

    # Total revenue ($9.99 per active sub)
    monthly_revenue = active_subs * 9.99

    # Cache stats
    domains_result = supabase.table("domains").select("id", count="exact").execute()
    companies_result = supabase.table("companies").select("id", count="exact").execute()
    ceos_result = supabase.table("ceos").select("id", count="exact").execute()

    return {
        "total_users": total_users,
        "active_subscriptions": active_subs,
        "total_runs": total_runs,
        "monthly_revenue": round(monthly_revenue, 2),
        "cache": {
            "domains": domains_result.count or 0,
            "companies": companies_result.count or 0,
            "ceos": ceos_result.count or 0
        }
    }
