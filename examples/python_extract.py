#!/usr/bin/env python3
"""
Example: Extract metrics from FTDC file using Python library

This example shows how to use the Python FTDC parser to read metrics
from an FTDC file and export them to various formats.
"""

import sys
import csv
import json
from pathlib import Path

# Add parent directory to path to import ftdc
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from ftdc.parser.reader import FTDCReader


def extract_to_csv(ftdc_file, output_file):
    """Extract FTDC metrics to CSV format."""
    reader = FTDCReader(ftdc_file)

    with open(output_file, 'w', newline='') as csvfile:
        writer = None
        metric_names = None

        for sample in reader.read_samples():
            if metric_names is None:
                # Write header on first sample
                metric_names = sorted(sample.metrics.keys())
                writer = csv.DictWriter(csvfile, fieldnames=['timestamp'] + metric_names)
                writer.writeheader()

            # Write sample row
            row = {'timestamp': sample.timestamp.isoformat()}
            row.update({name: sample.metrics.get(name, '') for name in metric_names})
            writer.writerow(row)

    print(f"Extracted {reader.sample_count} samples to {output_file}")


def extract_to_json(ftdc_file, output_file):
    """Extract FTDC metrics to JSON format."""
    reader = FTDCReader(ftdc_file)
    samples = []

    for sample in reader.read_samples():
        samples.append({
            'timestamp': sample.timestamp.isoformat(),
            'metrics': sample.metrics
        })

    with open(output_file, 'w') as jsonfile:
        json.dump(samples, jsonfile, indent=2)

    print(f"Extracted {len(samples)} samples to {output_file}")


def print_summary(ftdc_file):
    """Print summary statistics about FTDC file."""
    reader = FTDCReader(ftdc_file)

    # Read first sample to get metric names
    first_sample = next(reader.read_samples())
    metric_names = sorted(first_sample.metrics.keys())

    print(f"FTDC File: {ftdc_file}")
    print(f"Metrics count: {len(metric_names)}")
    print(f"\nFirst 10 metrics:")
    for name in metric_names[:10]:
        print(f"  - {name}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python_extract.py <command> <ftdc-file> [output-file]")
        print("\nCommands:")
        print("  csv    - Extract to CSV format")
        print("  json   - Extract to JSON format")
        print("  info   - Print summary information")
        print("\nExamples:")
        print("  python_extract.py csv metrics.ftdc output.csv")
        print("  python_extract.py json metrics.ftdc output.json")
        print("  python_extract.py info metrics.ftdc")
        sys.exit(1)

    command = sys.argv[1]
    ftdc_file = sys.argv[2]

    if command == "csv":
        if len(sys.argv) < 4:
            print("Error: output file required for CSV export")
            sys.exit(1)
        extract_to_csv(ftdc_file, sys.argv[3])

    elif command == "json":
        if len(sys.argv) < 4:
            print("Error: output file required for JSON export")
            sys.exit(1)
        extract_to_json(ftdc_file, sys.argv[3])

    elif command == "info":
        print_summary(ftdc_file)

    else:
        print(f"Error: Unknown command '{command}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
