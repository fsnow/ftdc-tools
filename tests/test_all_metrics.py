#!/usr/bin/env python3
"""Test all metrics files from the 3-node replica set."""

from pathlib import Path
from ftdc.parser.reader import FTDCReader

base_dir = Path("mongodb-logfiles_atlas-14lvdy-shard-0_2025-11-13T1844Z")

# All regular metrics files (not interim)
metrics_files = [
    base_dir / "atlas-14lvdy-shard-00-00.25orp.mongodb.net/27017/diagnostic.data/metrics.2025-11-13T17-15-32Z-00000",
    base_dir / "atlas-14lvdy-shard-00-01.25orp.mongodb.net/27017/diagnostic.data/metrics.2025-11-13T17-15-52Z-00000",
    base_dir / "atlas-14lvdy-shard-00-02.25orp.mongodb.net/27017/diagnostic.data/metrics.2025-11-13T17-15-34Z-00000",
]

print("Testing all regular metrics files from 3-node replica set:\n")

for idx, metrics_file in enumerate(metrics_files, 1):
    print(f"[{idx}/3] Testing: {metrics_file.parent.parent.parent.name}")

    if not metrics_file.exists():
        print(f"  ❌ File not found\n")
        continue

    try:
        reader = FTDCReader(metrics_file)

        # Count chunks
        chunk_count = 0
        total_samples = 0

        for chunk in reader.iter_chunks():
            chunk_count += 1
            total_samples += chunk.size()

        print(f"  ✅ SUCCESS")
        print(f"     Chunks: {chunk_count}")
        print(f"     Total samples: {total_samples}")
        print(f"     File size: {reader._file_size:,} bytes\n")

    except Exception as e:
        print(f"  ❌ FAILED: {e}\n")

print("="*60)
print("Testing all metrics.interim files:\n")

interim_files = [
    base_dir / "atlas-14lvdy-shard-00-00.25orp.mongodb.net/27017/diagnostic.data/metrics.interim",
    base_dir / "atlas-14lvdy-shard-00-01.25orp.mongodb.net/27017/diagnostic.data/metrics.interim",
    base_dir / "atlas-14lvdy-shard-00-02.25orp.mongodb.net/27017/diagnostic.data/metrics.interim",
]

for idx, interim_file in enumerate(interim_files, 1):
    print(f"[{idx}/3] Testing: {interim_file.parent.parent.parent.name}")

    if not interim_file.exists():
        print(f"  ❌ File not found\n")
        continue

    try:
        reader = FTDCReader(interim_file)

        # Count chunks
        chunk_count = 0
        total_samples = 0

        for chunk in reader.iter_chunks():
            chunk_count += 1
            total_samples += chunk.size()

        print(f"  ✅ SUCCESS")
        print(f"     Chunks: {chunk_count}")
        print(f"     Total samples: {total_samples}")
        print(f"     File size: {reader._file_size:,} bytes\n")

    except Exception as e:
        print(f"  ❌ FAILED: {e}\n")
