# FTDC Format Specification

## Overview

FTDC (Full Time Diagnostic Data Capture) is MongoDB's internal diagnostic data collection facility. It encodes time-series metrics data in a highly space-efficient format that allows MongoDB to record diagnostic information every second and store weeks of data with only a few hundred megabytes of storage.

## Key Concepts

### Space Efficiency
FTDC achieves its space efficiency through several compression techniques:
1. **Delta encoding** - Stores differences between consecutive samples rather than absolute values
2. **Run-Length Encoding (RLE)** - Compresses sequences of zeros
3. **VarInt encoding** - Variable-length integer encoding for small numbers
4. **ZLIB compression** - Final compression layer on top of the above

### Schema Assumption
FTDC assumes that non-numeric data (strings, field names, document structure) remains constant across all samples in a series. It only stores numeric values, using a reference document to define the schema.

## File Format

An FTDC file is a sequence of BSON documents, each representing either metadata or a compressed metric chunk.

### Document Types

Each BSON document in an FTDC file has the following structure:

```
{
  "_id": Date_t,      // Timestamp
  "type": int32,      // Document type (see below)
  "doc": {...}        // (for metadata) or "data": BinData(...) (for metrics)
}
```

#### Type Field Values

| Type | Name | Description |
|------|------|-------------|
| 0 | kMetadata | One-time metadata about the process/machine |
| 1 | kMetricChunk | Compressed time-series metrics data |
| 2 | kPeriodicMetadata | Periodic metadata with delta document |

### Type 0: Metadata Document

Metadata documents contain static information about the MongoDB process, system configuration, etc.

```
{
  "_id": Date_t,
  "type": 0,
  "doc": {
    // Static system/process information
    // e.g., ulimits, system parameters, build info
  }
}
```

### Type 1: Metric Chunk Document

This is the core of FTDC - a compressed chunk of time-series metrics.

```
{
  "_id": Date_t,
  "type": 1,
  "data": BinData(...)  // Compressed metric chunk
}
```

The binary data field contains a compressed metric chunk with the following structure.

## Compressed Metric Chunk Format

The compressed metric chunk stored in the "data" field has the following structure:

### Overall Structure

```
[4 bytes: uncompressed size (uint32 LE)]
[variable: ZLIB compressed data]
```

### Uncompressed Data Structure

After decompressing the ZLIB data, you get:

```
[variable: Reference BSON document]
[4 bytes: metrics count (uint32 LE)]
[4 bytes: deltas count (uint32 LE)]
[variable: Delta-encoded metrics array]
```

### Components

#### 1. Reference Document
A complete BSON document that defines the schema and contains the first sample's values. All subsequent samples are deltas from previous values.

#### 2. Metrics Count
Number of numeric metrics extracted from the reference document. Metrics are extracted via depth-first traversal of the BSON document.

#### 3. Deltas Count
Number of delta samples following the reference document. The total number of samples in the chunk is `deltas_count + 1` (the +1 is the reference document itself).

#### 4. Delta-encoded Metrics Array

The metrics array contains delta values for each metric across all samples, organized as:

```
For each metric M (0 to metrics_count-1):
  For each sample S (0 to deltas_count-1):
    delta[M][S] = current_value[M][S] - previous_value[M][S]
```

The deltas are stored in row-major order: `delta[metric * deltas_count + sample]`

##### Delta Encoding

Deltas are encoded using a combination of:

1. **VarInt encoding** - Variable-length unsigned integer encoding where smaller numbers use fewer bytes
2. **Run-Length Encoding (RLE) for zeros** - Consecutive zeros are encoded as pairs:
   - First VarInt: 0 (indicates start of RLE)
   - Second VarInt: count - 1 (number of additional zeros)

##### Example Delta Encoding

```
Input deltas: [5, 0, 0, 0, 10, 3]

Encoded as VarInts:
[VarInt(5), VarInt(0), VarInt(2), VarInt(10), VarInt(3)]
            ^------RLE------^
            (3 zeros = 0 followed by count-1=2)
```

## Metric Extraction

MongoDB extracts metrics from BSON documents via depth-first traversal. Only numeric and numeric-like types are considered metrics:

### Supported Metric Types

| BSON Type | Encoding | Notes |
|-----------|----------|-------|
| Double | int64 | Converted via `int64(Float64bits(value))` |
| Int32 | int64 | Cast to int64 |
| Int64 | int64 | Direct |
| Boolean | int64 | true=1, false=0 |
| Date | int64 | Milliseconds since epoch |
| Timestamp | 2 x int64 | Two values: timestamp + increment |

### Metric Path

For nested documents, metrics preserve their hierarchical path:
- Top-level field: `"fieldName"`
- Nested field: `"parent.child.fieldName"`
- Array elements are flattened into the metric stream

### Schema Validation

When adding a new sample, FTDC validates that it has the same schema as the reference document:
1. Same number of fields
2. Same field names in same order (depth-first)
3. Same types (with Double/Int32/Int64 considered equivalent)

If schema validation fails, the current chunk is flushed and a new chunk starts with the new document as the reference.

## Decompression Algorithm

To decompress an FTDC metric chunk:

1. **Read the chunk header:**
   - Extract _id (timestamp)
   - Verify type == 1
   - Extract binary data field

2. **Decompress the outer layer:**
   - Read first 4 bytes as uncompressed size (uint32 LE)
   - ZLIB decompress remaining bytes

3. **Parse uncompressed data:**
   - Read reference BSON document
   - Read metrics_count (uint32 LE)
   - Read deltas_count (uint32 LE)

4. **Decode delta array:**
   ```python
   metrics = []  # metrics_count x (deltas_count + 1) array

   for metric_idx in range(metrics_count):
       values = [reference_doc_metrics[metric_idx]]  # Start with reference

       sample_idx = 0
       while sample_idx < deltas_count:
           delta = read_varint()

           if delta == 0:
               # RLE: next varint is zero count
               zero_count = read_varint() + 1
               for _ in range(zero_count):
                   values.append(values[-1])  # Previous value + 0 delta
               sample_idx += zero_count
           else:
               # Regular delta
               values.append(values[-1] + delta)
               sample_idx += 1

       metrics.append(values)
   ```

5. **Reconstruct documents:**
   - For each sample (0 to deltas_count):
     - Clone reference document structure
     - Replace metric values with values from metrics array
     - Restore original types (e.g., convert int64 back to double)

## VarInt Encoding

FTDC uses unsigned VarInt encoding (same as Protocol Buffers):

- Each byte has 7 bits of data + 1 continuation bit
- If high bit is 1, more bytes follow
- If high bit is 0, this is the last byte
- Bytes are in little-endian order

Example:
```
Value 300 (0x12C):
  Binary: 10 0101100
  VarInt: [0xAC, 0x02]
          10101100  00000010
          ^------^  ^
          7 bits    7 bits (high bit=0, last byte)
```

## Configuration Parameters

From MongoDB source code (`FTDCConfig`):

- **maxSamplesPerArchiveMetricChunk**: Maximum samples per chunk (default: 300)
- **maxFileSizeBytes**: Maximum FTDC file size before rotation
- **period**: Collection interval (default: 1 second)

## File Naming Convention

FTDC files follow this naming pattern:
```
metrics.YYYY-MM-DDTHH-MM-SSZ-NNNNN
```

Special file:
```
metrics.interim
```
The interim file contains the most recent, incomplete chunk that hasn't been flushed to a regular metrics file yet.

## Example: Reading an FTDC File

### Hex Dump Analysis

From the sample FTDC file:
```
00000000  6d 55 00 00 09 5f 69 64  00 0b 1f 37 7e 9a 01 00  |mU..._id...7~...|
00000010  00 10 74 79 70 65 00 00  00 00 00 03 64 6f 63 00  |..type......doc.|
```

Breaking this down:
- `6d 55 00 00`: BSON document size = 21869 bytes (little-endian)
- `09`: BSON type = Date
- `5f 69 64 00`: Field name = "_id" (null-terminated)
- `0b 1f 37 7e 9a 01 00 00`: Date value
- `10`: BSON type = int32
- `74 79 70 65 00`: Field name = "type" (null-terminated)
- `00 00 00 00`: Type value = 0 (kMetadata)
- `03`: BSON type = embedded document
- `64 6f 63 00`: Field name = "doc" (null-terminated)

This is a metadata document (type=0) containing system information.

## Implementation Notes

### Float Encoding
Doubles are encoded by reinterpreting the 64-bit IEEE 754 representation as a signed int64:
```c
int64_t encoded = *(int64_t*)&doubleValue;  // Or use bit_cast
```

Decoding reverses this:
```c
double decoded = *(double*)&encodedInt64;
```

### Signed Deltas with Unsigned VarInt
Delta values can be negative (when metrics decrease). These are stored as unsigned VarInts by reinterpreting the signed int64 as uint64:
```c
uint64_t encoded = *(uint64_t*)&signedDelta;
```

When decoding, interpret back as signed:
```c
int64_t delta = *(int64_t*)&unsignedVarInt;
```

## Performance Characteristics

### Compression Ratio
Typical compression ratios for MongoDB server metrics:
- Uncompressed: ~1KB per sample
- FTDC compressed: ~10-50 bytes per sample
- Compression ratio: 20-100x

### Write Performance
- Single-threaded collector
- Minimal overhead (~1ms per sample collection)
- Batched ZLIB compression on chunk completion

### Read Performance
- Sequential scan of BSON documents
- Random access requires decompressing entire chunks
- Efficient for time-range queries (skip irrelevant chunks)

## Tools and Libraries

### Official MongoDB FTDC Library (Go)
- Repository: https://github.com/mongodb/ftdc
- Features: Full parsing and generation support
- API: Iterator-based chunk and document access

### MongoDB Server (C++)
- Location: `src/mongo/db/ftdc/`
- Includes: Compressor, decompressor, file writer, collectors

### Community Tools
- Python implementations (various)
- Rust parser: https://github.com/maoertel/mongodb-ftdc

## References

- MongoDB FTDC Go Library: https://github.com/mongodb/ftdc
- MongoDB Server Source: `src/mongo/db/ftdc/` directory
- Protocol Buffers VarInt: https://developers.google.com/protocol-buffers/docs/encoding

## Appendix: Complete Chunk Example

```
Metric Chunk Binary Layout:
┌─────────────────────────────────────┐
│ BSON Document Header                │
│ {                                   │
│   "_id": Date_t,                   │
│   "type": 1,                       │
│   "data": BinData(...)             │
│ }                                   │
└──────────────┬──────────────────────┘
               │
               │ BinData field contains:
               ▼
┌─────────────────────────────────────┐
│ [4 bytes] Uncompressed Size        │
├─────────────────────────────────────┤
│ [variable] ZLIB Compressed Data    │
│                                     │
│   After decompression:              │
│   ┌─────────────────────────────┐  │
│   │ Reference BSON Document     │  │
│   ├─────────────────────────────┤  │
│   │ [4 bytes] Metrics Count     │  │
│   ├─────────────────────────────┤  │
│   │ [4 bytes] Deltas Count      │  │
│   ├─────────────────────────────┤  │
│   │ Delta Array (VarInt RLE)    │  │
│   │   For each metric:          │  │
│   │     For each sample:        │  │
│   │       VarInt(delta) or      │  │
│   │       VarInt(0) + VarInt(N) │  │
│   └─────────────────────────────┘  │
└─────────────────────────────────────┘
```
