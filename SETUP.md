# ICP Compute - Complete Setup Guide

This guide will walk you through setting up ICPX locally and deploying to production.

---

## Part 1: Get API Keys

### 1. SerpAPI (Google Search)
**Cost**: Free tier: 100 searches/mo, then $50/mo for 5,000 searches

1. Go to https://serpapi.com
2. Sign up for an account
3. Go to Dashboard → API Key
4. Copy your API key
5. **Save it**: `SERP_API_KEY=your_key_here`

### 2. Grok API (AI)
**Cost**: Pay-as-you-go, ~$0.01-0.02 per request

1. Go to https://console.x.ai
2. Sign up / login with X account
3. Go to API Keys
4. Create new API key
5. **Save it**: `GROK_API_KEY=xai-your_key_here`

### 3. Supabase (Database)
**Cost**: Free tier, then $25/mo for Pro

1. Go to https://supabase.com
2. Create new project
3. Choose a region (closest to your users)
4. Wait for project to provision (~2 minutes)
5. Go to Settings → API
6. **Save these**:
   - Project URL: `SUPABASE_URL=https://xxx.supabase.co`
   - Anon/Public Key: `SUPABASE_KEY=eyJxxx...`

### 4. Stripe (Payments)
**Cost**: Free, 2.9% + $0.30 per transaction

1. Go to https://stripe.com
2. Sign up for account
3. Go to Developers → API Keys
4. **For testing**, use Test mode keys:
   - Secret Key: `STRIPE_SECRET_KEY=sk_test_xxx`
5. Go to Developers → Webhooks
6. Add endpoint: `https://your-domain.com/billing/webhook`
7. Select events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`
8. **Save**: `STRIPE_WEBHOOK_SECRET=whsec_xxx`

### 5. Cloudflare R2 (CSV Storage)
**Cost**: Free tier: 10GB storage, then $0.015/GB/mo

1. Go to https://dash.cloudflare.com
2. Go to R2 → Create bucket
3. Bucket name: `icp-leads`
4. Go to Manage R2 API Tokens
5. Create API token with read/write access
6. **Save these**:
   - `R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com`
   - `R2_ACCESS_KEY=xxx`
   - `R2_SECRET_KEY=xxx`
7. Enable public access to bucket for CSV downloads
8. Get public URL: `R2_PUBLIC_URL=https://pub-xxx.r2.dev`

---

## Part 2: Local Setup

### Step 1: Install Redis

**Mac:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Windows:**
```bash
# Use WSL2 or download from:
https://github.com/tporadowski/redis/releases
```

**Verify Redis:**
```bash
redis-cli ping
# Should return: PONG
```

### Step 2: Create .env File

```bash
cd ICPX
cp .env.example .env
nano .env  # Or use your favorite editor
```

Fill in ALL the API keys you collected above.

**Don't skip any!** The app won't work without them.

### Step 3: Set Up Supabase Database

1. Go to your Supabase project
2. Click "SQL Editor" in the left sidebar
3. Create a new query
4. Copy the entire contents of `database/schema.sql`
5. Paste into SQL Editor
6. Click "Run" (or press Cmd/Ctrl+Enter)
7. You should see: "Success. No rows returned"

**Verify tables created:**
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';
```

You should see: `users`, `icps`, `runs`, `domains`, `companies`, `ceos`

### Step 4: Create Stripe Product

1. Go to Stripe Dashboard → Products
2. Click "Add product"
3. Name: "ICP Compute Monthly"
4. Description: "$9.99/mo LinkedIn lead generation"
5. Pricing: Recurring, $9.99/month
6. Click "Save product"
7. Copy the **Price ID** (starts with `price_`)
8. Add to `.env`: `STRIPE_PRICE_ID=price_xxx`

### Step 5: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 6: Test Local Server

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - API Server:**
```bash
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 3 - Background Worker:**
```bash
source venv/bin/activate
dramatiq main
```

**Verify:**
- Open browser: http://localhost:8000
- You should see: `{"message": "icp.compute — Pure LinkedIn magic at $9.99/mo", ...}`

---

## Part 3: Test the System

### Test 1: Create User

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'
```

**Expected response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "email": "test@test.com",
    "subscribed": false
  }
}
```

**Save the access_token!** You'll need it for next tests.

### Test 2: Check Supabase

1. Go to Supabase Dashboard → Table Editor
2. Open `users` table
3. You should see your test user!

### Test 3: Simulate Subscription (for testing)

```bash
# Manually update user in Supabase
# Go to Table Editor → users → find your user → edit:
# - subscribed: true
# - runs_remaining: 1
```

Or run this SQL in Supabase:
```sql
UPDATE users
SET subscribed = true, runs_remaining = 1
WHERE email = 'test@test.com';
```

### Test 4: Start Lead Generation (Small Test)

```bash
# Replace YOUR_TOKEN with the access_token from Test 1
curl -X POST http://localhost:8000/compute/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "icp": {
      "industry": "SaaS",
      "min_size": 10,
      "max_size": 50,
      "location": "San Francisco",
      "pain_points": "Manual data entry"
    },
    "target": 10
  }'
```

**Expected response:**
```json
{
  "job_id": "job_abc123",
  "status": "started",
  "target": 10
}
```

**Watch the logs!**
- Terminal 3 (worker) should show processing
- This will use real API credits!

### Test 5: Verify Caching

Run the SAME request again. It should be faster and cheaper!

Check Supabase → `domains`, `companies`, `ceos` tables - you should see cached data.

---

## Part 4: Deploy to Production (Render.com)

### Why Render?
- Easy deployment from GitHub
- Built-in Redis
- Auto-deploys on git push
- Free tier available

### Step 1: Create Render Account

1. Go to https://render.com
2. Sign up with GitHub
3. Authorize Render to access your repos

### Step 2: Create Redis Instance

1. Dashboard → New → Redis
2. Name: `icpx-redis`
3. Region: Choose closest to your users
4. Plan: Free tier (25MB) is enough for testing
5. Click "Create Redis"
6. **Copy the Internal Redis URL** (starts with `redis://`)

### Step 3: Create Web Service

1. Dashboard → New → Web Service
2. Connect your ICPX repo
3. Branch: `claude/build-desperation-engine-01N2rSYvxr7GDqQdRZqTeP91`
4. Settings:
   - **Name**: `icpx-api`
   - **Region**: Same as Redis
   - **Branch**: your branch
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free tier to start

5. **Environment Variables** - Add ALL of these:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   JWT_SECRET_KEY=generate_new_secret_openssl_rand_hex_32
   STRIPE_SECRET_KEY=sk_live_xxx (use LIVE keys for production)
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   STRIPE_PRICE_ID=price_xxx
   SERP_API_KEY=your_serpapi_key
   GROK_API_KEY=your_grok_key
   R2_ENDPOINT=your_r2_endpoint
   R2_ACCESS_KEY=your_r2_access
   R2_SECRET_KEY=your_r2_secret
   R2_PUBLIC_URL=your_r2_public_url
   REDIS_URL=<paste the Internal Redis URL from Step 2>
   FRONTEND_URL=https://your-frontend-domain.com
   ENVIRONMENT=production
   ```

6. Click "Create Web Service"
7. Wait for deployment (~3-5 minutes)
8. **Copy the service URL**: `https://icpx-api.onrender.com`

### Step 4: Create Background Worker

1. Dashboard → New → Background Worker
2. Connect same repo
3. Settings:
   - **Name**: `icpx-worker`
   - **Region**: Same as Web Service
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `dramatiq main`
   - **Plan**: Free tier

4. **Environment Variables**: Copy ALL from Web Service above

5. Click "Create Background Worker"

### Step 5: Update Stripe Webhook

1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://icpx-api.onrender.com/billing/webhook`
3. Select events:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.deleted`
   - `customer.subscription.updated`
4. Copy new webhook secret
5. Update `STRIPE_WEBHOOK_SECRET` in Render environment variables

### Step 6: Test Production

```bash
# Health check
curl https://icpx-api.onrender.com/

# Create user
curl -X POST https://icpx-api.onrender.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "prod@test.com", "password": "test123"}'
```

---

## Part 5: Monitoring

### Render Logs
- Dashboard → Your service → Logs
- Watch for errors, API calls, job processing

### Supabase Logs
- Dashboard → Logs → API Logs
- Monitor database queries

### Stripe Dashboard
- Payments → View all transactions
- Subscriptions → Monitor active subs

### Cost Tracking

Monitor in Supabase:
```sql
SELECT
  SUM(cost) as total_cost,
  COUNT(*) as total_runs,
  AVG(cost) as avg_cost_per_run
FROM runs;
```

---

## Troubleshooting

### "Connection refused" to Redis
```bash
# Check if Redis is running
redis-cli ping

# Mac: restart Redis
brew services restart redis

# Linux: restart Redis
sudo systemctl restart redis
```

### "Invalid API key" errors
- Double-check your `.env` file
- Make sure no extra spaces or quotes
- Verify keys are active in respective dashboards

### Supabase connection errors
- Check URL and Key in `.env`
- Verify database schema is created
- Check Supabase dashboard for service status

### Dramatiq worker not processing jobs
- Check Redis connection
- Verify worker is running (check logs)
- Make sure Redis URL matches in both API and worker

### Stripe webhook failing
- Verify webhook secret is correct
- Check endpoint URL is accessible
- Test with Stripe CLI: `stripe listen --forward-to localhost:8000/billing/webhook`

---

## Next Steps

Once everything is working:

1. **Create your first real ICP** via the API
2. **Run a small batch** (target: 10-50 leads)
3. **Monitor costs** in each API dashboard
4. **Verify caching** is working (check Supabase tables)
5. **Build the frontend** (Next.js recommended)
6. **Set up monitoring** (Sentry, LogRocket, etc.)
7. **Scale up** gradually

---

## Cost Estimates

**For 1,000 users, 1 run/user/month:**

| Service | Cost |
|---------|------|
| SerpAPI (5,000 searches/mo) | $50 |
| Grok API (1,000 runs) | $20 |
| Supabase Pro | $25 |
| Render Web Service | $7 |
| Render Worker | $7 |
| Redis | $7 |
| Cloudflare R2 | $1 |
| Stripe fees (2.9%) | $290 |
| **Total** | **$407** |
| **Revenue** ($9.99 × 1,000) | **$9,990** |
| **Profit** | **$9,583** |
| **Margin** | **95.9%** |

---

## Support

If you run into issues:
1. Check the logs (Render, Supabase, local terminals)
2. Verify all API keys are valid
3. Test each component individually
4. Check this troubleshooting guide

---

**Ready to print money? Let's go! 🚀**
