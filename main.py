"""
ICP Compute Backend - Main Application
$9.99/mo LinkedIn lead generation with aggressive caching
"""

from fastapi import FastAPI, WebSocket, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import uuid
from datetime import datetime
import redis.asyncio as redis
import dramatiq
from dramatiq.brokers.redis import RedisBroker

from auth import get_current_user, signup, login
from billing import create_checkout, stripe_webhook
from chat import handle_icp_chat, handle_research_chat
from compute import start_lead_generation
from database import (
    save_icp,
    get_user_icps,
    record_run,
    check_user_subscription,
    get_user_runs_remaining
)

# Initialize FastAPI
app = FastAPI(
    title="icp.compute API",
    description="$9.99/mo LinkedIn lead generation",
    version="18.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://icp.compute.fbed.io", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Redis for WebSocket pub/sub
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

# Dramatiq for background jobs
redis_broker = RedisBroker(host="localhost", port=6379)
dramatiq.set_broker(redis_broker)

@app.get("/")
async def root():
    """Health check"""
    return {
        "message": "icp.compute — Pure LinkedIn magic at $9.99/mo",
        "status": "operational",
        "version": "18.0.0"
    }

@app.post("/auth/signup")
async def auth_signup(email: str, password: str):
    result = await signup(email, password)
    return result

@app.post("/auth/login")
async def auth_login(email: str, password: str):
    result = await login(email, password)
    return result

@app.post("/billing/checkout")
async def billing_checkout(user = Depends(get_current_user)):
    session = await create_checkout(user)
    return {"checkout_url": session.url}

@app.post("/billing/webhook")
async def billing_webhook_endpoint(request: Request):
    return await stripe_webhook(request)

@app.post("/compute/start")
async def compute_start(
    icp: dict,
    target: int = 800,
    user = Depends(get_current_user)
):
    if not user["subscribed"]:
        raise HTTPException(402, "Subscription required")

    if user["runs_remaining"] <= 0:
        raise HTTPException(403, "No runs remaining")

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    await start_lead_generation(job_id, icp, target, user["id"])

    return {
        "job_id": job_id,
        "status": "started",
        "target": target
    }

@app.websocket("/compute/stream/{job_id}")
async def compute_stream(websocket: WebSocket, job_id: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"job:{job_id}")

    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                await websocket.send_json(data)
                if data.get('complete'):
                    break
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await websocket.close()

@app.post("/icps/save")
async def save_icp_endpoint(name: str, criteria: dict, user = Depends(get_current_user)):
    icp_id = await save_icp(user["id"], name, criteria)
    return {"icp_id": icp_id}

@app.get("/icps")
async def get_icps(user = Depends(get_current_user)):
    icps = await get_user_icps(user["id"])
    return {"icps": icps}

@app.get("/user/runs")
async def get_runs(user = Depends(get_current_user)):
    remaining = await get_user_runs_remaining(user["id"])
    return {"runs_remaining": remaining}

@app.post("/chat/icp")
async def chat_icp(message: str, user = Depends(get_current_user)):
    response = await handle_icp_chat(message, user)
    return {"response": response}

@app.post("/chat/research")
async def chat_research(company: str, user = Depends(get_current_user)):
    insights = await handle_research_chat(company, user)
    return {"insights": insights}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
