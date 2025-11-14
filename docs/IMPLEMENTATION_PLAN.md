# FTDC Python Implementation Plan

## Strategic Goal

Build a **self-contained, production-ready Python FTDC parser** that the team owns and can customize for Consulting Engineer needs.

## Rationale

### Why Python as Primary Implementation

1. **Team Ownership**: Full control over codebase to customize for CE-specific needs
2. **Maintainability**: Team can fix bugs and add features independently
3. **Learning**: Deep understanding of FTDC format by implementing from scratch
4. **Accessibility**: More CEs familiar with Python than Go
5. **Integration**: Easy to integrate with data analysis tools (pandas, matplotlib, etc.)
6. **Performance**: Adequate for typical FTDC files (1-10MB, parse in seconds)
7. **Self-contained**: Minimal external dependencies using Python stdlib

### Python Suitability for Binary Parsing

Python is well-suited for FTDC parsing:
- **Built-in binary handling**: `struct`, `io.BytesIO`, `zlib`
- **BSON support**: `pymongo.bson` (MongoDB official, stable)
- **Bit manipulation**: Fully capable of VarInt, delta encoding
- **Performance**: Sufficient for diagnostic tool use cases

## Architecture

### Package Structure

```
ftdc/
├── docs/
│   ├── FTDC_FORMAT_SPECIFICATION.md
│   └── IMPLEMENTATION_PLAN.md (this file)
├── ftdc/
│   ├── __init__.py
│   ├── cli.py              # CLI commands
│   ├── service.py          # Atlas API (existing)
│   ├── models.py           # Data models (existing)
│   ├── errors.py           # Exceptions (existing)
│   │
│   ├── parser/             # NEW: FTDC parsing
│   │   ├── __init__.py
│   │   ├── reader.py       # High-level FTDC file reader
│   │   ├── chunk.py        # Chunk decompression
│   │   ├── varint.py       # VarInt encoding/decoding
│   │   ├── metrics.py      # Metric extraction from BSON
│   │   └── types.py        # Data structures (Chunk, Metric)
│   │
│   └── exporters/          # NEW: Output formats
│       ├── __init__.py
│       ├── json.py         # JSON export
│       ├── csv.py          # CSV export
│       └── pandas.py       # DataFrame export (optional)
├── tests/
│   ├── test_varint.py
│   ├── test_chunk.py
│   ├── test_reader.py
│   └── fixtures/           # Test FTDC files
└── pyproject.toml
```

## Implementation Phases

### Phase 1: Core Binary Parsing (Week 1)

**Goal**: Implement low-level binary parsing utilities

#### 1.1 VarInt Codec (`ftdc/parser/varint.py`)
- [ ] `read_varint(buffer)` - Read unsigned VarInt from buffer
- [ ] `write_varint(value)` - Encode uint64 to VarInt bytes
- [ ] Unit tests with known values
- [ ] Validation against Go library output

#### 1.2 Data Structures (`ftdc/parser/types.py`)
- [ ] `Metric` dataclass - stores metric path, values, type
- [ ] `Chunk` dataclass - stores reference doc, metrics, metadata
- [ ] `FTDCDocument` - wrapper for BSON documents with type info

#### 1.3 Metric Extraction (`ftdc/parser/metrics.py`)
- [ ] `extract_metrics(bson_doc)` - Extract numeric values from BSON
- [ ] Depth-first traversal implementation
- [ ] Type handling: double, int32, int64, bool, date, timestamp
- [ ] Schema validation between documents

**Deliverable**: Low-level parsing utilities with unit tests

### Phase 2: Chunk Decompression (Week 2)

**Goal**: Decompress and parse FTDC metric chunks

#### 2.1 Chunk Parser (`ftdc/parser/chunk.py`)
- [ ] `decompress_chunk(binary_data)` - Decompress ZLIB outer layer
- [ ] `parse_chunk_header()` - Read metrics count, deltas count
- [ ] `decode_deltas()` - VarInt + RLE decoding
- [ ] `undelta()` - Convert deltas to absolute values
- [ ] `reconstruct_documents()` - Build BSON from metrics array

#### 2.2 Float/Int Conversion
- [ ] `normalize_float(float64)` - Convert float to int64 (bit reinterpret)
- [ ] `restore_float(int64)` - Convert int64 back to float
- [ ] Handle endianness correctly

#### 2.3 RLE Zero Decoding
- [ ] Detect RLE pairs: `(0, count-1)`
- [ ] Expand zeros into delta stream
- [ ] Handle edge cases (RLE at end of metric)

**Deliverable**: Working chunk decompressor with tests

### Phase 3: File Reader (Week 2-3)

**Goal**: Read complete FTDC files

#### 3.1 FTDC File Reader (`ftdc/parser/reader.py`)
- [ ] `FTDCReader` class - Main file parser
- [ ] `read_documents()` - Iterator over BSON documents
- [ ] `read_chunks()` - Iterator over metric chunks
- [ ] Document type detection (metadata vs metrics)
- [ ] Handle type 0, 1, 2 documents

#### 3.2 Iterator Support
- [ ] Lazy loading - don't read entire file into memory
- [ ] `iter_samples()` - Iterate all samples across all chunks
- [ ] `iter_time_range(start, end)` - Filter by timestamp
- [ ] `iter_metrics(metric_names)` - Filter by metric names

**Deliverable**: Complete FTDC file reader

### Phase 4: Export Formats (Week 3)

**Goal**: Convert FTDC to usable formats

#### 4.1 JSON Exporter (`ftdc/exporters/json.py`)
- [ ] Export to JSON Lines (one sample per line)
- [ ] Pretty-printed JSON option
- [ ] Flattened vs nested structure options
- [ ] Streaming export for large files

#### 4.2 CSV Exporter (`ftdc/exporters/csv.py`)
- [ ] Flatten metrics to CSV columns
- [ ] Include timestamp column
- [ ] Handle nested field names (dot notation)
- [ ] Chunked writing for memory efficiency

#### 4.3 Pandas Exporter (`ftdc/exporters/pandas.py`) [Optional]
- [ ] Export to DataFrame
- [ ] Timestamp as index
- [ ] Metric columns with proper types
- [ ] Useful for analysis/visualization

**Deliverable**: Multiple export formats

### Phase 5: CLI Integration (Week 3-4)

**Goal**: Add convert/analyze commands to CLI

#### 5.1 Convert Command
```bash
ftdc convert <file.ftdc> --format json --output out.json
ftdc convert <file.tar.gz> --format csv --output metrics.csv
ftdc convert <file.ftdc> --format json --time-range 2025-01-01,2025-01-02
```

Features:
- [ ] Auto-detect input format (.ftdc vs .tar.gz)
- [ ] Extract from tar.gz automatically
- [ ] Multiple output formats
- [ ] Time range filtering
- [ ] Metric filtering
- [ ] Progress reporting

#### 5.2 Analyze Command
```bash
ftdc analyze <file.ftdc> --stats
ftdc analyze <file.ftdc> --list-metrics
ftdc analyze <file.ftdc> --metric "serverStatus.connections.current"
```

Features:
- [ ] Show file statistics (samples, time range, size)
- [ ] List all available metrics
- [ ] Extract specific metric time series
- [ ] Summary statistics (min, max, avg, p95, p99)

**Deliverable**: Full CLI with convert and analyze commands

### Phase 6: Testing & Validation (Week 4)

**Goal**: Ensure correctness and reliability

#### 6.1 Unit Tests
- [ ] VarInt encoding/decoding edge cases
- [ ] RLE zero compression
- [ ] Delta encoding/decoding
- [ ] Metric extraction from various BSON structures
- [ ] Float/int bit conversion

#### 6.2 Integration Tests
- [ ] Parse real Atlas FTDC files
- [ ] Compare output with mongodb/ftdc Go library
- [ ] Test all three document types (0, 1, 2)
- [ ] Test multi-chunk files
- [ ] Test edge cases (empty chunks, schema changes)

#### 6.3 Performance Testing
- [ ] Benchmark on 1MB, 10MB, 100MB files
- [ ] Memory usage profiling
- [ ] Streaming vs full-load comparison
- [ ] Identify bottlenecks

**Deliverable**: Comprehensive test suite with >90% coverage

### Phase 7: Documentation (Week 4)

**Goal**: Complete user and developer documentation

#### 7.1 User Documentation
- [ ] Update README with convert/analyze examples
- [ ] CLI usage guide
- [ ] Output format documentation
- [ ] Troubleshooting guide

#### 7.2 Developer Documentation
- [ ] Code comments throughout
- [ ] Architecture overview
- [ ] API documentation (docstrings)
- [ ] Contributing guide

#### 7.3 Learning Resources
- [ ] "How FTDC Works" tutorial
- [ ] Walkthrough of parsing algorithm
- [ ] Common use cases and recipes

**Deliverable**: Complete documentation set

## Validation Strategy

### Use Go Library for Development Validation

1. **Generate test cases**: Use Go library to parse known FTDC files
2. **Compare outputs**: Ensure Python produces identical results
3. **Document differences**: Any intentional deviations
4. **Capture test data**: Save expected outputs for regression testing

### Standalone Operation

Once validated, Python implementation operates as a standalone tool:
- Test suite contains comprehensive test cases and expected outputs
- Self-contained with minimal external dependencies
- Team maintains and extends independently

## Dependencies

### Required
- **Python**: 3.10+ (for better type hints)
- **pymongo**: For BSON parsing (official MongoDB package, stable)
- **click**: CLI framework (already in use)
- **Standard library**: `struct`, `zlib`, `io`, `dataclasses`

### Optional
- **pandas**: For DataFrame export (if useful for CEs)
- **pytest**: Testing framework
- **black**: Code formatting
- **mypy**: Type checking

### Development Dependencies (validation only)
- **mongodb/ftdc Go library**: Used for validation during development, not required at runtime

## Success Criteria

### Functional
- ✅ Parse all FTDC document types (0, 1, 2)
- ✅ Handle all metric types (double, int32, int64, bool, date, timestamp)
- ✅ Decompress chunks correctly (ZLIB + VarInt + RLE + delta)
- ✅ Export to JSON, CSV formats
- ✅ CLI commands work on real Atlas data
- ✅ Match Go library output (during validation)

### Non-Functional
- ✅ Parse 10MB file in <10 seconds
- ✅ Memory efficient (streaming for large files)
- ✅ Well documented (users and developers)
- ✅ Tested (>90% coverage)
- ✅ Type-safe (mypy passes)
- ✅ Self-contained (minimal dependencies)

### Strategic
- ✅ CE team can maintain and extend independently
- ✅ Serves as learning resource for FTDC format
- ✅ Customizable for CE-specific workflows
- ✅ Stable foundation for future enhancements

## Timeline

**Total: 4 weeks**

- Week 1: Core binary parsing (VarInt, types, metrics)
- Week 2: Chunk decompression and file reader
- Week 3: Export formats and CLI integration
- Week 4: Testing, validation, documentation

**Milestones:**
- End of Week 2: Can parse and decompress chunks
- End of Week 3: Full CLI with convert command
- End of Week 4: Production-ready, tested, documented

## Future Enhancements

Post-v1.0 features to consider:

- **Anomaly detection**: Flag unusual metric values
- **Visualization**: Generate plots of key metrics
- **Diff tool**: Compare metrics across FTDC files
- **Query language**: SQL-like queries over FTDC data
- **Cloud integration**: Direct S3/GCS support
- **Real-time streaming**: Parse FTDC as it's written
- **Custom collectors**: Generate FTDC from application metrics

## Optional: Go CLI (Later)

**After** Python implementation is complete and validated:

### Benefits
- Learn Go
- Contribute to MongoDB ecosystem
- Performance comparison
- Simple wrapper around mongodb/ftdc library

### Scope
- CLI argument parsing
- Call mongodb/ftdc library functions
- Format outputs
- No custom parsing logic (library does it all)

**Timeline**: 1 week

**Purpose**: Learning exercise to compare approaches and contribute to MongoDB ecosystem.

## Conclusion

This plan delivers a **production-ready, self-contained Python FTDC parser** that:

1. CE team owns and can customize
2. Provides deep learning opportunity for understanding FTDC
3. Serves customer diagnostic needs effectively
4. Integrates easily with Python data analysis tools
5. Extensible for future CE-specific features

The implementation will be validated against the Go library during development to ensure correctness, then operate as a standalone tool with comprehensive test coverage.
