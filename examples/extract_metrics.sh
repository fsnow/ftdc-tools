#!/bin/bash
# Example: Extract metrics from FTDC file to CSV using Go CLI

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input-ftdc-file> <output-csv-file>"
    echo "Example: $0 metrics.ftdc output.csv"
    exit 1
fi

INPUT_FILE=$1
OUTPUT_FILE=$2

# Check if ftdc-cli is available
if ! command -v ftdc-cli &> /dev/null; then
    echo "Error: ftdc-cli not found. Please build it first:"
    echo "  cd go && go build -o bin/ftdc-cli ./cmd/ftdc-cli"
    echo "  export PATH=\$PATH:\$(pwd)/go/bin"
    exit 1
fi

echo "Extracting metrics from $INPUT_FILE to $OUTPUT_FILE..."
ftdc-cli extract "$INPUT_FILE" -o "$OUTPUT_FILE"

echo "Done! Extracted metrics to $OUTPUT_FILE"
echo "Number of rows: $(wc -l < "$OUTPUT_FILE")"
