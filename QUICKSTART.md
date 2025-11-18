# ICP Compute - Quick Start (5 Minutes)

The fastest way to get ICPX running locally.

---

## Step 1: Get API Keys (2 min)

Open these URLs and grab your keys:

1. **SerpAPI**: https://serpapi.com → Dashboard → Copy API Key
2. **Grok**: https://console.x.ai → API Keys → Create New
3. **Supabase**: https://supabase.com → New Project → Settings → API → Copy URL + Anon Key
4. **Stripe**: https://stripe.com → Developers → API Keys → Copy Test Secret Key

---

## Step 2: Setup (2 min)

```bash
# 1. Install Redis
brew install redis && brew services start redis  # Mac
# OR
sudo apt install redis-server && sudo systemctl start redis  # Linux

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env and paste your API keys from Step 1
```

---

## Step 3: Setup Supabase Database (1 min)

1. Go to your Supabase project → SQL Editor
2. Copy contents of `database/schema.sql`
3. Paste and click "Run"
4. Done!

---

## Step 4: Start Everything (< 1 min)

```bash
./start.sh
```

That's it! The script starts:
- Redis (if not running)
- API Server on http://localhost:8000
- Background Worker
- All in a tmux session

---

## Step 5: Test It

Open http://localhost:8000 in your browser.

You should see:
```json
{
  "message": "icp.compute — Pure LinkedIn magic at $9.99/mo",
  "status": "operational",
  "version": "18.0.0"
}
```

---

## What's Next?

### Create a test user:
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}'
```

### Give them a free run (in Supabase):
```sql
UPDATE users
SET subscribed = true, runs_remaining = 1
WHERE email = 'test@test.com';
```

### Generate leads:
```bash
curl -X POST http://localhost:8000/compute/start \
  -H "Authorization: Bearer YOUR_TOKEN_FROM_SIGNUP" \
  -H "Content-Type: application/json" \
  -d '{
    "icp": {
      "industry": "SaaS",
      "min_size": 10,
      "max_size": 50,
      "location": "San Francisco"
    },
    "target": 10
  }'
```

Watch the worker logs to see the 5-layer algorithm in action!

---

## Troubleshooting

**Validation Script:**
```bash
python validate_setup.py
```

This checks everything and tells you exactly what's missing.

**Manual Debugging:**
```bash
# Test Redis
redis-cli ping  # Should return PONG

# Test API
curl http://localhost:8000

# Check logs
tmux attach -t icpx  # See all service logs
```

---

## Deploy to Production

See **SETUP.md** for complete Render.com deployment guide.

TLDR:
1. Push code to GitHub
2. Connect Render.com
3. Create Redis + Web Service + Worker
4. Add environment variables
5. Deploy!

---

**Need help?** Check `SETUP.md` for the complete guide.

**Ready to print money?** 🚀
