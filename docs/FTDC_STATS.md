# FTDC File Statistics

Analysis of real MongoDB FTDC file structure and compression characteristics.

**Source:** MongoDB Atlas M10 cluster running MongoDB 8.0.16
**File:** `metrics.2025-11-13T17-15-32Z-00000`
**Total Size:** 489,893 bytes (478 KB)
**Date Analyzed:** 2025-11-14

---

## File Structure Overview

**Total Documents:** 16
- Metadata documents: 3 (43,036 bytes)
- Data chunks: 13 (446,857 bytes)

**Total Samples:** 440 one-second metric readings
**Time Span:** ~7 minutes 20 seconds
**Collection Frequency:** 1 sample per second

---

## Reference Documents (Schema Records)

The reference document defines the metric schema for each chunk - containing all metric names, nested BSON structure, and one sample value per metric.

### Size Statistics

| Metric | Value |
|--------|-------|
| Minimum | 116,083 bytes |
| Maximum | 225,544 bytes |
| Average | 193,385 bytes |
| Total (13 chunks) | 2,514,005 bytes (2.4 MB) |

### Schema Variations

| Chunk | Ref Doc Size | Metrics | Notable Changes |
|-------|-------------|---------|-----------------|
| 0 | 116,140 bytes | 3,462 | Initial schema |
| 1 | 116,083 bytes | 3,459 | Lost /run/user/0 mount (-3) |
| 2 | 116,169 bytes | 3,463 | Added featureCompatibilityVersion (+4) |
| 3 | 136,188 bytes | 3,913 | Added WiredTiger oplog stats (+450) |
| 4 | 225,396 bytes | 5,574 | Added full WiredTiger collection stats (+1,661) |
| 5-12 | 193-225 KB | 5,574-5,582 | Minor variations (election metrics, mounts) |

**Key Insight:** Reference document size correlates directly with metric count. WiredTiger storage engine statistics add significant overhead (~89 KB for detailed index stats).

---

## Compressed Delta Data (Binary Only)

The actual metric values are stored as compressed delta-encoded integers.

### Size Statistics

| Metric | Value |
|--------|-------|
| Minimum | 23,332 bytes (1 sample) |
| Maximum | 70,488 bytes (300 samples) |
| Average | 34,330 bytes |
| Total (13 chunks) | 446,298 bytes (436 KB) |

### Compression Performance

| Metric | Value |
|--------|-------|
| Minimum Ratio | 4.4x |
| Maximum Ratio | 7.2x |
| Average Ratio | **6.0x** |

**Compression Algorithm:** ZLIB + Delta encoding + RLE (Run-Length Encoding) for zeros

---

## Samples per Chunk

FTDC creates a new chunk when the metric schema changes or a time/sample threshold is reached.

### Distribution

| Metric | Value |
|--------|-------|
| Minimum | 1 sample |
| Maximum | 300 samples |
| Average | 32 samples |
| Median | ~11 samples |

### Sample Counts by Chunk

| Chunk | Samples | Duration | Reason for New Chunk |
|-------|---------|----------|---------------------|
| 0 | 10 | 10 sec | Initial |
| 1 | 27 | 27 sec | Mount removed |
| 2 | 1 | 1 sec | Schema change |
| 3 | 11 | 11 sec | WiredTiger stats added |
| 4 | 2 | 2 sec | Collection stats added |
| 5 | 1 | 1 sec | Election metrics added |
| 6 | 2 | 2 sec | Mount reappeared |
| 7 | 9 | 9 sec | Election role change |
| 8 | 2 | 2 sec | Mount disappeared |
| 9 | 9 | 9 sec | Lock counter added |
| 10 | 9 | 9 sec | Mount reappeared |
| 11 | 300 | 5 min | Stable schema |
| 12 | 67 | 1m 7s | Mount disappeared |

**Observation:** Chunk 11 has 300 samples (5 minutes) with no schema changes, suggesting FTDC may have a ~300 sample or ~5 minute chunk size limit when schema is stable.

---

## Storage Efficiency

### Bytes per Sample (Compressed)

| Samples | Bytes/Sample | Efficiency |
|---------|--------------|------------|
| 1 | 23,332 | Poor (reference doc dominates) |
| 10 | 2,626 | Moderate |
| 27 | 1,094 | Good |
| 300 | ~235 | Excellent |

**Key Finding:** Efficiency improves dramatically with more samples per chunk as the reference document overhead is amortized.

### Overhead Analysis

| Component | Bytes | Percentage |
|-----------|-------|------------|
| Reference docs | 2,514,005 | 93.8% |
| Delta data (compressed) | 446,298 | 16.6% |
| Total uncompressed | 2,681,072 | - |

**Storage Breakdown:**
- Compressed file size: 490 KB
- Uncompressed data: 2.6 MB
- Overall compression: **5.5x**
- Reference doc overhead: **93.8%** of uncompressed size

---

## Schema Change Events

The file contains **12 schema changes** resulting in **13 chunks**.

### Major Changes

1. **Chunk 0→1:** Temporary mount removed (-3 metrics)
2. **Chunk 1→2:** Feature compatibility version added (+4 metrics)
3. **Chunk 2→3:** WiredTiger oplog.rs storage stats added (+450 metrics)
4. **Chunk 3→4:** WiredTiger collection stats for config.transactions and config.image_collection (+1,661 metrics)
5. **Chunk 6→7:** Election role change from candidate to participant (replica set election detected)
6. **Chunks 5-12:** Ephemeral mount `/run/user/0` appearing/disappearing (±3 metrics)

### Implications

- **Schema instability:** Frequent schema changes prevent FTDC from achieving optimal compression
- **Storage cost:** Each schema change adds ~193 KB reference document overhead
- **WiredTiger impact:** Detailed storage stats add ~89 KB to reference document
- **Dynamic metrics:** Temporary mounts and election states cause schema churn

---

## Metric Count Evolution

| File Segment | Columns (Metrics) | Change from Previous |
|--------------|-------------------|---------------------|
| CSV 0 | 3,461 | - |
| CSV 1 | 3,458 | -3 (mount) |
| CSV 2 | 3,462 | +4 (fcv) |
| CSV 3 | 3,912 | +450 (WiredTiger oplog) |
| CSV 4 | 5,573 | +1,661 (WiredTiger collections) |
| CSV 5-11 | 5,574-5,582 | ±1-3 (minor variations) |

**Peak Metrics:** 5,582 simultaneous metrics being tracked

---

## Performance Characteristics

### Compression Efficiency by Chunk

| Chunk | Ref Doc (KB) | Compressed (KB) | Uncompressed (KB) | Ratio | Samples |
|-------|-------------|-----------------|-------------------|-------|---------|
| 0 | 113 | 26 | 118 | 4.6x | 10 |
| 1 | 113 | 29 | 126 | 4.4x | 27 |
| 3 | 133 | 30 | 138 | 4.6x | 11 |
| 4 | 220 | 32 | 221 | 7.1x | 2 |
| 11 | 225 | 70 | 338 | **7.2x** | 300 |

**Best Compression:** Chunk 11 (7.2x) with 300 samples - stable schema allows FTDC to excel
**Worst Compression:** Chunks with 1-2 samples where reference doc overhead dominates

---

## Key Insights

### 1. Reference Document Dominates Storage
- Reference docs are **93.8%** of uncompressed data
- Delta data is only **6.2%** of uncompressed size
- FTDC is optimized for many samples per schema, not frequent schema changes

### 2. Schema Stability is Critical
- Stable schema (Chunk 11): 300 samples, 7.2x compression, 235 bytes/sample
- Unstable schema (Chunks 2-10): 1-11 samples, poor amortization
- Each schema change adds ~193 KB overhead

### 3. WiredTiger Stats Add Significant Overhead
- Basic metrics: ~116 KB reference doc (3,460 metrics)
- + Oplog stats: ~136 KB reference doc (3,913 metrics)
- + Collection stats: ~225 KB reference doc (5,574 metrics)
- WiredTiger detailed stats nearly double reference doc size

### 4. Actual Data is Highly Compressible
- Compressed deltas: 23-70 KB for 1-300 samples
- 6x average compression on delta data
- Varint encoding + RLE zeros is very effective
- Most metrics don't change much second-to-second

### 5. Collection Frequency
- MongoDB collects FTDC every **1 second**
- Maximum observed chunk: **300 samples** (5 minutes)
- Schema changes force new chunks regardless of sample count
- Ephemeral resources (mounts, elections) cause frequent schema changes

---

## Recommendations

### For MongoDB Users

1. **Minimize schema churn** - Stable metrics lead to better compression
2. **Disable unnecessary stats** - WiredTiger detailed stats add overhead without always adding value
3. **Expect ~500 KB per 7-10 minutes** of FTDC with typical schema changes
4. **Plan for 5-6x compression** when extracting to CSV/JSON

### For FTDC Tool Developers

1. **Handle schema changes gracefully** - 12+ schema changes in 7 minutes is normal
2. **Expect 3,400-5,600 metrics** depending on configuration
3. **Reference doc is 115-225 KB** - don't load entire doc into memory repeatedly
4. **Delta data is tiny** - average 34 KB compressed per chunk
5. **Compression ratios vary widely** - 4.4x to 7.2x depending on sample count

---

## File Analyzed

```
Path: mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1725Z/
      atlas-14lvdy-shard-00-00.25orp.mongodb.net/27017/diagnostic.data/
      metrics.2025-11-13T17-15-32Z-00000

Cluster: MongoDB Atlas M10
Version: 8.0.16
Platform: Unknown (Linux assumed)
Topology: Replica Set (3 nodes)
Role: Shard member (shard-00-00)
```

---

## Additional Notes

- This file exhibits high schema instability (12 changes in 7 minutes)
- Production files with stable workloads likely have fewer schema changes
- Larger FTDC files (hours/days) would show better overall compression
- The `/run/user/0` mount flapping suggests user session activity on the host
- Election metrics indicate this node participated in a replica set election during collection

---

**Generated:** 2025-11-14
**Tool:** FTDC Tools Python Parser v0.1.0
**Analysis Duration:** ~2 seconds for 490 KB file
