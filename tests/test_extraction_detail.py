#!/usr/bin/env python3
"""Test our extraction vs MongoDB's count in detail."""

import io
import struct
from pathlib import Path

from bson import decode as bson_decode
from ftdc.parser.chunk import decompress_chunk, parse_chunk_header
from ftdc.parser.metrics import metric_for_document


def test_extraction(ftdc_path: Path):
    """Test extraction and show details."""
    with open(ftdc_path, 'rb') as f:
        size_bytes = f.read(4)
        doc_size = struct.unpack('<I', size_bytes)[0]
        rest = f.read(doc_size - 4)
        doc = bson_decode(size_bytes + rest)

        if doc.get('type') == 1:  # Metric chunk
            print(f"Analyzing first metric chunk")

            # Decompress
            binary_data = doc.get('data')
            uncompressed = decompress_chunk(binary_data)

            # Parse header
            buffer = io.BytesIO(uncompressed)
            reference_doc, metrics_count, deltas_count = parse_chunk_header(buffer)

            print(f"MongoDB's count: {metrics_count}")

            # Extract metrics using our code
            metrics = metric_for_document(reference_doc)
            print(f"Our extraction: {len(metrics)}")
            print(f"Discrepancy: {metrics_count - len(metrics)}")

            # Look for histogram metrics specifically
            histogram_metrics = [m for m in metrics if 'histogram' in m.key().lower()]
            print(f"\nHistogram metrics we extracted: {len(histogram_metrics)}")

            # Show first few histogram metrics
            print(f"\nFirst 10 histogram metrics:")
            for metric in histogram_metrics[:10]:
                print(f"  {metric.key()}")

            # Count metrics by pattern
            member_metrics = [m for m in metrics if 'members' in m.key()]
            print(f"\nMetrics with 'members' in key: {len(member_metrics)}")
            if member_metrics[:5]:
                print("First 5:")
                for m in member_metrics[:5]:
                    print(f"  {m.key()}")


if __name__ == "__main__":
    ftdc_file = Path("mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1844Z") / \
                "atlas-14lvdy-shard-00-00.25orp.mongodb.net" / \
                "27017" / "diagnostic.data" / "metrics.interim"

    if ftdc_file.exists():
        test_extraction(ftdc_file)
    else:
        print(f"File not found: {ftdc_file}")
