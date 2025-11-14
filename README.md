# FTDC Tools

MongoDB FTDC (Full Time Diagnostic Data Capture) parsing and analysis tools.

## ⚠️ Project Status: ALPHA

**NOT PRODUCTION READY**

Current limitations:
- 🔴 **Limited test coverage** - only tested with one Atlas FTDC file (MongoDB 8.0.16)
- ⚠️ **No multi-version testing** - MongoDB 7.0, 8.2 not verified
- ⚠️ **No platform verification** - Linux x86_64, ARM64, macOS, Windows not tested

**What works**:
- ✅ Go CLI - Stable wrapper around official mongodb/ftdc library
- ✅ Python parser - Double precision bug fixed (matches mongodb/ftdc behavior)
- ✅ 122 passing unit tests

**Before using in production**: See [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) and [TESTING_COVERAGE.md](docs/TESTING_COVERAGE.md)

---

## Mission

Provide open-source tools for parsing, analyzing, and exporting MongoDB's Full Time Diagnostic Data Capture (FTDC) files to popular monitoring platforms.

## Overview

MongoDB collects diagnostic data through FTDC files. This project provides open-source CLI tools and libraries that enable customers to analyze, export, and integrate their FTDC data with their existing monitoring and observability infrastructure.

## Project Structure

```
ftdc-tools/
├── python/              # Python implementation
│   ├── ftdc/           # Parser library
│   ├── pyproject.toml  # Python package configuration
│   └── uv.lock         # Python dependencies lock file
├── go/                 # Go CLI wrapper (planned)
│   └── cmd/ftdc-cli/   # ftdc-cli-go
├── docs/               # Shared documentation
├── tests/              # Integration tests
└── examples/           # Usage examples (planned)
```

## Features

### Python FTDC Parser

✓ **Complete BSON Parser** - Parses BSON directly from bytes, preserving duplicate keys
✓ **Chunk Decompression** - ZLIB decompression with delta decoding and RLE compression
✓ **Metric Extraction** - Depth-first traversal with array indexing support
✓ **File Reader** - Iterate over chunks with time-range filtering
✓ **Verified Accuracy** - 3,462 metrics extracted, matches `mongodb/ftdc` Go library exactly

### Test Coverage

- ✓ 124 tests passing (100%)
- ✓ All timezone issues resolved
- ✓ Metric names and order match Go library 100%

## Installation

### Python

```bash
cd python
uv pip install -e .
```

Or with standard pip:

```bash
cd python
pip install -e .
```

## Quick Start

### Python Library

```python
from ftdc.parser.reader import FTDCReader

# Read FTDC file
reader = FTDCReader("metrics.ftdc")

# Iterate over samples
for sample in reader.read_samples():
    timestamp = sample.timestamp
    metrics = sample.metrics
    print(f"{timestamp}: {len(metrics)} metrics")
```

## Documentation

- [FTDC Format Specification](docs/FTDC_FORMAT_SPECIFICATION.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [MongoDB /boot/efi Duplication Analysis](docs/MONGODB_BOOT_EFI_DUPLICATION.md)
- [Timezone Fix](docs/TIMEZONE_FIX.md)
- [Development Roadmap](docs/ROADMAP.md)

## Roadmap

### Phase 1: Python FTDC Parser ✓ COMPLETE
- ✓ Core BSON parsing with duplicate key support
- ✓ Chunk decompression and delta decoding
- ✓ Metric extraction and file reading
- ✓ 100% test coverage
- ✓ Verified against mongodb/ftdc Go library

### Phase 2: CLI Tools (In Progress)
- [ ] Go CLI wrapper around mongodb/ftdc
- [ ] Python CLI tool
- [ ] CSV export (human-readable and exact modes)
- [ ] JSON export
- [ ] Verification framework

### Phase 3: Time-Series Exporters (Planned)
- [ ] Prometheus exporter
- [ ] InfluxDB exporter
- [ ] Datadog exporter
- [ ] OpenTelemetry exporter

### Phase 4: Advanced Features (Planned)
- [ ] Real-time monitoring
- [ ] Anomaly detection
- [ ] HTML report generation
- [ ] MongoDB Atlas integration

See [ROADMAP.md](docs/ROADMAP.md) for detailed plans.

## Development

### Running Tests

```bash
cd python
uv run pytest
```

### Project Status

**Current State**: Phase 1 complete, moving to Phase 2 (CLI tools)

**Verification Results**:
- Metrics extracted: 3,462 (matches mongodb/ftdc exactly)
- Metric names: 100% match
- Metric order: 100% match
- Duplicate keys: Preserved (6 /boot/efi metrics)

## Contributing

Contributions are welcome! Please see [ROADMAP.md](docs/ROADMAP.md) for planned features and current priorities.

## Related Projects

- [mongodb/ftdc](https://github.com/mongodb/ftdc) - Official MongoDB FTDC Go library
- [Percona MongoDB Exporter](https://github.com/percona/mongodb_exporter) - Prometheus exporter for MongoDB
- MongoDB native tools: `mongostat`, `mongotop`

## Questions?

See the [documentation](docs/) directory or open an issue.
