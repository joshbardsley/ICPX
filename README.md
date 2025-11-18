# ICP Compute v18 - Backend

**Pure LinkedIn magic at $9.99/mo**

Generate 800 verified LinkedIn CEO profiles in 20 minutes with deep ICP matching and aggressive caching.

---

## 🎯 Overview

### What This Does

- **Input**: User describes their Ideal Customer Profile
- **Process**: 5-layer algorithm with aggressive caching
- **Output**: 800 LinkedIn CEO profiles (CSV download)
- **Cost**: $0.36 → $0.01 (with caching)
- **Price**: $9.99/mo

### The Moat

**Aggressive caching reduces costs over time:**
- Run 1: $0.36 (fresh scraping)
- Run 10: $0.07 (80% cache hits)
- Run 100: $0.02 (95% cache hits)
- Run 1000: $0.01 (99% cache hits)

Result: **99%+ profit margins at scale**

---

## 🏗️ Architecture

### 5-Layer Algorithm

```
L1: Location → Zipcodes (SerpAPI, cached permanently)
↓
L2: Zipcodes → Domains (Google dorks, cached 90 days)
↓
L3: Domains → Company Signals (scraping, cached 30 days)
↓
L3.5: Signals → ICP Score (Grok AI, cached 60 days)
↓
L4: Company → CEO LinkedIn (dorks, cached permanently)
↓
CSV: Download 800 leads
```

### Tech Stack

**Backend:**
- FastAPI (Python 3.11+)
- Dramatiq (background jobs)
- Redis (caching + pub/sub)
- Supabase (Postgres database)

**External APIs:**
- SerpAPI (Google searches)
- Grok API (deep ICP matching)
- Stripe (billing)

**Infrastructure:**
- Render.com (backend + worker)
- Cloudflare R2 (CSV storage)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis installed locally
- Supabase account
- API keys: SerpAPI, Grok, Stripe

### 1. Clone & Setup

```bash
# Clone repo
git clone <repo-url>
cd ICPX

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env and fill in your API keys
nano .env
```

Required keys:
- `SERP_API_KEY` - Get from serpapi.com
- `GROK_API_KEY` - Get from x.ai
- `SUPABASE_URL` & `SUPABASE_KEY` - From Supabase dashboard
- `STRIPE_SECRET_KEY` - From Stripe dashboard
- `R2_*` - From Cloudflare R2

### 3. Database Setup

```bash
# Go to Supabase dashboard > SQL Editor
# Run the database/schema.sql file
```

Or use Supabase CLI:
```bash
supabase db push
```

### 4. Run Locally

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start API server
uvicorn main:app --reload --port 8000

# Terminal 3: Start background worker
dramatiq main

# API will be at: http://localhost:8000
```

---

## 📦 Project Structure

```
ICPX/
├── main.py              # FastAPI app, routes, WebSocket
├── auth.py              # Authentication (Supabase + JWT)
├── billing.py           # Stripe integration
├── chat.py              # Dual chat system (Grok)
├── compute.py           # 5-layer algorithm
├── cache.py             # Caching logic (the moat)
├── database.py          # Supabase operations
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── README.md            # This file
└── database/
    └── schema.sql       # Database schema
```

---

## 🎨 API Endpoints

### Authentication

```
POST /auth/signup
POST /auth/login
```

### Billing

```
POST /billing/checkout      # Create Stripe session
POST /billing/webhook       # Stripe webhooks
```

### ICP Management

```
POST /icps/save             # Save ICP
GET  /icps                  # List saved ICPs
```

### Chat

```
POST /chat/icp              # ICP Builder chat
POST /chat/research         # Research Assistant chat
```

### Lead Generation

```
POST /compute/start         # Start generation (returns job_id)
WS   /compute/stream/{id}   # WebSocket for real-time updates
GET  /user/runs             # Get runs remaining
```

---

## 🔥 Deployment

### Option 1: Render.com (Recommended)

**Step 1: Create Web Service**
1. Go to dashboard.render.com
2. New → Web Service
3. Connect GitHub repo
4. Settings:
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Step 2: Add Redis**
1. New → Redis
2. Copy `REDIS_URL` to environment variables

**Step 3: Add Worker Service**
1. New → Background Worker
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `dramatiq main`

**Step 4: Environment Variables**
Add all variables from `.env.example` to Render dashboard

**Step 5: Deploy**
- Push to GitHub → Auto-deploys

---

## 💰 Cost Analysis

### Per-Run Costs

| Layer | First Run | Cached |
|-------|-----------|--------|
| L1 Zips | $0.001 | $0.00 |
| L2 Domains | $0.30 | $0.00 |
| L3 Companies | $0.01 | $0.00 |
| L3.5 ICP Scores | $0.04 | $0.00 |
| L4 CEOs | $0.01 | $0.00 |
| **Total** | **$0.36** | **$0.01** |

### Monthly Economics (1,000 users)

```
Revenue:    $9,990  ($9.99 × 1,000 users)
Costs:
  Compute:     $360  ($0.36 × 1,000 runs)
  Infra:       $205  (Render + Supabase)
  Stripe:      $290  (2.9% of revenue)

Profit:    $9,135  (91.4% margin)
```

**At scale (10,000 users):**
- Revenue: $99,900/mo
- Costs: $5,000/mo (with caching)
- Profit: $94,900/mo (95% margin)

---

## 🧪 Testing

### Manual Testing

```bash
# 1. Create test user
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'

# 2. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'

# 3. Start generation
curl -X POST http://localhost:8000/compute/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"icp": {"industry": "SaaS", "min_size": 50, "max_size": 200, "location": "United States"}, "target": 10}'
```

---

## 🐛 Troubleshooting

### Common Issues

**1. Redis Connection Error**
```bash
# Start Redis
redis-server

# Or install Redis
brew install redis  # Mac
sudo apt install redis  # Linux
```

**2. Supabase Connection Error**
- Check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Verify database schema is created (run `database/schema.sql`)

**3. Grok API Error**
- Verify `GROK_API_KEY` is valid
- Check API quota at x.ai dashboard

**4. SerpAPI Rate Limit**
- Upgrade SerpAPI plan
- Increase delay in `compute.py` L2 (currently 0.3s)

---

## 🔐 Security

### Best Practices

1. **Never commit .env file**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use strong JWT secret**
   ```bash
   openssl rand -hex 32
   ```

3. **Supabase RLS is enabled**
   - Row Level Security in `database/schema.sql`
   - Users can only access their own data

---

## 🎯 Roadmap

### v18 (Current)
- ✅ 5-layer algorithm
- ✅ Aggressive caching
- ✅ Dual chat system
- ✅ Stripe billing ($9.99/mo)
- ✅ Real-time streaming

### v19 (Next)
- [ ] Chrome extension (one-click enrich)
- [ ] Team features
- [ ] ICP templates library
- [ ] Success metrics dashboard

---

## 💬 Support

For questions or issues, please open an issue in the GitHub repository.

---

**We are compute. We are compliant. We are winning.**

**$9.99/mo. 99% margins. Pure LinkedIn magic.**
