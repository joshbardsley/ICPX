-- ============================================================================
-- ICP COMPUTE DATABASE SCHEMA
-- Supabase (Postgres)
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,

  -- Subscription
  subscribed BOOLEAN DEFAULT FALSE,
  runs_remaining INTEGER DEFAULT 0,
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  subscription_status TEXT,
  subscription_started_at TIMESTAMP,
  subscription_cancelled_at TIMESTAMP,
  last_payment_at TIMESTAMP,

  -- Metadata
  is_admin BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe_customer ON users(stripe_customer_id);

-- ============================================================================
-- ICPS TABLE (Saved ICPs)
-- ============================================================================

CREATE TABLE icps (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  criteria JSONB NOT NULL,

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_icps_user ON icps(user_id);
CREATE INDEX idx_icps_created ON icps(created_at DESC);

-- ============================================================================
-- RUNS TABLE (Generation History)
-- ============================================================================

CREATE TABLE runs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  icp_id UUID REFERENCES icps(id) ON DELETE SET NULL,

  leads_count INTEGER NOT NULL,
  csv_url TEXT NOT NULL,
  cost DECIMAL(10, 2) NOT NULL,

  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_runs_user ON runs(user_id);
CREATE INDEX idx_runs_created ON runs(created_at DESC);

-- ============================================================================
-- CACHE: DOMAINS TABLE
-- ============================================================================

CREATE TABLE domains (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  domain TEXT UNIQUE NOT NULL,

  data JSONB,  -- Store domain discovery results

  first_seen TIMESTAMP DEFAULT NOW(),
  last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_domains_domain ON domains(domain);
CREATE INDEX idx_domains_updated ON domains(last_updated DESC);

-- ============================================================================
-- CACHE: COMPANIES TABLE
-- ============================================================================

CREATE TABLE companies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  domain TEXT UNIQUE NOT NULL,

  signals JSONB NOT NULL,  -- {size, industry, hiring, founded, etc.}

  last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_companies_updated ON companies(last_updated DESC);

-- ============================================================================
-- CACHE: CEOS TABLE
-- ============================================================================

CREATE TABLE ceos (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  domain TEXT UNIQUE NOT NULL,

  ceo_data JSONB NOT NULL,  -- {name, title, linkedin_url}

  found_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ceos_domain ON ceos(domain);

-- ============================================================================
-- UPDATED_AT TRIGGER (Auto-update timestamps)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_icps_updated_at
  BEFORE UPDATE ON icps
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- RPC FUNCTIONS
-- ============================================================================

-- Decrement runs (atomic)
CREATE OR REPLACE FUNCTION decrement_runs(user_id_param UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE users
  SET runs_remaining = GREATEST(0, runs_remaining - 1)
  WHERE id = user_id_param;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS (for analytics)
-- ============================================================================

CREATE OR REPLACE VIEW user_stats AS
SELECT
  u.id,
  u.email,
  u.subscribed,
  u.runs_remaining,
  u.created_at,
  COUNT(DISTINCT r.id) as total_runs,
  SUM(r.leads_count) as total_leads_generated,
  SUM(r.cost) as total_cost
FROM users u
LEFT JOIN runs r ON u.id = r.user_id
GROUP BY u.id, u.email, u.subscribed, u.runs_remaining, u.created_at;

CREATE OR REPLACE VIEW cache_stats AS
SELECT
  (SELECT COUNT(*) FROM domains) as domains_cached,
  (SELECT COUNT(*) FROM companies) as companies_cached,
  (SELECT COUNT(*) FROM ceos) as ceos_cached,
  (SELECT COUNT(*) FROM domains WHERE last_updated > NOW() - INTERVAL '30 days') as domains_fresh,
  (SELECT COUNT(*) FROM companies WHERE last_updated > NOW() - INTERVAL '30 days') as companies_fresh;

-- ============================================================================
-- RLS (Row Level Security)
-- ============================================================================

-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE icps ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;

-- Policies: Users can only see their own data
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON users
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own ICPs" ON icps
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own runs" ON runs
  FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION get_total_users()
RETURNS INTEGER AS $$
BEGIN
  RETURN (SELECT COUNT(*) FROM users);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_active_subscriptions()
RETURNS INTEGER AS $$
BEGIN
  RETURN (SELECT COUNT(*) FROM users WHERE subscribed = TRUE);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_total_revenue()
RETURNS DECIMAL AS $$
BEGIN
  -- $9.99 per active subscription
  RETURN (SELECT COUNT(*) * 9.99 FROM users WHERE subscribed = TRUE);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DONE
-- ============================================================================
