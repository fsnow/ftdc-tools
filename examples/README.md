# FTDC Tools Examples

This directory contains example scripts demonstrating how to use the FTDC tools.

## Prerequisites

### Go CLI

Build the Go CLI first:

```bash
cd ../go
go build -o bin/ftdc-cli ./cmd/ftdc-cli
export PATH=$PATH:$(pwd)/bin
```

### Python Library

Install the Python library:

```bash
cd ../python
uv pip install -e .
```

## Examples

### extract_metrics.sh

Bash script showing how to extract metrics using the Go CLI.

```bash
./extract_metrics.sh input.ftdc output.csv
```

### python_extract.py

Python script showing how to use the Python FTDC parser library.

**Extract to CSV:**
```bash
./python_extract.py csv metrics.ftdc output.csv
```

**Extract to JSON:**
```bash
./python_extract.py json metrics.ftdc output.json
```

**Print summary info:**
```bash
./python_extract.py info metrics.ftdc
```

## Sample FTDC Files

To get sample FTDC files for testing:

1. **From a running MongoDB instance:**
   ```bash
   # FTDC files are typically in the diagnostic.data directory
   ls /var/log/mongodb/diagnostic.data/
   ```

2. **From MongoDB Atlas:**
   - Download from Atlas UI: Clusters → ... → Download Logs

3. **From MongoDB support:**
   - FTDC files are often included in diagnostic bundles

## Output Formats

### CSV Format

```csv
timestamp,metric1,metric2,metric3,...
2025-11-13T17:15:33.004Z,42,1000000,128,...
2025-11-13T17:15:34.000Z,43,1000000,129,...
```

### JSON Format

```json
[
  {
    "timestamp": "2025-11-13T17:15:33.004Z",
    "metrics": {
      "serverStatus.connections.current": 42,
      "serverStatus.connections.available": 1000000,
      ...
    }
  }
]
```

## Next Steps

See the main [README.md](../README.md) for more information about the FTDC tools project.
