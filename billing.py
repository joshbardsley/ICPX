"""
Billing Module - Stripe Integration
$9.99/mo subscription with 1 run per month
"""

import os
import stripe
from fastapi import Request, HTTPException
from supabase import create_client, Client

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = STRIPE_SECRET_KEY

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Price ID (create in Stripe dashboard)
PRICE_ID = os.getenv("STRIPE_PRICE_ID")

# ============================================================================
# CREATE CHECKOUT SESSION
# ============================================================================

async def create_checkout(user: dict):
    """Create Stripe checkout session for $9.99/mo"""

    # Check if user already has a customer ID
    customer_id = user.get("stripe_customer_id")

    if not customer_id:
        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": str(user["id"])}
        )
        customer_id = customer.id

        # Save customer ID
        supabase.table("users").update({
            "stripe_customer_id": customer_id
        }).eq("id", user["id"]).execute()

    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[
            {
                "price": PRICE_ID,
                "quantity": 1
            }
        ],
        mode="subscription",
        success_url=os.getenv("FRONTEND_URL") + "/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=os.getenv("FRONTEND_URL") + "/pricing",
        metadata={
            "user_id": str(user["id"])
        }
    )

    return session

# ============================================================================
# STRIPE WEBHOOKS
# ============================================================================

async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""

    # Get payload and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle events
    if event["type"] == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"])

    elif event["type"] == "invoice.paid":
        await handle_invoice_paid(event["data"]["object"])

    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_deleted(event["data"]["object"])

    elif event["type"] == "customer.subscription.updated":
        await handle_subscription_updated(event["data"]["object"])

    return {"status": "success"}

# ============================================================================
# WEBHOOK HANDLERS
# ============================================================================

async def handle_checkout_completed(session):
    """Handle successful checkout"""
    user_id = session["metadata"]["user_id"]
    subscription_id = session["subscription"]

    # Update user
    supabase.table("users").update({
        "subscribed": True,
        "runs_remaining": 1,  # Grant 1 run
        "stripe_subscription_id": subscription_id,
        "subscription_status": "active",
        "subscription_started_at": "NOW()"
    }).eq("id", user_id).execute()

    print(f"✅ User {user_id} subscribed")

async def handle_invoice_paid(invoice):
    """Handle successful payment (renewal)"""
    customer_id = invoice["customer"]

    # Get user by customer ID
    result = supabase.table("users").select("id").eq("stripe_customer_id", customer_id).execute()

    if result.data:
        user_id = result.data[0]["id"]

        # Grant another run
        supabase.table("users").update({
            "runs_remaining": 1,  # Reset to 1 run per month
            "last_payment_at": "NOW()"
        }).eq("id", user_id).execute()

        print(f"✅ User {user_id} renewed - granted 1 run")

async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    customer_id = subscription["customer"]

    # Get user
    result = supabase.table("users").select("id").eq("stripe_customer_id", customer_id).execute()

    if result.data:
        user_id = result.data[0]["id"]

        # Mark as unsubscribed
        supabase.table("users").update({
            "subscribed": False,
            "subscription_status": "cancelled",
            "subscription_cancelled_at": "NOW()"
        }).eq("id", user_id).execute()

        print(f"❌ User {user_id} cancelled subscription")

async def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    customer_id = subscription["customer"]
    status = subscription["status"]

    # Get user
    result = supabase.table("users").select("id").eq("stripe_customer_id", customer_id).execute()

    if result.data:
        user_id = result.data[0]["id"]

        # Update status
        supabase.table("users").update({
            "subscription_status": status
        }).eq("id", user_id).execute()

        print(f"📝 User {user_id} subscription updated: {status}")

# ============================================================================
# SUBSCRIPTION STATUS
# ============================================================================

async def get_subscription_status(user: dict):
    """Get user's subscription status"""

    if not user.get("stripe_subscription_id"):
        return {
            "subscribed": False,
            "status": "none",
            "runs_remaining": 0
        }

    # Fetch from Stripe
    try:
        subscription = stripe.Subscription.retrieve(user["stripe_subscription_id"])

        return {
            "subscribed": user["subscribed"],
            "status": subscription.status,
            "runs_remaining": user["runs_remaining"],
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except stripe.error.StripeError:
        return {
            "subscribed": user["subscribed"],
            "status": "error",
            "runs_remaining": user["runs_remaining"]
        }

# ============================================================================
# CANCEL SUBSCRIPTION
# ============================================================================

async def cancel_subscription(user: dict):
    """Cancel user's subscription"""

    if not user.get("stripe_subscription_id"):
        raise HTTPException(status_code=400, detail="No active subscription")

    # Cancel at period end (don't cancel immediately)
    stripe.Subscription.modify(
        user["stripe_subscription_id"],
        cancel_at_period_end=True
    )

    return {"message": "Subscription will be cancelled at the end of the billing period"}
