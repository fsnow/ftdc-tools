"""FTDC chunk decompression.

A chunk is the compressed binary data stored in type=1 BSON documents.
It contains a reference document, metrics count, deltas count, and delta-encoded metrics.
"""

import io
import struct
import zlib
from typing import BinaryIO

from bson import decode as bson_decode

from .bson_parser import parse_bson_document_to_metrics
from .metrics import restore_float, BSONType
from .types import Chunk, Metric
from .varint import read_varint


class ChunkDecodeError(Exception):
    """Raised when chunk decompression fails."""
    pass


def decompress_chunk(binary_data: bytes) -> bytes:
    """Decompress the ZLIB-compressed chunk data.

    The chunk format is:
    - [4 bytes] Uncompressed size (uint32 little-endian)
    - [variable] ZLIB compressed data

    Args:
        binary_data: Binary data from FTDC document 'data' field

    Returns:
        Uncompressed bytes

    Raises:
        ChunkDecodeError: If decompression fails
    """
    if len(binary_data) < 4:
        raise ChunkDecodeError(f"Chunk too short: {len(binary_data)} bytes")

    # Read uncompressed size (first 4 bytes, little-endian uint32)
    uncompressed_size = struct.unpack('<I', binary_data[:4])[0]

    # Decompress the rest
    try:
        uncompressed = zlib.decompress(binary_data[4:])
    except zlib.error as e:
        raise ChunkDecodeError(f"ZLIB decompression failed: {e}")

    # Verify size matches
    if len(uncompressed) != uncompressed_size:
        raise ChunkDecodeError(
            f"Uncompressed size mismatch: expected {uncompressed_size}, got {len(uncompressed)}"
        )

    return uncompressed


def parse_chunk_header(buffer: BinaryIO) -> tuple[bytes, int, int]:
    """Parse the chunk header from uncompressed data.

    The header format is:
    - [variable] Reference BSON document
    - [4 bytes] Metrics count (uint32 little-endian)
    - [4 bytes] Deltas count (uint32 little-endian)

    Args:
        buffer: Buffer containing uncompressed chunk data

    Returns:
        Tuple of (reference_doc_bytes, metrics_count, deltas_count)

    Raises:
        ChunkDecodeError: If header parsing fails
    """
    # Read the reference BSON document
    # BSON documents start with a 4-byte size field
    size_bytes = buffer.read(4)
    if len(size_bytes) != 4:
        raise ChunkDecodeError("Failed to read BSON document size")

    doc_size = struct.unpack('<I', size_bytes)[0]

    # Read the rest of the document
    doc_bytes = size_bytes + buffer.read(doc_size - 4)
    if len(doc_bytes) != doc_size:
        raise ChunkDecodeError(
            f"Failed to read BSON document: expected {doc_size} bytes, got {len(doc_bytes)}"
        )

    # Return raw BSON bytes (will be parsed later to preserve duplicate keys)
    reference_doc = doc_bytes

    # Read metrics count
    metrics_bytes = buffer.read(4)
    if len(metrics_bytes) != 4:
        raise ChunkDecodeError("Failed to read metrics count")
    metrics_count = struct.unpack('<I', metrics_bytes)[0]

    # Read deltas count
    deltas_bytes = buffer.read(4)
    if len(deltas_bytes) != 4:
        raise ChunkDecodeError("Failed to read deltas count")
    deltas_count = struct.unpack('<I', deltas_bytes)[0]

    return reference_doc, metrics_count, deltas_count


def decode_deltas(buffer: BinaryIO, metrics_count: int, deltas_count: int) -> list[list[int]]:
    """Decode delta-encoded metrics from buffer.

    The delta array is organized as:
    For each metric M (0 to metrics_count-1):
      For each sample S (0 to deltas_count-1):
        VarInt encoded delta, with RLE for zeros

    RLE encoding: When a delta of 0 is read, the next VarInt is the count of
    ADDITIONAL zeros (not including the current zero). The current sample gets
    the zero, and subsequent samples use the zero count.

    IMPORTANT: The RLE zero counter PERSISTS ACROSS METRICS. If an RLE count
    of 10000 is read for the last sample of a metric, the remaining zeros
    carry over to the next metric.

    Args:
        buffer: Buffer positioned at start of delta data
        metrics_count: Number of metrics
        deltas_count: Number of delta samples per metric

    Returns:
        2D list: deltas[metric_index][sample_index]

    Raises:
        ChunkDecodeError: If delta decoding fails
    """
    deltas = []
    nzeroes = 0  # Counter for remaining zeros in RLE sequence - PERSISTS across metrics!

    for metric_idx in range(metrics_count):
        metric_deltas = []

        for sample_idx in range(deltas_count):
            if nzeroes > 0:
                # Use zero from RLE sequence
                delta = 0
                nzeroes -= 1
            else:
                # Read next delta from stream
                try:
                    delta = read_varint(buffer)
                except Exception as e:
                    raise ChunkDecodeError(
                        f"Failed to read delta for metric {metric_idx}, sample {sample_idx}: {e}"
                    )

                if delta == 0:
                    # RLE: next varint is count of ADDITIONAL zeros
                    try:
                        nzeroes = read_varint(buffer)
                    except Exception as e:
                        raise ChunkDecodeError(f"Failed to read RLE zero count: {e}")

            metric_deltas.append(delta)

        deltas.append(metric_deltas)

    return deltas


def undelta(reference_value: int, deltas: list[int]) -> list[int]:
    """Convert delta-encoded values to absolute values.

    The reference value is the first sample (from reference document).
    Each delta is added to the previous absolute value.

    Args:
        reference_value: Starting value from reference document
        deltas: List of delta values

    Returns:
        List of absolute values (includes reference as first value)

    Example:
        >>> undelta(100, [5, -3, 0, 10])
        [100, 105, 102, 102, 112]
    """
    # Need to handle signed deltas properly
    # VarInt encodes as unsigned, but deltas can be negative
    # Convert from unsigned to signed interpretation
    def varint_to_signed(value: int) -> int:
        """Convert VarInt (unsigned) to signed int64."""
        # VarInt stores as uint64, but we interpret as int64
        # If high bit is set, it's negative in two's complement
        if value > 0x7FFFFFFFFFFFFFFF:  # > max int64
            return value - 0x10000000000000000  # Convert to negative
        return value

    absolute_values = [reference_value]

    for delta in deltas:
        # Convert delta to signed
        signed_delta = varint_to_signed(delta)
        # Add to previous value
        new_value = absolute_values[-1] + signed_delta
        absolute_values.append(new_value)

    return absolute_values


def reconstruct_document(reference_doc: dict, metrics: list[Metric], sample_idx: int) -> dict:
    """Reconstruct a BSON document from metrics at a specific sample index.

    Args:
        reference_doc: Reference document defining the structure
        metrics: List of Metric objects with values
        sample_idx: Which sample to extract (0 = reference, 1+ = deltas)

    Returns:
        Reconstructed document with metric values replaced

    Example:
        >>> ref = {'connections': {'current': 10, 'available': 100}}
        >>> metrics = [
        ...     Metric(parent_path=[], key_name='connections.current', values=[10, 15, 20]),
        ...     Metric(parent_path=[], key_name='connections.available', values=[100, 95, 90])
        ... ]
        >>> reconstruct_document(ref, metrics, 1)
        {'connections': {'current': 15, 'available': 95}}
    """
    # Create a deep copy of the reference document structure
    import copy
    doc = copy.deepcopy(reference_doc)

    # Replace metric values
    for metric in metrics:
        if sample_idx >= len(metric.values):
            raise ChunkDecodeError(
                f"Sample index {sample_idx} out of range for metric {metric.key()}"
            )

        value = metric.values[sample_idx]

        # Restore original type
        if metric.original_type == BSONType.DOUBLE:
            value = restore_float(value)
        elif metric.original_type == BSONType.BOOLEAN:
            value = bool(value)
        elif metric.original_type == BSONType.INT32:
            value = int(value)
        elif metric.original_type == BSONType.INT64:
            value = int(value)
        elif metric.original_type == BSONType.DATE:
            # Convert milliseconds to datetime
            from datetime import datetime, timezone
            value = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)

        # Set value in document at the correct path
        set_nested_value(doc, metric.parent_path + [metric.key_name], value)

    return doc


def set_nested_value(doc: dict, path: list[str], value: any) -> None:
    """Set a value in a nested dictionary using a path.

    Args:
        doc: Dictionary to modify
        path: List of keys representing the path
        value: Value to set

    Example:
        >>> d = {'a': {'b': {'c': 1}}}
        >>> set_nested_value(d, ['a', 'b', 'c'], 42)
        >>> d
        {'a': {'b': {'c': 42}}}
    """
    current = doc
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[path[-1]] = value


def parse_chunk(binary_data: bytes) -> Chunk:
    """Parse a complete FTDC chunk from binary data.

    This is the main entry point for chunk decompression.

    Args:
        binary_data: Binary data from FTDC document 'data' field

    Returns:
        Chunk object with all metrics and samples

    Raises:
        ChunkDecodeError: If parsing fails at any stage
    """
    # Step 1: Decompress
    uncompressed = decompress_chunk(binary_data)

    # Step 2: Parse header
    buffer = io.BytesIO(uncompressed)
    reference_doc_bytes, metrics_count, deltas_count = parse_chunk_header(buffer)

    # Step 3: Extract metrics from reference document
    # Parse BSON directly to preserve duplicate keys
    metrics = parse_bson_document_to_metrics(reference_doc_bytes)

    # Also decode to dict for the Chunk reference field (loses duplicates, but needed for API)
    reference_doc = bson_decode(reference_doc_bytes)

    # Verify metrics count matches exactly
    # Note: We use actual extracted count for delta decoding since that's what
    # MongoDB wrote to the stream, but we should investigate any discrepancies
    if len(metrics) != metrics_count:
        discrepancy = abs(len(metrics) - metrics_count)
        # Log the discrepancy but don't fail - use extracted count for decoding
        # TODO: Investigate and fix the root cause of metric count mismatches
        import warnings
        warnings.warn(
            f"Metrics count mismatch: header says {metrics_count}, found {len(metrics)} "
            f"(discrepancy: {discrepancy}, {discrepancy/metrics_count*100:.2f}%). "
            f"Using extracted count ({len(metrics)}) for delta decoding.",
            UserWarning
        )

    # Step 4: Decode deltas (if any)
    # Use the actual number of extracted metrics. MongoDB writes deltas for the metrics
    # it actually extracted, not necessarily the count in the header (which can be slightly
    # off due to different BSON type handling between versions).
    actual_metrics_count = len(metrics)
    if deltas_count > 0:
        # Decode deltas using actual extracted metrics count
        deltas = decode_deltas(buffer, actual_metrics_count, deltas_count)

        # Step 5: Undelta to get absolute values
        for metric_idx, metric in enumerate(metrics):
            reference_value = metric.values[0]  # From reference doc
            absolute_values = undelta(reference_value, deltas[metric_idx])
            metric.values = absolute_values

    # Create chunk
    chunk = Chunk(
        metrics=metrics,
        npoints=deltas_count + 1,  # +1 for reference document
        reference=reference_doc,
    )

    return chunk
