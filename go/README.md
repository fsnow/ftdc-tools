# Go FTDC CLI

Command-line tool for parsing MongoDB FTDC files, built as a wrapper around the official [mongodb/ftdc](https://github.com/mongodb/ftdc) Go library.

## Installation

### From Source

```bash
cd go
go build -o bin/ftdc-cli ./cmd/ftdc-cli
```

### Using go install

```bash
go install github.com/fsnow/ftdc-tools/go/cmd/ftdc-cli@latest
```

## Usage

### Extract Metrics to CSV

Extract all metrics from an FTDC file to CSV format:

```bash
ftdc-cli extract metrics.ftdc -o output.csv
```

Output to stdout:

```bash
ftdc-cli extract metrics.ftdc
```

### Handle Schema Changes

If your FTDC file contains schema changes (different metrics over time), use the dump prefix option to create multiple CSV files:

```bash
ftdc-cli extract metrics.ftdc --dump-prefix=metrics
# Creates: metrics.0.csv, metrics.1.csv, etc.
```

## CSV Output Format

The CSV output contains one row per metric per sample, with columns:

```csv
metric_name_1,metric_name_2,metric_name_3,...
value_1,value_2,value_3,...
value_1,value_2,value_3,...
```

## Features

- **Fast and Reliable**: Uses the official MongoDB FTDC library
- **Schema Change Detection**: Automatically handles FTDC files with changing metric schemas
- **Streaming**: Memory-efficient processing of large FTDC files
- **Simple CLI**: Easy-to-use command-line interface

## Examples

### Basic Extraction

```bash
# Extract to CSV file
ftdc-cli extract /var/log/mongodb/metrics.ftdc -o analysis.csv

# Extract to stdout and pipe to other tools
ftdc-cli extract metrics.ftdc | head -100
```

### Working with Large Files

```bash
# Use dump mode for files with schema changes
ftdc-cli extract large-metrics.ftdc --dump-prefix=chunks
```

## Development

### Building

```bash
go build -o bin/ftdc-cli ./cmd/ftdc-cli
```

### Dependencies

- [github.com/mongodb/ftdc](https://github.com/mongodb/ftdc) - MongoDB FTDC library
- [github.com/spf13/cobra](https://github.com/spf13/cobra) - CLI framework

## License

See the root LICENSE file for licensing information.
