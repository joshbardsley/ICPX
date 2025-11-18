#!/usr/bin/env python3
"""
ICP Compute - Setup Validation Script
Checks if your environment is ready to run
"""

import os
import sys
import subprocess
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def check_pass(text):
    print(f"{GREEN}✓{RESET} {text}")

def check_fail(text):
    print(f"{RED}✗{RESET} {text}")

def check_warn(text):
    print(f"{YELLOW}⚠{RESET} {text}")

def check_python_version():
    """Check Python version >= 3.11"""
    print_header("Checking Python Version")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 11:
        check_pass(f"Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        check_fail(f"Python {version.major}.{version.minor}.{version.micro} - Need 3.11+")
        return False

def check_redis():
    """Check if Redis is running"""
    print_header("Checking Redis")
    try:
        result = subprocess.run(
            ['redis-cli', 'ping'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and 'PONG' in result.stdout:
            check_pass("Redis is running")
            return True
        else:
            check_fail("Redis not responding")
            return False
    except FileNotFoundError:
        check_fail("Redis CLI not found - is Redis installed?")
        return False
    except subprocess.TimeoutExpired:
        check_fail("Redis connection timeout")
        return False

def check_env_file():
    """Check if .env file exists and has required keys"""
    print_header("Checking Environment Variables")

    env_path = Path('.env')
    if not env_path.exists():
        check_fail(".env file not found")
        check_warn("Copy .env.example to .env and fill in your API keys")
        return False

    check_pass(".env file exists")

    # Load .env
    required_keys = [
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'JWT_SECRET_KEY',
        'STRIPE_SECRET_KEY',
        'STRIPE_WEBHOOK_SECRET',
        'STRIPE_PRICE_ID',
        'SERP_API_KEY',
        'GROK_API_KEY',
        'R2_ENDPOINT',
        'R2_ACCESS_KEY',
        'R2_SECRET_KEY',
        'R2_PUBLIC_URL',
    ]

    env_vars = {}
    with open('.env') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

    missing = []
    empty = []

    for key in required_keys:
        if key not in env_vars:
            missing.append(key)
            check_fail(f"{key} - MISSING")
        elif not env_vars[key] or env_vars[key].startswith('your-') or env_vars[key].startswith('your_'):
            empty.append(key)
            check_warn(f"{key} - NOT SET (still has placeholder)")
        else:
            check_pass(f"{key} - OK")

    if missing or empty:
        print(f"\n{YELLOW}You need to set these in .env:{RESET}")
        for key in missing + empty:
            print(f"  - {key}")
        return False

    return True

def check_dependencies():
    """Check if Python dependencies are installed"""
    print_header("Checking Python Dependencies")

    required = [
        'fastapi',
        'uvicorn',
        'dramatiq',
        'redis',
        'supabase',
        'stripe',
        'boto3',
        'httpx',
        'jose',
        'passlib'
    ]

    all_installed = True

    for package in required:
        try:
            __import__(package)
            check_pass(f"{package} installed")
        except ImportError:
            check_fail(f"{package} NOT installed")
            all_installed = False

    if not all_installed:
        print(f"\n{YELLOW}Run: pip install -r requirements.txt{RESET}")
        return False

    return True

def check_supabase_connection():
    """Check if Supabase is accessible"""
    print_header("Checking Supabase Connection")

    try:
        from supabase import create_client
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')

        if not url or not key:
            check_fail("Supabase credentials not in environment")
            return False

        client = create_client(url, key)

        # Try to query users table
        result = client.table('users').select('id').limit(1).execute()

        check_pass("Connected to Supabase")
        check_pass("Database schema is set up (users table exists)")
        return True

    except Exception as e:
        check_fail(f"Supabase connection failed: {str(e)}")
        check_warn("Make sure you ran database/schema.sql in Supabase")
        return False

def check_stripe_connection():
    """Check if Stripe is accessible"""
    print_header("Checking Stripe Connection")

    try:
        import stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

        if not stripe.api_key:
            check_fail("Stripe API key not in environment")
            return False

        # Try to list products
        products = stripe.Product.list(limit=1)

        check_pass("Connected to Stripe")

        # Check if price exists
        price_id = os.getenv('STRIPE_PRICE_ID')
        if price_id:
            try:
                price = stripe.Price.retrieve(price_id)
                check_pass(f"Stripe Price exists: ${price.unit_amount/100}/mo")
            except:
                check_warn("Stripe Price ID not found - create product in Stripe Dashboard")

        return True

    except Exception as e:
        check_fail(f"Stripe connection failed: {str(e)}")
        return False

def print_summary(checks):
    """Print summary of all checks"""
    print_header("Summary")

    passed = sum(checks.values())
    total = len(checks)

    for name, status in checks.items():
        if status:
            check_pass(name)
        else:
            check_fail(name)

    print(f"\n{BLUE}Passed: {passed}/{total}{RESET}")

    if passed == total:
        print(f"\n{GREEN}✓ All checks passed! You're ready to run ICPX!{RESET}")
        print(f"\n{BLUE}Next steps:{RESET}")
        print("1. Terminal 1: redis-server")
        print("2. Terminal 2: uvicorn main:app --reload")
        print("3. Terminal 3: dramatiq main")
        print("4. Open http://localhost:8000")
        return True
    else:
        print(f"\n{RED}✗ Some checks failed. Fix the issues above and try again.{RESET}")
        print(f"\n{YELLOW}See SETUP.md for detailed instructions.{RESET}")
        return False

def main():
    print(f"{BLUE}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         ICP COMPUTE - SETUP VALIDATION                  ║")
    print("║         Checking if your environment is ready...        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

    # Load .env if it exists
    env_path = Path('.env')
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv()

    # Run all checks
    checks = {
        "Python 3.11+": check_python_version(),
        "Redis": check_redis(),
        "Environment Variables": check_env_file(),
        "Python Dependencies": check_dependencies(),
    }

    # Only check API connections if env vars are set
    if checks["Environment Variables"]:
        checks["Supabase Connection"] = check_supabase_connection()
        checks["Stripe Connection"] = check_stripe_connection()

    # Print summary
    success = print_summary(checks)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # First, try to install python-dotenv if not available
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(f"{YELLOW}Installing python-dotenv...{RESET}")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'python-dotenv'], check=True)
        from dotenv import load_dotenv

    main()
