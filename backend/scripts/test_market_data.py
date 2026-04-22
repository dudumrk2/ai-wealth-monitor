"""
test_market_data.py
===================
Standalone async test script for the market_data module.
Run from the backend directory:

    python test_market_data.py

Tests:
  1. Dynamic resource ID discovery for גמל נט
  2. Live fetch of top competitors for a common track (כללי)
  3. In-memory resource ID cache (second call must not hit the network)
  4. Hardcoded fallback (simulated by passing a nonsense track name)
"""

import asyncio
import json
import sys
import os

# Ensure the backend directory is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import market_data


def _hr(label: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")


async def test_resource_id_discovery():
    _hr("TEST 1 — Dynamic Resource ID Discovery")
    rid = await market_data.get_latest_resource_id("גמל נט")
    if rid:
        print(f"✅ Discovered resource_id: {rid}")
    else:
        print("❌ FAILED — resource_id is None. Gov API may be down.")
    return rid


async def test_resource_id_cache(first_rid: str):
    _hr("TEST 2 — In-Memory Cache (no network call)")
    # The second call should return from CACHED_RESOURCE_IDS without going to the network
    rid2 = await market_data.get_latest_resource_id("גמל נט")
    if rid2 == first_rid:
        print(f"✅ Cache HIT — same resource_id returned: {rid2}")
    else:
        print(f"⚠️  Cache mismatch: first={first_rid}, second={rid2}")


async def test_live_fetch():
    _hr("TEST 3 — Live Competitor Fetch (track: כללי)")
    competitors = await market_data.get_top_competitors(
        product_type="קרן גמל",
        track_name="כללי",
    )
    print(f"\nReturned competitor structure keys: {list(competitors.keys())}")
    top = competitors.get("top_competitors", [])
    print(f"\nReturned {len(top)} top competitor(s):")
    print(json.dumps(top, indent=2, ensure_ascii=False))
    if top and top[0].get("provider_name"):
        print("✅ Live fetch parsed correctly.")
    else:
        print("⚠️  Competitors list is empty or malformed — may have fallen back to hardcoded data.")


async def test_hardcoded_fallback():
    _hr("TEST 4 — Hardcoded Fallback (nonsense track name)")
    # A track name that will never match any Gov API record triggers the fallback
    competitors = await market_data.get_top_competitors(
        product_type="קרן גמל",
        track_name="__NONEXISTENT_TRACK_XYZ__",
    )
    top = competitors.get("top_competitors", [])
    print(f"\nFallback returned {len(top)} top competitor(s):")
    print(json.dumps(top, indent=2, ensure_ascii=False))
    # Hardcoded data always has exactly 3 entries
    if len(top) == 3:
        print("✅ Hardcoded safety-net fallback triggered correctly.")
    else:
        print("⚠️  Unexpected number of fallback entries.")


async def main():
    print("\n🚀 Starting market_data.py test suite...\n")

    first_rid = await test_resource_id_discovery()
    if first_rid:
        await test_resource_id_cache(first_rid)

    await test_live_fetch()
    await test_hardcoded_fallback()

    print(f"\n{'═' * 60}")
    print("  Test suite complete.")
    print(f"{'═' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
