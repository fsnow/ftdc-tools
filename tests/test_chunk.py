"""Tests for FTDC chunk decompression."""

import io
import struct
import zlib

import pytest
from bson import encode as bson_encode

from ftdc.parser.chunk import (
    ChunkDecodeError,
    decode_deltas,
    decompress_chunk,
    parse_chunk,
    parse_chunk_header,
    reconstruct_document,
    set_nested_value,
    undelta,
)
from ftdc.parser.metrics import BSONType, metric_for_document
from ftdc.parser.types import Metric
from ftdc.parser.varint import write_varint


def create_compressed_chunk(reference_doc: dict, deltas: list[list[int]]) -> bytes:
    """Helper to create a compressed chunk for testing.

    Args:
        reference_doc: BSON document to use as reference
        deltas: 2D list of deltas[metric][sample]

    Returns:
        Compressed chunk binary data
    """
    def signed_to_unsigned(value: int) -> int:
        """Convert signed int64 to unsigned uint64 for VarInt encoding."""
        if value < 0:
            # Two's complement: negative values become large unsigned values
            return (1 << 64) + value
        return value

    # Encode reference document as BSON
    ref_bson = bson_encode(reference_doc)

    # Get metrics count
    metrics = metric_for_document(reference_doc)
    metrics_count = len(metrics)

    # Get deltas count (samples per metric)
    deltas_count = len(deltas[0]) if deltas else 0

    # Build uncompressed data
    uncompressed = bytearray()

    # Add reference BSON
    uncompressed.extend(ref_bson)

    # Add metrics count (uint32 LE)
    uncompressed.extend(struct.pack('<I', metrics_count))

    # Add deltas count (uint32 LE)
    uncompressed.extend(struct.pack('<I', deltas_count))

    # Add encoded deltas with RLE
    for metric_deltas in deltas:
        for delta in metric_deltas:
            if delta == 0:
                # For simplicity, don't RLE-encode zeros in test data
                # Just write them as regular varints
                uncompressed.extend(write_varint(0))
                uncompressed.extend(write_varint(0))  # count - 1 = 0 means 1 zero
            else:
                # Convert signed to unsigned for VarInt encoding
                unsigned_delta = signed_to_unsigned(delta)
                uncompressed.extend(write_varint(unsigned_delta))

    # Compress
    compressed = zlib.compress(bytes(uncompressed))

    # Add size header
    size = struct.pack('<I', len(uncompressed))

    return size + compressed


class TestDecompressChunk:
    """Tests for ZLIB decompression."""

    def test_simple_decompression(self):
        """Test basic ZLIB decompression."""
        data = b'Hello, FTDC!'
        compressed = zlib.compress(data)
        size = struct.pack('<I', len(data))
        chunk_data = size + compressed

        result = decompress_chunk(chunk_data)
        assert result == data

    def test_empty_data(self):
        """Test decompressing empty data."""
        data = b''
        compressed = zlib.compress(data)
        size = struct.pack('<I', len(data))
        chunk_data = size + compressed

        result = decompress_chunk(chunk_data)
        assert result == data

    def test_too_short(self):
        """Test that too-short data raises error."""
        with pytest.raises(ChunkDecodeError, match="too short"):
            decompress_chunk(b'\x00\x01')

    def test_invalid_zlib(self):
        """Test that invalid ZLIB data raises error."""
        size = struct.pack('<I', 100)
        invalid_data = size + b'not zlib data'
        with pytest.raises(ChunkDecodeError, match="decompression failed"):
            decompress_chunk(invalid_data)

    def test_size_mismatch(self):
        """Test that size mismatch is detected."""
        data = b'test'
        compressed = zlib.compress(data)
        wrong_size = struct.pack('<I', 999)  # Wrong size
        chunk_data = wrong_size + compressed

        with pytest.raises(ChunkDecodeError, match="size mismatch"):
            decompress_chunk(chunk_data)


class TestParseChunkHeader:
    """Tests for chunk header parsing."""

    def test_simple_header(self):
        """Test parsing a simple chunk header."""
        ref_doc = {'count': 42}
        ref_bson = bson_encode(ref_doc)

        metrics_count = 1
        deltas_count = 5

        data = bytearray()
        data.extend(ref_bson)
        data.extend(struct.pack('<I', metrics_count))
        data.extend(struct.pack('<I', deltas_count))

        buffer = io.BytesIO(bytes(data))
        doc_bytes, m_count, d_count = parse_chunk_header(buffer)

        # parse_chunk_header now returns raw BSON bytes
        assert doc_bytes == ref_bson
        assert m_count == metrics_count
        assert d_count == deltas_count

    def test_nested_document(self):
        """Test parsing header with nested document."""
        ref_doc = {
            'server': {
                'connections': {
                    'current': 10,
                    'available': 100
                }
            }
        }

        ref_bson = bson_encode(ref_doc)
        data = bytearray()
        data.extend(ref_bson)
        data.extend(struct.pack('<I', 2))  # 2 metrics
        data.extend(struct.pack('<I', 3))  # 3 deltas

        buffer = io.BytesIO(bytes(data))
        doc_bytes, m_count, d_count = parse_chunk_header(buffer)

        # parse_chunk_header now returns raw BSON bytes
        assert doc_bytes == ref_bson
        assert m_count == 2
        assert d_count == 3


class TestUndelta:
    """Tests for delta decoding."""

    def test_simple_undelta(self):
        """Test converting deltas to absolute values."""
        result = undelta(100, [5, 3, -2, 0])
        assert result == [100, 105, 108, 106, 106]

    def test_zero_deltas(self):
        """Test with all zero deltas."""
        result = undelta(50, [0, 0, 0])
        assert result == [50, 50, 50, 50]

    def test_negative_deltas(self):
        """Test with negative deltas."""
        result = undelta(100, [-10, -5, -3])
        assert result == [100, 90, 85, 82]

    def test_empty_deltas(self):
        """Test with no deltas."""
        result = undelta(42, [])
        assert result == [42]

    def test_large_values(self):
        """Test with large values."""
        result = undelta(1000000, [100000, 200000, -50000])
        assert result == [1000000, 1100000, 1300000, 1250000]


class TestDecodeDeltas:
    """Tests for delta decoding with RLE."""

    def test_simple_deltas(self):
        """Test decoding simple deltas without RLE."""
        # Create buffer with deltas for 2 metrics, 3 samples each
        data = bytearray()

        # Metric 0: [5, 10, 15]
        data.extend(write_varint(5))
        data.extend(write_varint(10))
        data.extend(write_varint(15))

        # Metric 1: [1, 2, 3]
        data.extend(write_varint(1))
        data.extend(write_varint(2))
        data.extend(write_varint(3))

        buffer = io.BytesIO(bytes(data))
        result = decode_deltas(buffer, metrics_count=2, deltas_count=3)

        assert len(result) == 2
        assert result[0] == [5, 10, 15]
        assert result[1] == [1, 2, 3]

    def test_rle_zeros(self):
        """Test decoding with RLE-encoded zeros."""
        data = bytearray()

        # Metric 0: [5, 0, 0, 0, 10]
        # Encoded as: 5, RLE(0,2), 10
        data.extend(write_varint(5))
        data.extend(write_varint(0))  # RLE marker
        data.extend(write_varint(2))  # 2 additional zeros (total 3)
        data.extend(write_varint(10))

        buffer = io.BytesIO(bytes(data))
        result = decode_deltas(buffer, metrics_count=1, deltas_count=5)

        assert result[0] == [5, 0, 0, 0, 10]

    def test_multiple_rle_sequences(self):
        """Test multiple RLE sequences in one metric."""
        data = bytearray()

        # Metric 0: [1, 0, 0, 5, 0, 0, 0, 0, 3]
        data.extend(write_varint(1))
        data.extend(write_varint(0))  # RLE for 2 zeros
        data.extend(write_varint(1))  # count-1
        data.extend(write_varint(5))
        data.extend(write_varint(0))  # RLE for 4 zeros
        data.extend(write_varint(3))  # count-1
        data.extend(write_varint(3))

        buffer = io.BytesIO(bytes(data))
        result = decode_deltas(buffer, metrics_count=1, deltas_count=9)

        assert result[0] == [1, 0, 0, 5, 0, 0, 0, 0, 3]

    def test_all_zeros(self):
        """Test metric with all zeros."""
        data = bytearray()

        # All 5 zeros encoded as single RLE
        data.extend(write_varint(0))
        data.extend(write_varint(4))  # 4 more zeros (total 5)

        buffer = io.BytesIO(bytes(data))
        result = decode_deltas(buffer, metrics_count=1, deltas_count=5)

        assert result[0] == [0, 0, 0, 0, 0]


class TestSetNestedValue:
    """Tests for setting nested dictionary values."""

    def test_top_level(self):
        """Test setting top-level value."""
        doc = {'a': 1}
        set_nested_value(doc, ['a'], 42)
        assert doc == {'a': 42}

    def test_nested_value(self):
        """Test setting nested value."""
        doc = {'a': {'b': {'c': 1}}}
        set_nested_value(doc, ['a', 'b', 'c'], 42)
        assert doc == {'a': {'b': {'c': 42}}}

    def test_create_nested_path(self):
        """Test creating nested path that doesn't exist."""
        doc = {}
        set_nested_value(doc, ['a', 'b', 'c'], 42)
        assert doc == {'a': {'b': {'c': 42}}}

    def test_partial_path_exists(self):
        """Test when partial path exists."""
        doc = {'a': {'x': 1}}
        set_nested_value(doc, ['a', 'b', 'c'], 42)
        assert doc == {'a': {'x': 1, 'b': {'c': 42}}}


class TestReconstructDocument:
    """Tests for document reconstruction."""

    def test_simple_reconstruction(self):
        """Test reconstructing a simple document."""
        ref_doc = {'count': 10}
        metrics = [
            Metric(
                parent_path=[],
                key_name='count',
                values=[10, 15, 20],
                original_type=BSONType.INT32
            )
        ]

        # Reconstruct sample 1
        doc = reconstruct_document(ref_doc, metrics, 1)
        assert doc == {'count': 15}

        # Reconstruct sample 2
        doc = reconstruct_document(ref_doc, metrics, 2)
        assert doc == {'count': 20}

    def test_nested_reconstruction(self):
        """Test reconstructing nested document."""
        ref_doc = {
            'server': {
                'connections': {
                    'current': 10,
                    'available': 100
                }
            }
        }

        metrics = [
            Metric(
                parent_path=['server', 'connections'],
                key_name='current',
                values=[10, 15, 12],
                original_type=BSONType.INT32
            ),
            Metric(
                parent_path=['server', 'connections'],
                key_name='available',
                values=[100, 95, 98],
                original_type=BSONType.INT32
            )
        ]

        doc = reconstruct_document(ref_doc, metrics, 1)
        assert doc == {
            'server': {
                'connections': {
                    'current': 15,
                    'available': 95
                }
            }
        }

    def test_float_restoration(self):
        """Test that floats are properly restored."""
        from ftdc.parser.metrics import normalize_float

        ref_doc = {'temperature': 98.6}
        metrics = [
            Metric(
                parent_path=[],
                key_name='temperature',
                values=[
                    normalize_float(98.6),
                    normalize_float(99.2),
                    normalize_float(97.8)
                ],
                original_type=BSONType.DOUBLE
            )
        ]

        doc = reconstruct_document(ref_doc, metrics, 1)
        assert doc['temperature'] == pytest.approx(99.2)

    def test_bool_restoration(self):
        """Test that booleans are properly restored."""
        ref_doc = {'enabled': True}
        metrics = [
            Metric(
                parent_path=[],
                key_name='enabled',
                values=[1, 0, 1],
                original_type=BSONType.BOOLEAN
            )
        ]

        doc = reconstruct_document(ref_doc, metrics, 1)
        assert doc == {'enabled': False}

        doc = reconstruct_document(ref_doc, metrics, 2)
        assert doc == {'enabled': True}


class TestParseChunk:
    """Integration tests for full chunk parsing."""

    def test_simple_chunk(self):
        """Test parsing a simple chunk."""
        ref_doc = {'count': 100}

        # Create deltas: count goes 100 -> 105 -> 108 -> 106
        deltas = [[5, 3, -2]]

        chunk_data = create_compressed_chunk(ref_doc, deltas)
        chunk = parse_chunk(chunk_data)

        assert chunk.num_metrics() == 1
        assert chunk.size() == 4  # reference + 3 deltas
        assert len(chunk.metrics[0].values) == 4
        assert chunk.metrics[0].values == [100, 105, 108, 106]

    def test_multiple_metrics(self):
        """Test chunk with multiple metrics."""
        ref_doc = {
            'a': 10,
            'b': 20
        }

        # Deltas for 2 metrics, 3 samples each
        deltas = [
            [1, 2, 3],  # a: 10 -> 11 -> 13 -> 16
            [5, -2, 1]  # b: 20 -> 25 -> 23 -> 24
        ]

        chunk_data = create_compressed_chunk(ref_doc, deltas)
        chunk = parse_chunk(chunk_data)

        assert chunk.num_metrics() == 2
        assert chunk.size() == 4
        assert chunk.metrics[0].values == [10, 11, 13, 16]
        assert chunk.metrics[1].values == [20, 25, 23, 24]

    def test_chunk_with_zeros(self):
        """Test chunk with zero deltas (RLE encoded)."""
        ref_doc = {'value': 50}

        # value: 50 -> 55 -> 55 -> 55 -> 60
        # deltas: [5, 0, 0, 5]
        deltas = [[5, 0, 0, 5]]

        chunk_data = create_compressed_chunk(ref_doc, deltas)
        chunk = parse_chunk(chunk_data)

        assert chunk.metrics[0].values == [50, 55, 55, 55, 60]

    def test_nested_document_chunk(self):
        """Test chunk with nested document."""
        ref_doc = {
            'server': {
                'connections': 10,
                'requests': 100
            }
        }

        # 2 metrics, 2 samples
        deltas = [
            [2, 3],   # connections: 10 -> 12 -> 15
            [10, 20]  # requests: 100 -> 110 -> 130
        ]

        chunk_data = create_compressed_chunk(ref_doc, deltas)
        chunk = parse_chunk(chunk_data)

        assert chunk.num_metrics() == 2
        assert chunk.size() == 3

        # Verify metric paths
        keys = {m.key() for m in chunk.metrics}
        assert 'server.connections' in keys
        assert 'server.requests' in keys
