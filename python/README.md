# Python FTDC Parser

Python library for parsing MongoDB FTDC (Full Time Diagnostic Data Capture) files.

## Installation

Using uv (recommended):

```bash
uv pip install -e .
```

Or with standard pip:

```bash
pip install -e .
```

## Quick Start

```python
from ftdc.parser.reader import FTDCReader

# Read FTDC file
reader = FTDCReader("path/to/metrics.ftdc")

# Iterate over samples
for sample in reader.read_samples():
    print(f"Timestamp: {sample.timestamp}")
    print(f"Metrics: {len(sample.metrics)}")

    # Access specific metrics
    if "serverStatus.connections.current" in sample.metrics:
        connections = sample.metrics["serverStatus.connections.current"]
        print(f"Current connections: {connections}")
```

## Features

- **Complete BSON Parser**: Parses BSON directly from bytes, preserving duplicate keys
- **Chunk Decompression**: ZLIB decompression with delta decoding and RLE compression
- **Metric Extraction**: Depth-first traversal with array indexing support
- **Time-Range Filtering**: Filter samples by timestamp
- **Verified Accuracy**: 3,462 metrics extracted, matches mongodb/ftdc Go library exactly

## API Reference

### FTDCReader

Main class for reading FTDC files.

```python
reader = FTDCReader(file_path: str)
```

#### Methods

- `read_samples(start_time: datetime = None, end_time: datetime = None)` - Iterator over samples
- `get_metric_names()` - Get list of all metric names
- `get_sample_count()` - Get total number of samples

### Sample

Data class representing a single FTDC sample.

```python
class Sample:
    timestamp: datetime
    metrics: Dict[str, Union[int, float, bool, datetime]]
```

## Development

### Running Tests

```bash
uv run pytest
```

### Test Coverage

- 124 tests passing (100%)
- All timezone issues resolved
- Verified against mongodb/ftdc Go library

## Implementation Details

### BSON Parsing

The parser uses a custom BSON implementation that preserves duplicate keys, which the standard Python `bson` library silently deduplicates. This is critical for accurate FTDC parsing.

### Delta Decoding

FTDC uses delta encoding with RLE (Run-Length Encoding) zero compression. The RLE zero counter persists across all metrics in a chunk, which is a critical implementation detail.

### Metric Naming

Metrics are named using dot notation:
- Simple fields: `serverStatus.uptime`
- Arrays: `array.0.field`, `array.1.field`
- Timestamps: `field` (timestamp value) and `field.inc` (increment value)

## Known Limitations

See [../docs/KNOWN_LIMITATIONS.md](../docs/KNOWN_LIMITATIONS.md) for details.

## Documentation

- [FTDC Format Specification](../docs/FTDC_FORMAT_SPECIFICATION.md)
- [MongoDB /boot/efi Duplication](../docs/MONGODB_BOOT_EFI_DUPLICATION.md)
- [Timezone Fix](../docs/TIMEZONE_FIX.md)

## License

See the root LICENSE file for licensing information.
