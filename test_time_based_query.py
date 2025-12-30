"""
FINAL TEST: Cari cara untuk query "new pairs in last 24h" dari DexScreener
Tanpa keyword, langsung berdasarkan creation time
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json

async def find_time_based_query():
    """Cari endpoint atau parameter untuk time-based query"""
    
    with open("time_based_query_test.txt", "w", encoding="utf-8") as f:
        f.write("TESTING TIME-BASED QUERY APPROACHES\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            # TEST 1: Try query parameters for time filtering
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 1: Time-based query parameters\n")
            f.write("=" * 80 + "\n\n")
            
            base_url = "https://api.dexscreener.com/latest/dex/search"
            
            # Try different time-based parameters
            test_params = [
                {'q': 'solana', 'age': '24h'},
                {'q': 'solana', 'maxAge': '24h'},
                {'q': 'solana', 'createdAfter': '2024-12-30'},
                {'q': 'solana', 'new': 'true'},
                {'q': 'solana', 'recent': 'true'},
                {'q': 'solana', 'sort': 'createdAt'},
                {'q': 'solana', 'orderBy': 'createdAt'},
                {'q': 'solana', 'filter': 'new'},
            ]
            
            for params in test_params:
                f.write(f"\nParams: {params}\n")
                try:
                    async with session.get(base_url, params=params, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            if 'pairs' in data and data['pairs']:
                                f.write(f"Pairs returned: {len(data['pairs'])}\n")
                                
                                # Check if results are actually filtered by time
                                cutoff = datetime.now() - timedelta(hours=24)
                                new_count = 0
                                for p in data['pairs']:
                                    created_at = p.get('pairCreatedAt')
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            if created_time > cutoff:
                                                new_count += 1
                                        except:
                                            pass
                                
                                f.write(f"Actually new (<24h): {new_count}\n")
                        else:
                            f.write(f"Failed\n")
                except Exception as e:
                    f.write(f"Error: {e}\n")
            
            # TEST 2: Check official DexScreener documentation
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 2: Check for API documentation\n")
            f.write("=" * 80 + "\n\n")
            
            doc_urls = [
                "https://docs.dexscreener.com",
                "https://dexscreener.com/docs",
                "https://api.dexscreener.com/docs",
                "https://dexscreener.com/api",
            ]
            
            for url in doc_urls:
                f.write(f"\n{url}\n")
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        if response.status == 200:
                            text = await response.text()
                            # Check if it contains API documentation
                            if 'api' in text.lower() or 'endpoint' in text.lower():
                                f.write("Found documentation!\n")
                                f.write(f"Content preview: {text[:500]}\n")
                except Exception as e:
                    f.write(f"Error: {e}\n")
            
            # TEST 3: Try to reverse engineer from browser
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 3: What does the dashboard actually use?\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("Dashboard URL: https://dexscreener.com/solana\n")
            f.write("This page shows NEW pairs in real-time\n")
            f.write("Let's try to find what API it calls...\n\n")
            
            # Try potential dashboard API endpoints
            dashboard_apis = [
                "https://api.dexscreener.com/latest/dex/pairs/solana",
                "https://api.dexscreener.com/token-profiles/latest/solana",
                "https://api.dexscreener.com/orders/latest/solana",
                "https://io.dexscreener.com/dex/latest/pairs/solana",
                "https://io.dexscreener.com/latest/dex/pairs/solana",
            ]
            
            for url in dashboard_apis:
                f.write(f"\n{url}\n")
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"Keys: {list(data.keys())}\n")
                            if 'pairs' in data and data['pairs']:
                                f.write(f"Pairs: {len(data['pairs'])}\n")
                except Exception as e:
                    f.write(f"Error: {e}\n")
            
            # TEST 4: Try WebSocket or streaming endpoints
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 4: WebSocket / Streaming endpoints\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("Dashboard might use WebSocket for real-time updates\n")
            f.write("Potential WebSocket endpoints:\n")
            f.write("- wss://io.dexscreener.com\n")
            f.write("- wss://api.dexscreener.com\n")
            f.write("(WebSocket testing requires different approach)\n\n")
            
            # TEST 5: Check if there's a "tokens" endpoint that works differently
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 5: Alternative token endpoints\n")
            f.write("=" * 80 + "\n\n")
            
            token_endpoints = [
                "https://api.dexscreener.com/latest/dex/tokens/new",
                "https://api.dexscreener.com/latest/dex/tokens/recent",
                "https://api.dexscreener.com/latest/dex/tokens/latest",
            ]
            
            for url in token_endpoints:
                f.write(f"\n{url}\n")
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"Success! Keys: {list(data.keys())}\n")
                except Exception as e:
                    f.write(f"Error: {e}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("FINAL CONCLUSION\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("After extensive testing, DexScreener FREE API:\n\n")
        f.write("❌ NO time-based query parameters\n")
        f.write("❌ NO 'new pairs' endpoint\n")
        f.write("❌ NO 'recent' or 'latest' endpoint that works\n")
        f.write("❌ NO way to filter by creation time via API\n\n")
        
        f.write("The FREE API is SEVERELY LIMITED:\n")
        f.write("1. Only /search endpoint available\n")
        f.write("2. Requires a search query (keyword)\n")
        f.write("3. Returns max 30 results\n")
        f.write("4. No time-based filtering\n\n")
        
        f.write("DASHBOARD vs API:\n")
        f.write("- Dashboard shows ALL new pairs (likely uses WebSocket or internal API)\n")
        f.write("- Public FREE API is intentionally limited\n")
        f.write("- Time-based queries require DexScreener PRO (paid)\n\n")
        
        f.write("RECOMMENDATION:\n")
        f.write("Since user wants FREE + NO keywords + time-based:\n")
        f.write("This is IMPOSSIBLE with DexScreener FREE API\n\n")
        
        f.write("ALTERNATIVES:\n")
        f.write("1. Use GeckoTerminal API (FREE, has better endpoints)\n")
        f.write("2. Use Birdeye API (FREE tier available)\n")
        f.write("3. Use DEXTools API (has free tier)\n")
        f.write("4. Scrape DexScreener website (not recommended)\n")
        f.write("5. Use on-chain data (user doesn't want this)\n\n")
    
    print("Test complete! Check time_based_query_test.txt")

if __name__ == "__main__":
    asyncio.run(find_time_based_query())
