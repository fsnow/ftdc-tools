"""Test parsing a real FTDC file from MongoDB Atlas."""

import sys
from pathlib import Path

from bson import decode as bson_decode

from ftdc.parser.chunk import parse_chunk
from ftdc.parser.types import FTDCType


def read_ftdc_file(file_path: Path):
    """Read and parse an FTDC file."""
    print(f"Reading FTDC file: {file_path}")
    print(f"File size: {file_path.stat().st_size:,} bytes")
    print()

    with open(file_path, 'rb') as f:
        data = f.read()

    # FTDC files are sequences of BSON documents
    offset = 0
    doc_count = 0
    metadata_count = 0
    metric_chunk_count = 0
    total_samples = 0

    while offset < len(data):
        # Read BSON document
        try:
            # BSON starts with 4-byte size
            if offset + 4 > len(data):
                break

            import struct
            doc_size = struct.unpack('<I', data[offset:offset+4])[0]

            if offset + doc_size > len(data):
                print(f"Warning: Incomplete document at offset {offset}")
                break

            doc_bytes = data[offset:offset+doc_size]
            doc = bson_decode(doc_bytes)
            offset += doc_size
            doc_count += 1

            # Parse document based on type
            doc_type = doc.get('type')
            doc_id = doc.get('_id')

            if doc_type == FTDCType.METADATA:
                metadata_count += 1
                print(f"Document {doc_count}: METADATA (type=0)")
                print(f"  ID: {doc_id}")
                if 'doc' in doc:
                    metadata_doc = doc['doc']
                    print(f"  Contains: {list(metadata_doc.keys())[:5]}...")

            elif doc_type == FTDCType.METRIC_CHUNK:
                metric_chunk_count += 1
                print(f"\nDocument {doc_count}: METRIC CHUNK (type=1)")
                print(f"  ID: {doc_id}")

                # Parse the chunk
                if 'data' in doc:
                    binary_data = doc['data']
                    print(f"  Compressed size: {len(binary_data):,} bytes")

                    try:
                        chunk = parse_chunk(binary_data)
                        print(f"  ✓ Successfully parsed!")
                        print(f"  Metrics: {chunk.num_metrics()}")
                        print(f"  Samples: {chunk.size()}")
                        total_samples += chunk.size()

                        # Show first few metrics
                        print(f"  First metrics:")
                        for i, metric in enumerate(chunk.metrics[:5]):
                            print(f"    {metric.key()}: {metric.values[:3]}...")

                    except Exception as e:
                        print(f"  ✗ Failed to parse: {e}")

            else:
                print(f"Document {doc_count}: UNKNOWN TYPE {doc_type}")

        except Exception as e:
            print(f"Error at offset {offset}: {e}")
            break

    print(f"\n" + "="*60)
    print(f"Summary:")
    print(f"  Total documents: {doc_count}")
    print(f"  Metadata documents: {metadata_count}")
    print(f"  Metric chunks: {metric_chunk_count}")
    print(f"  Total samples: {total_samples:,}")
    print("="*60)


if __name__ == '__main__':
    # Use one of the FTDC files from the Atlas download
    ftdc_file = Path("mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1844Z") / \
                "atlas-14lvdy-shard-00-00.25orp.mongodb.net" / \
                "27017" / "diagnostic.data" / "metrics.interim"

    if not ftdc_file.exists():
        print(f"Error: FTDC file not found: {ftdc_file}")
        sys.exit(1)

    read_ftdc_file(ftdc_file)
