# Known Limitations

## Current Issues

### 1. Limited Test Coverage (CRITICAL)

**Status**: 🔴 CRITICAL - Insufficient for production use

**Description**: The FTDC parser has only been tested with a single MongoDB Atlas FTDC file. The MongoDB version and platform are unknown.

**Missing Coverage**:
- ❌ MongoDB 7.0 testing
- ❌ MongoDB 8.0 testing
- ❌ MongoDB 8.2 testing
- ❌ Platform verification (Linux x86_64, Linux ARM64, macOS, Windows)
- ❌ Deployment topology testing (standalone, replica set, sharded)
- ❌ Enterprise edition features

**Impact**: CRITICAL - Cannot guarantee parser works across all supported MongoDB versions and platforms

**Requirements for Production**:
- Minimum: MongoDB 7.0, 8.0 on Linux x86_64 and ARM64
- Recommended: Complete version × platform × topology matrix

**See**: [docs/TESTING_COVERAGE.md](./TESTING_COVERAGE.md) for detailed testing plan

### 2. Python Parser: Double Precision Handling (RESOLVED)

**Status**: ✅ RESOLVED - Fixed to match mongodb/ftdc Go implementation

**Previous Error**: `struct.error: required argument is not an integer`

**Location**: `ftdc/parser/metrics.py` - `restore_float()` function

**Description**: The Python parser was failing when reconstructing double values from FTDC delta streams in edge cases where int64 overflow occurred during delta arithmetic.

**Root Cause**: MongoDB stores doubles as int64 bit patterns in the delta stream. Delta arithmetic could cause values to overflow int64 range, causing `struct.pack('<q', value)` to fail.

**Fix Applied**: Updated `restore_float()` to match the mongodb/ftdc Go implementation:
- Cast to uint64 before bit reinterpretation (handles overflow/underflow)
- Made function idempotent (handles float inputs gracefully)
- Uses `struct.pack('<Q', unsigned_value)` for unsigned interpretation

**Go Reference**: `func restoreFloat(in int64) float64 { return math.Float64frombits(uint64(in)) }`

**Verification**: All 122 existing tests pass with the new implementation

### 2. Interim File Parsing (NEEDS INVESTIGATION)

**Status**: ⚠️ KNOWN ISSUE - Requires further investigation

**Description**: The `metrics.interim` files (incomplete/in-progress FTDC files) exhibit parsing issues. These files are created by MongoDB while actively collecting metrics and may not follow the standard FTDC format completely.

**Files Affected**:
- `metrics.interim` (found in MongoDB's diagnostic.data directory)
- These are temporary files that become `metrics.YYYY-MM-DDTHH-MM-SSZ-00000` when rotated

**Workaround**: Use completed FTDC files (with timestamp naming) instead of interim files for reliable parsing.

**TODO**: Investigate the specific differences in interim file format and determine if parsing can be made robust for these files.

---

## Resolved Issues

### Previous Issue: Metric Extraction Accuracy (RESOLVED)

**Status**: ✓ RESOLVED - Now achieving 100% metric extraction accuracy

**Root Causes Identified**:
1. **Array Indexing** (FIXED): Arrays in BSON documents create indexed paths like `array.0.field`, `array.1.field`
2. **Timestamp Fields** (FIXED): BSON Timestamp creates TWO metrics with suffixes: base name (seconds) and `.inc` (increment)
3. **MongoDB /boot/efi Quirk** (WORKAROUND ADDED): MongoDB FTDC duplicates `systemMetrics.mounts./boot/efi.{capacity,available,free}` metrics, creating 6 total metrics instead of 3. This appears to be a quirk in MongoDB's FTDC implementation.
4. **RLE Zero Counter** (FIXED): The RLE (Run-Length Encoding) zero counter must PERSIST across metrics, not reset for each metric. Large RLE counts (e.g., 8000+) can span multiple metrics.

**Fixes Applied**:
- `ftdc/parser/metrics.py`: Fixed array indexing to use `indexed_path = current_path + [str(idx)]`
- `ftdc/parser/metrics.py`: Fixed Timestamp to create metrics with correct naming: `key` and `{key}.inc`
- `ftdc/parser/metrics.py`: Added workaround to duplicate `/boot/efi` metrics to match MongoDB's behavior
  - **Note**: This is a workaround for a bug in the evergreen-ci/birch BSON library
  - See [docs/BIRCH_LIBRARY_BUG.md](docs/BIRCH_LIBRARY_BUG.md) for detailed analysis
- `ftdc/parser/chunk.py`: Moved `nzeroes` counter outside metric loop to persist across all metrics

**Verification**:
- ✓ All 6 FTDC files (3 replica set nodes × 2 files each) now parse successfully
- ✓ 100% metric extraction accuracy: header count matches extracted count
- ✓ Delta decoding works correctly with proper RLE handling
- ✓ Sample data:
  - Node 0: 5580 metrics, 121 samples
  - Node 1: 5598 metrics, 121 samples
  - Node 2: 5578 metrics, 121 samples
