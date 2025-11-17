# Claude Code Session Guide

Quick reference for AI assistants working on the FTDC Tools project.

**Last Updated:** 2025-11-14
**Project Status:** ALPHA - Phase 1 complete, Phase 2 in progress
**Repository:** https://github.com/fsnow/ftdc-tools

---

## Project Overview

MongoDB FTDC (Full Time Diagnostic Data Capture) parsing and analysis tools.

**Mission:** Provide open-source tools for parsing, analyzing, and exporting MongoDB FTDC files to popular monitoring platforms.

**Current State:**
- ✅ Python parser complete (122/124 tests passing)
- ✅ Critical double precision bug fixed (2025-11-14)
- ✅ Go CLI basic extraction working
- 🔴 Limited test coverage (MongoDB 8.0.16 only)
- 🔴 Interim file parsing broken

---

## Local Resources

### MongoDB Repositories

When working on FTDC tools, these local repositories are available for reference:

```bash
# Official MongoDB FTDC Go library
/Users/frank.snow/github/mongodb/ftdc

# MongoDB server source code
/Users/frank.snow/github/mongodb/mongo
```

**Use cases:**
- Understanding FTDC format implementation
- Checking API signatures and behavior
- Investigating edge cases
- Comparing implementations (Go vs Python)

### Test Data

```bash
# Real MongoDB Atlas M10 (8.0.16) FTDC files
/Users/frank.snow/mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1725Z/

# Structure:
atlas-14lvdy-shard-00-0{0,1,2}.25orp.mongodb.net/
  27017/diagnostic.data/
    metrics.interim              # Broken - needs investigation
    metrics.2025-11-13T17-15-*   # Working FTDC files
```

**Test file details:**
- MongoDB version: 8.0.16
- Cluster: Atlas M10
- Topology: 3-node replica set
- Platform: Unknown (Linux assumed)
- Samples: ~440 per file (7-10 minutes)
- Metrics: 3,400-5,600 depending on schema

---

## Repository Structure

```
ftdc-tools/
├── python/                   # Python implementation
│   ├── ftdc/                # Parser library
│   │   ├── parser/          # Core parsing logic
│   │   │   ├── bson_parser.py   # Custom BSON parser (preserves duplicate keys)
│   │   │   ├── chunk.py         # Chunk decompression and delta decoding
│   │   │   ├── metrics.py       # Metric extraction (FIXED: restore_float bug)
│   │   │   ├── reader.py        # File reader and iteration
│   │   │   ├── types.py         # Data structures
│   │   │   └── varint.py        # VarInt encoding/decoding
│   │   ├── cli.py           # CLI tool (in progress)
│   │   ├── models.py        # Data models for Atlas API
│   │   └── service.py       # Atlas API client
│   ├── pyproject.toml       # Python package config
│   └── uv.lock             # Dependency lock file
│
├── go/                      # Go CLI wrapper
│   ├── cmd/ftdc-cli/       # CLI implementation
│   │   └── main.go         # Basic CSV extraction working
│   ├── bin/                # Compiled binaries (gitignored)
│   ├── go.mod              # Go module definition
│   └── README.md
│
├── tests/                   # Python tests (122/124 passing)
│   ├── test_chunk.py       # Chunk decompression tests
│   ├── test_metrics.py     # Metric extraction tests
│   ├── test_reader.py      # File reader tests
│   ├── test_varint.py      # VarInt tests
│   └── test_real_ftdc.py   # Integration tests (need FTDC files)
│
├── docs/                    # Documentation
│   ├── FTDC_FORMAT_SPECIFICATION.md  # Format details
│   ├── FTDC_STATS.md                 # Real file analysis (NEW)
│   ├── KNOWN_LIMITATIONS.md          # Current issues
│   ├── ROADMAP.md                    # Development plan
│   ├── TESTING_COVERAGE.md           # Test coverage plan
│   └── TIMEZONE_FIX.md               # Timezone handling notes
│
├── examples/                # Usage examples
├── README.md               # Main documentation
├── TODO.md                 # Task tracking
└── CLAUDE.md              # This file
```

---

## Recent Changes (2025-11-14)

### Fixed Critical Bug

**Issue:** Python parser failed with `struct.error: required argument is not an integer`

**Root Cause:** Delta arithmetic caused int64 overflow, making `struct.pack('<q', value)` fail

**Solution:** Updated `restore_float()` to match mongodb/ftdc Go implementation:
```python
# Cast to uint64 before bit reinterpretation (handles overflow)
unsigned_value = value & 0xFFFFFFFFFFFFFFFF
packed = struct.pack('<Q', unsigned_value)  # '<Q' = unsigned long long
return struct.unpack('<d', packed)[0]
```

**Reference:** `mongodb/ftdc/util.go:94`
```go
func restoreFloat(in int64) float64 { return math.Float64frombits(uint64(in)) }
```

**Verification:** All 122 tests pass

**Commits:**
- `ffd48bd` - Initial commit
- `bfded69` - Fix double precision bug

---

## Common Tasks

### Running Tests

```bash
cd python
uv run pytest -v                    # All tests
uv run pytest tests/test_chunk.py   # Specific test file
```

**Note:** 2 tests are skipped (need real FTDC files in specific location)

### Building Go CLI

```bash
cd go
go build -o bin/ftdc-cli ./cmd/ftdc-cli
```

### Extracting FTDC to CSV

```bash
# Single CSV (fails if schema changes)
./go/bin/ftdc-cli extract <ftdc-file> -o output.csv

# Multiple CSVs (handles schema changes)
./go/bin/ftdc-cli extract <ftdc-file> --dump-prefix=output
# Creates: output.0.csv, output.1.csv, etc.
```

### Using Python Parser

```python
from ftdc.parser.reader import FTDCReader

reader = FTDCReader("metrics.ftdc")

# Iterate over samples
for sample in reader.read_samples():
    timestamp = sample.timestamp
    metrics = sample.metrics  # dict of metric_name -> value
    print(f"{timestamp}: {len(metrics)} metrics")
```

---

## Current Priorities

### High Priority (Blocking Production)

1. **Expand Test Coverage** 🔴 CRITICAL
   - Need FTDC files from MongoDB 7.0, 8.0, 8.2
   - Test on Linux x86_64, ARM64, macOS
   - Test replica sets, sharded clusters
   - Currently only tested: MongoDB 8.0.16 Atlas M10

2. **Fix Interim File Parsing** 🔴 CRITICAL
   - `metrics.interim` files fail to parse
   - Investigation needed: incomplete chunks? different structure?
   - Test file available at: `mongodb-logfiles*/*/27017/diagnostic.data/metrics.interim`

3. **Complete Go CLI** 🟡 Medium Priority
   - JSON export
   - Verification command (compare against Python)
   - Time-range filtering
   - Metric filtering (regex patterns)

### Medium Priority

4. **Python CLI Tool**
   - Entry point: `ftdc` command
   - Commands: extract, stats, verify
   - Progress bars for large files

5. **Binary Verification**
   - Compare Python vs Go output
   - Define "exact mode" CSV format
   - Implement comparison tool

---

## Known Issues

### 1. Limited Test Coverage (CRITICAL)
- **Status:** Only tested with MongoDB 8.0.16 Atlas M10
- **Missing:** 7.0, 8.2, different platforms, topologies
- **Impact:** Cannot guarantee parser works universally
- **Priority:** Must fix before production use

### 2. Interim File Parsing (CRITICAL)
- **Status:** `metrics.interim` files fail to parse
- **Error:** Unknown - needs investigation
- **Workaround:** Use completed FTDC files (with timestamp names)
- **Priority:** Medium - interim files rotate to standard format

### 3. Schema Changes Cause Performance Issues
- **Status:** Design limitation
- **Impact:** Frequent schema changes reduce compression efficiency
- **Observed:** 12 schema changes in 7 minutes (Atlas M10)
- **Each change:** Adds ~193 KB reference document overhead
- **Mitigation:** FTDC is optimized for stable schemas

---

## Key Insights from Analysis

### FTDC Format Characteristics (MongoDB 8.0.16)

**File Structure:**
- Metadata docs: 1-3 per file (~43 KB total)
- Data chunks: Variable (13 in our test file)
- Samples: 1-300 per chunk (average 32)
- Collection frequency: 1 sample per second

**Compression:**
- Reference doc: 116-225 KB per chunk (schema definition)
- Compressed deltas: 23-70 KB per chunk (actual data)
- Compression ratio: 4.4x - 7.2x (average 6.0x)
- Efficiency: Better with more samples (300 samples = 7.2x, 1 sample = 4.4x)

**Schema Evolution:**
- Basic metrics: ~3,460 metrics, 116 KB reference doc
- + WiredTiger oplog stats: ~3,910 metrics, 136 KB
- + WiredTiger collection stats: ~5,570 metrics, 225 KB
- Schema changes force new chunks regardless of sample count

**Storage Overhead:**
- Reference docs: 93.8% of uncompressed data
- Delta data: 6.2% of uncompressed data
- FTDC is optimized for many samples per schema

### Python vs Go Comparison

**Python Parser:**
- Custom BSON parser (preserves duplicate keys)
- Handles all BSON types correctly
- Double precision now matches Go (as of 2025-11-14)
- 122/124 tests passing
- Performance: ~2 seconds for 490 KB file

**Go CLI (mongodb/ftdc wrapper):**
- Uses official MongoDB library
- Proven stable and correct
- CSV export working
- Schema change handling automatic
- JSON export not yet implemented

**Verification Status:**
- Metric names: 100% match
- Metric order: 100% match
- Metric counts: 100% match (3,462 extracted)
- Double values: Now match after bug fix

---

## Development Workflow

### Before Starting Work

1. **Check recent changes:**
   ```bash
   git log --oneline -10
   git status
   ```

2. **Review priorities:**
   ```bash
   cat TODO.md | head -100
   ```

3. **Check test status:**
   ```bash
   cd python && uv run pytest -v
   ```

### Making Changes

1. **Read relevant code first**
2. **Make focused changes**
3. **Test thoroughly:**
   ```bash
   cd python && uv run pytest
   ```

4. **Update documentation:**
   - README.md for user-facing changes
   - TODO.md for task completion
   - KNOWN_LIMITATIONS.md for new issues

5. **Commit with descriptive message:**
   ```bash
   git add .
   git commit -m "Description

   - Detailed change 1
   - Detailed change 2

   🤖 Generated with Claude Code

   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

### Important Conventions

- **Never commit binaries** (go/bin/* is gitignored)
- **Always run tests** before committing
- **Update TODO.md** when completing tasks
- **Document breaking changes** in KNOWN_LIMITATIONS.md
- **Use TodoWrite tool** for multi-step tasks

---

## Quick Reference

### File Paths

```bash
# Python parser entry point
python/ftdc/parser/reader.py

# Critical bug fix location
python/ftdc/parser/metrics.py:62-93  # restore_float()

# Go CLI entry point
go/cmd/ftdc-cli/main.go

# Test FTDC files
/Users/frank.snow/mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1725Z/

# MongoDB FTDC reference
/Users/frank.snow/github/mongodb/ftdc/
```

### Key Commands

```bash
# Python tests
cd python && uv run pytest -v

# Go build
cd go && go build -o bin/ftdc-cli ./cmd/ftdc-cli

# Extract CSV
./go/bin/ftdc-cli extract <file> --dump-prefix=output

# Git status
git log --oneline -5
git status
```

### Important Metrics

- Python tests: **122/124 passing**
- Verification: **100% metric match** with mongodb/ftdc
- Test coverage: **MongoDB 8.0.16 only** 🔴
- Compression: **6.0x average**
- Metrics tracked: **3,400-5,600** depending on schema

---

## Next Session Quick Start

1. **Check git status:** `git status`
2. **Review TODO.md:** High priority section
3. **Run tests:** `cd python && uv run pytest -v`
4. **Check for new FTDC files:** `ls -lh ~/mongodb-logfiles*`
5. **Review recent commits:** `git log --oneline -5`

---

## Common Pitfalls

### ❌ Don't

- Commit binaries (go/bin/*)
- Commit test FTDC files (*.ftdc)
- Commit generated CSV files (unless examples)
- Skip tests before committing
- Modify FTDC format (it's MongoDB's spec)

### ✅ Do

- Run tests frequently
- Update TODO.md when completing tasks
- Document new limitations
- Reference mongodb/ftdc for format questions
- Use local mongodb repos for investigation
- Test with real FTDC files
- Handle schema changes gracefully

---

## Troubleshooting

### Tests Failing

```bash
# Check Python environment
cd python && uv pip list

# Reinstall dependencies
cd python && uv pip install -e .

# Run specific failing test
cd python && uv run pytest tests/test_metrics.py -v -k test_name
```

### Go Build Issues

```bash
# Check Go version
go version  # Should be 1.21+

# Clean and rebuild
cd go && rm -rf bin/ && go build -o bin/ftdc-cli ./cmd/ftdc-cli
```

### FTDC Parse Errors

1. **Check MongoDB version** - May have format differences
2. **Try with Go CLI** - Canonical reference implementation
3. **Check for interim files** - Known to fail
4. **Examine file size** - Corrupted files may be truncated

---

## Resources

### Documentation
- [FTDC Format Spec](docs/FTDC_FORMAT_SPECIFICATION.md)
- [Stats Analysis](docs/FTDC_STATS.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [Roadmap](docs/ROADMAP.md)

### External Links
- [MongoDB FTDC Go Library](https://github.com/mongodb/ftdc)
- [MongoDB Server Source](https://github.com/mongodb/mongo)
- [FTDC in Server Code](https://github.com/mongodb/mongo/tree/master/src/mongo/db/ftdc)

### Test Data Location
```bash
/Users/frank.snow/mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1725Z/
```

---

**Remember:** This is ALPHA software. The main blocker for production use is comprehensive test coverage across MongoDB versions and platforms.

**Status as of 2025-11-14:** Python parser working correctly, Go CLI functional for basic extraction, critical bug fixed, ready for expanded testing.
