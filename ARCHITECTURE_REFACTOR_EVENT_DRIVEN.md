# Architecture Refactor: True Global Event-Driven Mode

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    %% Global Block Service - The Single Source of Truth
    GBS[Global Block Service] -->|Polls eth_blockNumber| RPC[RPC Node]
    GBS -->|1. Creates Snapshot| SNAP[Shared BlockSnapshot]
    
    %% Event Bus Fan-out
    SNAP -->|2. Publishes| BUS[Global Event Bus]
    
    %% Consumers (Passive, No Polling)
    BUS -->|3. On Block Event| BASE[Base Scanner]
    BUS -->|3. On Block Event| ETH[Ethereum Scanner]
    BUS -->|3. On Block Event| SOL[Solana Scanner]
    BUS -->|3. On Block Event| ACT[Activity Scanner]
    BUS -->|3. On Block Event| HEAT[Heat Engine]

    %% Data Flow
    subgraph "BlockSnapshot Data"
        BN[Block Number]
        TS[Timestamp]
        CID[Chain ID (Hardcoded)]
    end
    
    SNAP --- BN
    SNAP --- TS
    SNAP --- CID
    
    %% Eliminated Calls
    style RPC fill:#f9f,stroke:#333
    style GBS fill:#ccf,stroke:#333
    style SNAP fill:#cfc,stroke:#333
```

## 2. Refactored Service Responsibilities

### **A. Global Block Service (`modules.global_block_events`)**
- **Sole Responsibility**: Owns the "Heartbeat" of the chain.
- **Strict Polling**: Manages the `eth_blockNumber` polling interval (Lazy for idle, Strict for Mainnet).
- **Snapshot Creation**: Fetches `timestamp` ONCE per block. Fills `BlockSnapshot`.
- **Dedup**: Uses LRU cache to ensure the same block is never broadcast twice.
- **Reliability**: Handles RPC errors and backoff centrally.

### **B. Shared `BlockSnapshot` Object**
- **Immutable State**: `block_number`, `timestamp`, `chain_id` (hardcoded).
- **Universal Currency**: All downstream modules accept ONLY this object. passing raw `int` is deprecated.

### **C. Scanners (`EVMAdapter`, `BaseScanner`, etc.)**
- **Passive Mode**: logic loops (`while True`) are REMOVED.
- **Reactive**: `scan_new_pairs_async(snapshot)` is triggered by the Event Bus.
- **RPC Usage**:
  - `eth_blockNumber`: **ELIMINATED** (0 calls).
  - `eth_getBlockByNumber` (for timestamp): **ELIMINATED** (0 calls).
  - `eth_getLogs`: **OPTIMIZED** (Only calls if snapshot is new).

### **D. Activity Scanner (Delta-Event Mode)**
- **Trigger**: Runs ONLY when `BlockSnapshot` arrives.
- **Range**: `from_block = snapshot.block_number`, `to_block = snapshot.block_number`.
- **Logic**: No persistent loop. No independence.

## 3. Eliminated RPC Calls & CU Reduction Estimates

| Component | RPC Method | Old Frequency | New Frequency | Elimination Status | CU Saved (Est.) |
|-----------|------------|---------------|---------------|--------------------|-----------------|
| **BaseScanner** | `eth_blockNumber` | 1/30s | 0 | **ELIMINATED** | ~2,880/day |
| **BaseScanner** | `eth_getBlock` | 1/Block | 0 (Shared) | **ELIMINATED** | ~500/day |
| **EthScanner** | `eth_blockNumber` | 1/30s | 0 | **ELIMINATED** | ~2,880/day |
| **EthScanner** | `eth_getBlock` | 1/Block | 0 (Shared) | **ELIMINATED** | ~5,000/day |
| **ActivityScanner** | `eth_blockNumber` | 1/30s | 0 | **ELIMINATED** | ~2,880/day |
| **HeatEngine** | `eth_blockNumber` | 1/60s | 0 | **ELIMINATED** | ~1,440/day |
| **GlobalService** | `eth_blockNumber` | - | 1/6s-12s | **ADDED** | (-7,200/day) |

### **Total Savings Estimate**
- **Old Architecture**: Every module polled independently.
  - Base: ~3,500 CU/day wasted on checks.
  - Eth: ~8,000 CU/day wasted (calls are more expensive on mainnet usually, or similar).
  - Total Overhead: ~15,000+ CU/day just for "Are we there yet?".
- **New Architecture**:
  - Global Service: ~7,200-14,000 calls (depending on interval).
  - **Net Reduction**: **~40-60% Reduction in Idle/Overhead Calls.**
  - **Duplicate `getBlock` (Timestamp)**: Previously every scanner fetched the block to get the timestamp. Now fetched ONCE. **100% reduction in duplicate payload calls.**

## 4. Implementation Details (Pseudocode)

### Global Service Loop
```python
async def _loop(self):
    while self.is_running:
        # SINGLE RPC CALL
        current = await w3.eth.get_block_number()
        
        if current > self.latest_block:
            # SINGLE TIMESTAMP FETCH
            block_data = await w3.eth.get_block(current)
            
            snapshot = BlockSnapshot(
                block_number=current,
                timestamp=block_data['timestamp'],
                chain_id=config.CHAIN_ID # Hardcoded
            )
            
            # FAN OUT
            await EventBus.publish("NEW_BLOCK", snapshot)
            self.latest_block = current
            
        await asyncio.sleep(self.interval)
```

### Scanner Consumption
```python
# Adapter
async def scan_new_pairs_async(self, snapshot: BlockSnapshot):
    # NO RPC CALLS HERE
    current_block = snapshot.block_number
    timestamp = snapshot.timestamp 
    
    # Delta Scan Logic...
    logs = await self.fetch_logs(current_block)
    # ...
```

## 5. Next Steps
1.  Integrate `GlobalBlockService` into `main.py`.
2.  Update `multi_scanner.chain_loop` to subscribe to `GlobalBlockService`.
3.  Inject `inject_external_event` for DEXTools triggers.
