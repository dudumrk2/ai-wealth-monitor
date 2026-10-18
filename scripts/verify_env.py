#!/usr/bin/env python3
"""
Pre-deployment Environment Verification Script.

Usage:
    python scripts/verify_env.py [--env-file backend/.env]

Checks that all mandatory production environment variables are present and non-empty
before deploying to Google Cloud Run, preventing accidental deployment of broken revisions.
"""
import os
import sys
import argparse
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from env_validator import MANDATORY_ENV_VARS, get_secret_from_sm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Verify environment variables before deployment.")
    parser.add_argument(
        "--env-file",
        default=str(backend_dir / ".env"),
        help="Path to .env file to load (default: backend/.env)",
    )
    parser.add_argument(
        "--check-secret-manager",
        action="store_true",
        default=True,
        help="Check Google Cloud Secret Manager for missing variables as fallback",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if env_path.exists():
        print(f"📄 Loading environment from: {env_path}")
        load_dotenv(dotenv_path=str(env_path))
    else:
        print(f"ℹ️  No env file found at '{env_path}'. Checking active process environment...")

    print("\n🔍 Validating mandatory production environment variables:\n")
    missing_vars = []

    for var in MANDATORY_ENV_VARS:
        val = os.getenv(var, "").strip()
        if val:
            print(f"  ✅ {var} : Present")
        else:
            # Check Secret Manager
            sm_val = get_secret_from_sm(var) if args.check_secret_manager else None
            if sm_val:
                print(f"  🔄 {var} : Missing in local env, but found in Secret Manager")
            else:
                print(f"  ❌ {var} : MISSING")
                missing_vars.append(var)

    print("\n" + "=" * 50)
    if missing_vars:
        print(f"🚨 PRE-DEPLOY CHECK FAILED: {len(missing_vars)} mandatory variable(s) missing:")
        for var in missing_vars:
            print(f"   • {var}")
        print("\nPlease supply them via --set-env-vars, --env-vars-file, or in Secret Manager.")
        print("=" * 50 + "\n")
        sys.exit(1)
    else:
        print("✨ PRE-DEPLOY CHECK PASSED: All mandatory variables verified.")
        print("Safe to proceed with Cloud Run deployment.")
        print("=" * 50 + "\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
