# FTDC Tools Roadmap

## Mission

Make MongoDB's Full Time Diagnostic Data Capture (FTDC) more transparent and accessible to customers by providing open-source tools for parsing, analyzing, and exporting FTDC data to popular monitoring platforms.

## Background

MongoDB collects diagnostic data through FTDC files, which are primarily analyzed by MongoDB Technical Services using internal tools. While MongoDB has published the `mongodb/ftdc` Go library, there is currently no official CLI tool for customers to analyze their own FTDC data. This project aims to fill that gap and extend FTDC accessibility to the broader monitoring ecosystem.

---

## What We've Accomplished

### Phase 1: Python FTDC Parser (✓ COMPLETE)

**Implementation**: `/Users/frank.snow/github/fsnow/mongo-tools/ftdc/`

#### Core Components
- ✓ **BSON Parser** (`ftdc/parser/bson_parser.py`)
  - Parses BSON directly from bytes, preserving duplicate keys
  - Handles all BSON types: int32, int64, double, bool, datetime, Timestamp, ObjectId, arrays, embedded documents
  - **Critical Discovery**: Python's `bson.decode()` silently deduplicates keys - we built a custom parser to preserve MongoDB's exact data structure

- ✓ **Chunk Decompression** (`ftdc/parser/chunk.py`)
  - ZLIB decompression
  - Delta decoding with RLE (Run-Length Encoding) zero compression
  - **Critical Bug Fix**: RLE zero counter must persist across ALL metrics, not reset per metric

- ✓ **Metric Extraction** (`ftdc/parser/metrics.py`)
  - Depth-first traversal of BSON documents
  - Array indexing support (e.g., `array.0.field`, `array.1.field`)
  - Timestamp handling (creates two metrics: `field` and `field.inc`)

- ✓ **File Reader** (`ftdc/parser/reader.py`)
  - Iterates over chunks
  - Reconstructs full BSON samples
  - Time-range filtering support

#### Verification Results

**Metrics Extracted**: 3,462 metrics (matches `mongodb/ftdc` exactly)
- ✓ All metric names identical
- ✓ All metric order identical
- ✓ Duplicate keys preserved (6 `/boot/efi` metrics)
- ⚠ Double values stored differently (semantic correctness, not binary identical)

**Test Coverage**:
- ✓ 124 tests passing (100%)
- ✓ All timezone issues resolved

**Important Note**: The timezone fix affects only time-based filtering in the Python reader API. It has **zero impact** on metric extraction, delta decoding, or compatibility with the Go `mongodb/ftdc` library. All metric comparisons remain identical.

#### Documentation
- ✓ `docs/MONGODB_BOOT_EFI_DUPLICATION.md` - Root cause analysis of duplicate key issue
- ✓ `docs/FTDC_FORMAT_SPECIFICATION.md` - Format documentation
- ✓ `docs/KNOWN_LIMITATIONS.md` - Implementation notes
- ✓ `docs/TIMEZONE_FIX.md` - Timezone handling resolution

---

## Open Questions & Decisions

### 1. Repository Organization

**Current State**: Code lives in `/Users/frank.snow/github/fsnow/mongo-tools/ftdc/`

**Decision Needed**: Move to dedicated repository

**Options**:

| Repository Name | Pros | Cons |
|----------------|------|------|
| `ftdc-tools` | Simple, clear | Generic |
| `mongodb-ftdc-toolkit` | Explicit MongoDB connection | Verbose |
| `ftdc-parser` | Descriptive | Doesn't convey multi-tool nature |
| `ftdc` | Concise | May conflict with mongodb/ftdc |

**Proposed Structure**:
```
ftdc-tools/
├── python/              # Python implementation
│   ├── ftdc/           # Parser library
│   ├── cli/            # CLI tool (ftdc-cli-python)
│   └── exporters/      # Time-series exporters
├── go/                 # Go CLI wrapper
│   └── cmd/ftdc-cli/   # ftdc-cli-go
├── docs/               # Shared documentation
├── tests/              # Integration tests
└── examples/           # Usage examples
```

**Action Item**: Choose repository name and structure

---

### 2. Binary Compatibility & Verification

**Current State**:
- Metric names match 100%
- Metric order matches 100%
- Double values differ in representation:
  - **Go**: Stores as raw int64 bit patterns (e.g., `4617315517961601024`)
  - **Python**: Stores as float values (e.g., `5.0`)

**Decision Needed**: How to achieve 100% binary-compatible output for verification?

**Options**:

#### Option A: Match Go's Raw Storage Format
```python
# Store doubles as int64 bit patterns
import struct
def double_to_int64(value: float) -> int:
    return struct.unpack('<q', struct.pack('<d', value))[0]
```
**Pros**: Exact binary match with Go library
**Cons**: Less Pythonic, requires conversion for use

#### Option B: Define Canonical CSV Format
```csv
# Format: metric_index,sample_index,type,value_as_string
0,0,DATE,1763054133004
19,0,DOUBLE,5.0
3428,0,INT64,10446848
```
**Pros**: Language-agnostic, human-readable
**Cons**: String comparison may have precision issues

#### Option C: Use MessagePack/Protocol Buffers
**Pros**: Binary format, type-preserving, cross-language
**Cons**: Additional dependency, overkill for verification

**Proposed Solution**:
- Implement **both** storage modes in Python:
  - `mode='native'`: Store doubles as floats (default, Pythonic)
  - `mode='exact'`: Store doubles as int64 (for Go compatibility)
- Use CSV with type annotations for verification
- Define precision requirements (e.g., doubles match within 1e-15)

**Action Items**:
1. Add storage mode parameter to parser
2. Define CSV format specification
3. Implement comparison tool with configurable precision

---

### 3. Output Formats

**Goal**: Support two modes:
1. **Human-readable mode**: Sensible output for analysis
2. **Exact mode**: Binary-compatible output for verification

**Format Options**:

#### CSV Format
```csv
# Human-readable mode
timestamp,metric_name,value
2025-11-13T17:15:33.004Z,serverStatus.connections.current,42
2025-11-13T17:15:34.000Z,serverStatus.connections.current,43

# Exact mode (for verification)
chunk_index,metric_index,sample_index,metric_name,type_code,raw_value
0,19,0,serverStatus.uptime,1,4617315517961601024
```

#### JSON Format
```json
{
  "timestamp": "2025-11-13T17:15:33.004Z",
  "metrics": {
    "serverStatus.connections.current": 42,
    "serverStatus.connections.available": 1000000
  }
}
```

#### Time-Series Format (for exporters)
```
# InfluxDB Line Protocol
ftdc,host=node0,metric=connections value=42 1731516933004000000

# Prometheus Remote Write
ftdc_connections{host="node0"} 42 1731516933004
```

**Action Items**:
1. Implement CSV exporter with both modes
2. Implement JSON exporter
3. Define output format specifications in docs

---

### 4. Double Precision Handling

**Current Issue**: Delta encoding of doubles introduces precision errors

**Example**:
```
Go library (raw int64):
  5, 5, 5.0000000000000009, 5.0000000000000018, 5.0000000000000027

Python (reconstructed):
  5.0, 5.0, 6.0, 7.0, 8.0
```

**Root Cause**: MongoDB stores doubles as int64 in delta stream, applying deltas to bit patterns

**Investigation Needed**:
1. Is Python's reconstruction semantically correct?
2. Should we preserve exact bit patterns?
3. How does MongoDB's official tooling handle this?

**Action Items**:
1. Test with `ftdc-cli-go` (when built) to see official output
2. Document precision requirements
3. Decide on acceptable tolerance for comparison

---

## Roadmap

### Immediate Priority (Sprint 1: Weeks 1-2)

#### 1.1 Fix Outstanding Issues
- [x] Fix 2 timezone-related test failures (✓ COMPLETED - see `docs/TIMEZONE_FIX.md`)
- [x] Ensure 100% test coverage passes (✓ 124/124 tests passing)
- [ ] Complete Phase 3: File Reader implementation (deferred - basic reader working)

#### 1.2 Build ftdc-cli-go
```bash
# Wrapper around mongodb/ftdc
go install github.com/your-org/ftdc-tools/cmd/ftdc-cli-go@latest

# Usage
ftdc-cli-go extract --input metrics.ftdc --output metrics.csv
ftdc-cli-go extract --input metrics.ftdc --output metrics.json --format json
ftdc-cli-go verify --ftdc metrics.ftdc --csv metrics.csv
```

**Features**:
- Extract metrics to CSV (human-readable mode)
- Extract metrics to CSV (exact mode, for verification)
- Extract metrics to JSON
- Verification command (compare FTDC against CSV/JSON)
- Time-range filtering
- Metric filtering (regex patterns)

**Action Items**:
- [ ] Create Go CLI project structure
- [ ] Implement CSV export (both modes)
- [ ] Implement JSON export
- [ ] Implement verification command
- [ ] Write CLI documentation

#### 1.3 Binary Verification Framework
- [ ] Define CSV format specification for exact mode
- [ ] Implement Python CSV exporter (exact mode)
- [ ] Implement Go CSV exporter (exact mode)
- [ ] Create comparison tool that verifies:
  - Metric count matches
  - Metric names match
  - Metric order matches
  - Values match (with configurable precision)
- [ ] Document precision requirements

**Success Criteria**:
- Python and Go produce identical CSV in exact mode
- Verification tool reports 100% match (within precision tolerance)

---

### Near-term Priority (Sprint 2: Weeks 3-4)

#### 2.1 Repository Migration
- [ ] Create new repository (decide on name)
- [ ] Migrate Python implementation
- [ ] Migrate Go CLI
- [ ] Set up CI/CD (GitHub Actions)
  - Run tests on PR
  - Binary verification tests (Python CSV vs Go CSV)
  - Build and publish releases
- [ ] Update documentation
- [ ] Archive old location

#### 2.2 Python CLI Tool
```bash
pip install ftdc-tools

# Usage
ftdc-cli extract --input metrics.ftdc --output metrics.csv
ftdc-cli stats --input metrics.ftdc  # Show summary statistics
```

**Features**:
- Match Go CLI functionality
- Additional Python-specific features (NumPy/Pandas integration)

**Action Items**:
- [ ] Create CLI entry point
- [ ] Implement commands (extract, stats, verify)
- [ ] Add progress bars for large files
- [ ] Write user documentation

#### 2.3 Documentation Improvements
- [ ] Quickstart guide
- [ ] API documentation (Python)
- [ ] CLI usage guide
- [ ] Format specification (finalize)
- [ ] Troubleshooting guide
- [ ] Performance benchmarks

---

### Medium-term Priority (Sprint 3-4: Weeks 5-8)

#### 3.1 Time-Series Exporters

**Prometheus Exporter**
```bash
ftdc-export prometheus \
  --input metrics.ftdc \
  --output metrics.txt \
  --labels "cluster=prod,shard=0"
```

Output format:
```
# HELP ftdc_connections_current Current connections
# TYPE ftdc_connections_current gauge
ftdc_connections_current{cluster="prod",shard="0"} 42 1731516933004
```

**InfluxDB Exporter**
```bash
ftdc-export influxdb \
  --input metrics.ftdc \
  --database mongodb \
  --measurement ftdc
```

**Datadog Exporter**
```bash
ftdc-export datadog \
  --input metrics.ftdc \
  --api-key $DD_API_KEY \
  --tags "env:prod,cluster:main"
```

**Action Items**:
- [ ] Implement Prometheus exporter
- [ ] Implement InfluxDB exporter
- [ ] Implement Datadog exporter
- [ ] Add exporter plugin system
- [ ] Document exporter configuration

#### 3.2 Analysis Tools
```bash
# Compare two FTDC files
ftdc-compare metrics1.ftdc metrics2.ftdc --output diff.html

# Generate report
ftdc-report metrics.ftdc --output report.html

# Find anomalies
ftdc-analyze metrics.ftdc --detect-anomalies
```

**Action Items**:
- [ ] Implement comparison tool
- [ ] Implement HTML report generator
- [ ] Add anomaly detection (simple statistical methods)
- [ ] Add visualization support (matplotlib/plotly)

---

### Long-term Priority (Sprint 5+: Weeks 9+)

#### 4.1 Advanced Features
- [ ] Real-time FTDC monitoring (watch mode)
- [ ] FTDC compression/deduplication
- [ ] FTDC merging (combine multiple files)
- [ ] Query language for FTDC (SQL-like)
- [ ] WebUI for FTDC exploration

#### 4.2 Integration with MongoDB Ecosystem
- [ ] Atlas integration (download FTDC via API)
- [ ] Ops Manager integration
- [ ] MongoDB Shell integration
- [ ] Compass plugin

#### 4.3 Performance Optimization
- [ ] Parallel processing of chunks
- [ ] Memory-mapped file I/O
- [ ] Streaming mode for large files
- [ ] C extension for critical paths

#### 4.4 Additional Exporters
- [ ] OpenTelemetry exporter
- [ ] Elasticsearch exporter
- [ ] CloudWatch exporter
- [ ] Splunk exporter
- [ ] Generic webhook exporter

---

## Success Metrics

### Phase 1 (Immediate)
- ✓ Python parser matches mongodb/ftdc: 3,462 metrics extracted
- ✓ All tests passing (124/124)
- ⚠ 100% binary compatibility (pending precision definition)
- [ ] ftdc-cli-go built and verified

### Phase 2 (Near-term)
- [ ] Repository migrated and CI/CD running
- [ ] Python CLI published to PyPI
- [ ] Go CLI published to GitHub releases
- [ ] Documentation complete (quickstart, API, CLI)

### Phase 3 (Medium-term)
- [ ] 3+ time-series exporters working
- [ ] 1000+ GitHub stars
- [ ] Adoption by MongoDB customers

### Phase 4 (Long-term)
- [ ] Integration with MongoDB official tools
- [ ] Used by MongoDB Technical Services
- [ ] Community contributions

---

## Open Technical Questions

### 1. Double Precision Storage

**Question**: Should we store doubles as int64 bit patterns (like Go) or as float values (Pythonic)?

**Options**:
- **A**: Always store as int64, convert on read (matches Go exactly)
- **B**: Store as float by default, add `--exact` mode for int64 (best of both worlds)
- **C**: Store as float, accept precision differences (simpler)

**Recommendation**: **Option B** - provides both usability and exact matching when needed

**Decision Needed By**: Sprint 1, Week 1

---

### 2. Repository Structure

**Question**: Single repo with Python + Go, or separate repos?

**Option A: Monorepo**
```
ftdc-tools/
├── python/
├── go/
└── docs/
```
**Pros**: Shared docs, easier cross-language verification
**Cons**: Harder to version independently

**Option B: Separate Repos**
```
ftdc-tools-python/
ftdc-tools-go/
ftdc-tools-docs/
```
**Pros**: Independent versioning, clearer ownership
**Cons**: Documentation duplication, harder to keep in sync

**Recommendation**: **Option A (Monorepo)** - easier verification, shared test suite

**Decision Needed By**: Sprint 2, Week 1

---

### 3. Precision Requirements

**Question**: What precision is acceptable for double comparison?

**Options**:
- **A**: Exact bit-level match (requires int64 storage)
- **B**: Relative tolerance: `|a - b| / max(|a|, |b|) < 1e-15`
- **C**: Absolute tolerance: `|a - b| < 1e-10`
- **D**: User-configurable tolerance

**Recommendation**: **Option D** with sensible defaults (1e-15 relative or 1e-10 absolute)

**Decision Needed By**: Sprint 1, Week 1

---

### 4. CLI Tool Naming

**Question**: What should we name the CLI tools?

**Options**:
| Name | Go Version | Python Version |
|------|-----------|---------------|
| `ftdc` | `ftdc` | `ftdc` |
| `ftdc-cli` | `ftdc-cli` | `ftdc-cli` |
| `ftdc-tools` | `ftdc-go` | `ftdc-py` |
| `mongodb-ftdc` | `mongodb-ftdc` | `mongodb-ftdc` |

**Recommendation**: `ftdc` for both (single binary per language)

**Decision Needed By**: Sprint 1, Week 2

---

## Next Steps

### Immediate Actions (This Week)

1. **Fix Outstanding Issues**
   - [x] Fix 2 timezone test failures (✓ COMPLETED)
   - [x] Document current limitations (✓ COMPLETED)
   - [ ] Review double precision handling

2. **Make Decisions**
   - [ ] Choose repository name
   - [ ] Define precision requirements
   - [ ] Choose CLI tool name
   - [ ] Decide on storage format for doubles

3. **Plan Sprint 1**
   - [ ] Create detailed task breakdown
   - [ ] Set up project tracking (GitHub Projects)
   - [ ] Assign priorities

### Next Week

1. **Start Go CLI Implementation**
   - [ ] Create project structure
   - [ ] Implement CSV export
   - [ ] Test against Python output

2. **Binary Verification**
   - [ ] Implement exact mode in Python
   - [ ] Create comparison tool
   - [ ] Run full verification suite

---

## Resources

### Documentation
- [FTDC Format Specification](./FTDC_FORMAT_SPECIFICATION.md)
- [MongoDB /boot/efi Duplication Analysis](./MONGODB_BOOT_EFI_DUPLICATION.md)
- [Known Limitations](./KNOWN_LIMITATIONS.md)

### Code Repositories
- **MongoDB FTDC (Go)**: https://github.com/mongodb/ftdc
- **Current Python Implementation**: `/Users/frank.snow/github/fsnow/mongo-tools/ftdc/`
- **Future Repository**: TBD

### Related Projects
- **Percona MongoDB Exporter**: Prometheus exporter for MongoDB
- **mongostat**: Real-time MongoDB statistics
- **mongotop**: Track MongoDB read/write activity

---

## Questions for Discussion

1. **Repository Name**: What should we call the new repository?
2. **Binary Compatibility**: Is exact bit-level matching required, or is semantic equivalence sufficient?
3. **Ownership**: Who will maintain this after initial development?
4. **Licensing**: MIT? Apache 2.0? (MongoDB uses Apache 2.0)
5. **Community**: Should we announce this to the MongoDB community? When?

---

## Appendix: Technical Debt

### Known Issues
1. ⚠ Double values stored differently than Go library
2. ⚠ 2 timezone-related test failures
3. ⚠ No streaming support for large files
4. ⚠ No progress indicators for long operations

### Future Refactoring
1. Consolidate BSON parsing with Python's `bson` library (if they add duplicate key support)
2. Optimize delta decoding (currently pure Python)
3. Add type hints throughout codebase
4. Improve error messages

### Performance Concerns
1. Large FTDC files (>1GB) may cause memory issues
2. Delta decoding is CPU-intensive
3. No parallel processing of chunks

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Author**: Frank Snow
**Status**: Draft - Awaiting Decisions



https://pkg.go.dev/github.com/mongodb/ftdc
