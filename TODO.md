# TODO - Future Work

## High Priority

### 1. Fix Python Parser Double Precision Bug
**Status**: 🔴 CRITICAL - Blocks production use
**Issue**: Python parser fails with `struct.error: required argument is not an integer`
**Files**: `docs/KNOWN_LIMITATIONS.md#python-parser-double-precision-handling`

**Tasks**:
- [ ] Investigate exact conditions that trigger struct.error in restore_float()
- [ ] Review double precision handling in metrics.py and chunk.py
- [ ] Study how mongodb/ftdc handles double reconstruction
- [ ] Add test case with failing FTDC file
- [ ] Implement robust double reconstruction matching Go library

**Priority**: CRITICAL - Python parser unusable until fixed

### 2. Comprehensive FTDC Testing Coverage
**Status**: 🔴 CRITICAL - Required for production
**Issue**: Only tested with single Atlas FTDC file (unknown version/platform)
**Files**: `docs/TESTING_COVERAGE.md`

**Tasks**:
- [ ] Document current Atlas FTDC MongoDB version and platform
- [ ] Acquire FTDC from MongoDB 7.0 (Linux x86_64)
- [ ] Acquire FTDC from MongoDB 8.0 (Linux x86_64)
- [ ] Acquire FTDC from MongoDB 8.2 (Linux x86_64) if available
- [ ] Test on ARM64 platform (Graviton or Apple Silicon)
- [ ] Test replica set FTDC files
- [ ] Create test data repository structure
- [ ] Add CI/CD matrix testing for multiple versions
- [ ] Document version/platform for all test files

**Priority**: CRITICAL - Cannot claim production-ready without this

### 3. Fix Interim File Parsing
**Status**: 🔴 Needs Investigation
**Issue**: `metrics.interim` files don't parse correctly
**Files**: `docs/KNOWN_LIMITATIONS.md#interim-file-parsing`

**Tasks**:
- [ ] Investigate what makes interim files different from completed FTDC files
- [ ] Determine if interim files have incomplete chunks or different structure
- [ ] Add test case with interim file
- [ ] Implement fix or document workaround

**Priority**: Medium - Interim files are temporary and rotate to standard format

---

## Medium Priority

### 2. Binary Verification Framework
**Status**: 🟡 Planned
**From**: `docs/ROADMAP.md` - Sprint 1

**Tasks**:
- [ ] Define CSV format specification for exact mode
- [ ] Implement Python CSV exporter (exact mode)
- [ ] Create comparison tool (Python vs Go output)
- [ ] Document precision requirements for double values

### 3. Python CLI Tool
**Status**: 🟡 Planned
**From**: `docs/ROADMAP.md` - Sprint 2

**Tasks**:
- [ ] Create CLI entry point (similar to Go CLI)
- [ ] Implement commands: extract, stats, verify
- [ ] Add progress bars for large files
- [ ] Write user documentation

---

## Low Priority

### 4. Time-Series Exporters
**Status**: ⚪ Future
**From**: `docs/ROADMAP.md` - Sprint 3-4

**Tasks**:
- [ ] Prometheus exporter
- [ ] InfluxDB exporter
- [ ] Datadog exporter
- [ ] OpenTelemetry exporter

### 5. Advanced Features
**Status**: ⚪ Future
**From**: `docs/ROADMAP.md` - Sprint 5+

**Tasks**:
- [ ] Real-time FTDC monitoring (watch mode)
- [ ] FTDC comparison tool
- [ ] HTML report generation
- [ ] Anomaly detection
- [ ] MongoDB Atlas integration (download FTDC via API)

---

## Documentation Improvements

### 6. Add CLAUDE.md
**Status**: 🟡 Suggested
**Suggestion**: Document local repository references for AI assistance

**Content**:
```markdown
# Resources for AI/Claude Code Sessions

## Local MongoDB Repositories

When working on FTDC tools, these local repositories are available for reference:

- `/Users/frank.snow/github/mongodb/ftdc` - Official MongoDB FTDC Go library
- `/Users/frank.snow/github/mongodb/mongo` - MongoDB server source code

These can be useful for:
- Understanding the FTDC format implementation
- Checking API signatures
- Investigating edge cases
```

---

## Backlog

- [ ] Performance optimization (parallel chunk processing)
- [ ] Streaming mode for very large files (>1GB)
- [ ] C extension for critical paths (delta decoding)
- [ ] Comprehensive benchmarking suite
- [ ] Support for older FTDC format versions (if any exist)

---

**Last Updated**: 2025-11-14
