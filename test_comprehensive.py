"""
FINAL TEST: Mencari strategi terbaik untuk mendeteksi koin baru
Berdasarkan dokumentasi DexScreener yang sebenarnya
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_comprehensive():
    """Test comprehensive untuk menemukan koin baru"""
    
    with open("comprehensive_test.txt", "w", encoding="utf-8") as f:
        f.write("COMPREHENSIVE DEXSCREENER TEST\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            # STRATEGY 1: Search dengan berbagai query populer
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 1: Search dengan query populer\n")
            f.write("=" * 80 + "\n\n")
            
            queries = ['pepe', 'doge', 'shib', 'meme', 'ai', 'trump']
            
            for query in queries:
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': query}
                
                try:
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get('pairs', [])
                            
                            # Filter untuk base dan solana
                            base_pairs = [p for p in pairs if p.get('chainId', '').lower() == 'base']
                            solana_pairs = [p for p in pairs if p.get('chainId', '').lower() == 'solana']
                            
                            f.write(f"Query '{query}':\n")
                            f.write(f"  BASE: {len(base_pairs)} pairs\n")
                            f.write(f"  SOLANA: {len(solana_pairs)} pairs\n")
                            
                            # Check for new pairs
                            cutoff = datetime.now() - timedelta(hours=24)
                            
                            for chain_name, chain_pairs in [('BASE', base_pairs), ('SOLANA', solana_pairs)]:
                                new_count = 0
                                for p in chain_pairs:
                                    created_at = p.get('pairCreatedAt')
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            if created_time > cutoff:
                                                new_count += 1
                                        except:
                                            pass
                                
                                if new_count > 0:
                                    f.write(f"  {chain_name} new (<24h): {new_count}\n")
                            
                            f.write("\n")
                            
                except Exception as e:
                    f.write(f"Error with query '{query}': {e}\n\n")
            
            # STRATEGY 2: Get pairs by specific DEX
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 2: Get pairs by DEX\n")
            f.write("=" * 80 + "\n\n")
            
            dexes = {
                'base': ['uniswap', 'aerodrome', 'baseswap'],
                'solana': ['raydium', 'orca', 'jupiter']
            }
            
            for chain, dex_list in dexes.items():
                f.write(f"\n{chain.upper()}:\n")
                for dex in dex_list:
                    url = "https://api.dexscreener.com/latest/dex/search"
                    params = {'q': dex}
                    
                    try:
                        async with session.get(url, params=params, timeout=10) as response:
                            if response.status == 200:
                                data = await response.json()
                                pairs = data.get('pairs', [])
                                
                                # Filter by chain and DEX
                                chain_pairs = [p for p in pairs 
                                             if p.get('chainId', '').lower() == chain 
                                             and dex.lower() in p.get('dexId', '').lower()]
                                
                                f.write(f"  {dex}: {len(chain_pairs)} pairs\n")
                                
                                # Check for new
                                cutoff = datetime.now() - timedelta(hours=24)
                                new_count = 0
                                for p in chain_pairs:
                                    created_at = p.get('pairCreatedAt')
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            if created_time > cutoff:
                                                new_count += 1
                                        except:
                                            pass
                                
                                if new_count > 0:
                                    f.write(f"    New (<24h): {new_count}\n")
                                    
                    except Exception as e:
                        f.write(f"  Error with {dex}: {e}\n")
            
            # STRATEGY 3: Broader search - just get LOTS of pairs
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 3: Broad search untuk volume tinggi\n")
            f.write("=" * 80 + "\n\n")
            
            # Try searching for common tokens that appear in many pairs
            broad_queries = ['0x', 'token', 'coin']
            
            for query in broad_queries:
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': query}
                
                try:
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get('pairs', [])
                            
                            f.write(f"Query '{query}': {len(pairs)} total pairs\n")
                            
                            # Analyze by chain
                            by_chain = {}
                            for p in pairs:
                                chain = p.get('chainId', 'unknown')
                                by_chain[chain] = by_chain.get(chain, 0) + 1
                            
                            f.write("  By chain:\n")
                            for chain, count in sorted(by_chain.items(), key=lambda x: x[1], reverse=True)[:10]:
                                f.write(f"    {chain}: {count}\n")
                            
                            f.write("\n")
                            
                except Exception as e:
                    f.write(f"Error: {e}\n\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("ANALYSIS COMPLETE\n")
        f.write("=" * 80 + "\n")
        f.write("\nKESIMPULAN:\n")
        f.write("DexScreener API /search endpoint memiliki keterbatasan:\n")
        f.write("1. Tidak ada endpoint khusus untuk 'new pairs' atau 'trending'\n")
        f.write("2. Search query sangat terbatas (max 30 results)\n")
        f.write("3. Hasil didominasi oleh pairs dengan volume tinggi (established)\n")
        f.write("4. Koin baru dengan volume rendah tidak muncul di hasil search\n\n")
        f.write("REKOMENDASI:\n")
        f.write("- Gunakan multiple search queries dengan keyword populer\n")
        f.write("- Scan lebih sering (setiap 10-15 detik)\n")
        f.write("- Fokus pada DEX-specific queries\n")
        f.write("- Pertimbangkan menggunakan DexScreener Pro API (paid)\n")
    
    print("Test complete! Check comprehensive_test.txt")

if __name__ == "__main__":
    asyncio.run(test_comprehensive())
