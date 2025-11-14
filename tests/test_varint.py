"""Tests for VarInt encoding/decoding."""

import io
import pytest
from ftdc.parser.varint import (
    read_varint,
    write_varint,
    read_varint_from_bytes,
    VarIntDecodeError,
)


class TestWriteVarInt:
    """Tests for encoding integers as VarInt."""

    def test_zero(self):
        """Test encoding zero."""
        assert write_varint(0) == b'\x00'

    def test_one(self):
        """Test encoding one."""
        assert write_varint(1) == b'\x01'

    def test_127(self):
        """Test encoding 127 (max single byte value)."""
        assert write_varint(127) == b'\x7f'

    def test_128(self):
        """Test encoding 128 (first two-byte value)."""
        assert write_varint(128) == b'\x80\x01'

    def test_300(self):
        """Test encoding 300 (example from spec).

        300 in binary: 100101100
        Split into 7-bit chunks: 0000010 0101100
        Little-endian VarInt: 10101100 00000010
        Bytes: 0xAC 0x02
        """
        assert write_varint(300) == b'\xac\x02'

    def test_16384(self):
        """Test encoding 16384 (first three-byte value)."""
        # 16384 = 0x4000
        # Binary: 100000000000000
        # 7-bit chunks: 0000001 0000000 0000000
        # VarInt: 10000000 10000000 00000001
        assert write_varint(16384) == b'\x80\x80\x01'

    def test_max_uint32(self):
        """Test encoding maximum uint32 value."""
        max_uint32 = 0xFFFFFFFF  # 4,294,967,295
        result = write_varint(max_uint32)
        assert len(result) == 5  # Requires 5 bytes

    def test_max_uint64(self):
        """Test encoding maximum uint64 value."""
        max_uint64 = 0xFFFFFFFFFFFFFFFF  # 2^64 - 1
        result = write_varint(max_uint64)
        assert len(result) == 10  # Requires 10 bytes (max for VarInt)

    def test_negative_raises_error(self):
        """Test that negative values raise an error."""
        with pytest.raises(ValueError, match="non-negative"):
            write_varint(-1)

    def test_too_large_raises_error(self):
        """Test that values larger than uint64 raise an error."""
        too_large = 0xFFFFFFFFFFFFFFFF + 1
        with pytest.raises(ValueError, match="too large"):
            write_varint(too_large)


class TestReadVarInt:
    """Tests for decoding VarInt."""

    def test_zero(self):
        """Test decoding zero."""
        buf = io.BytesIO(b'\x00')
        assert read_varint(buf) == 0

    def test_one(self):
        """Test decoding one."""
        buf = io.BytesIO(b'\x01')
        assert read_varint(buf) == 1

    def test_127(self):
        """Test decoding 127."""
        buf = io.BytesIO(b'\x7f')
        assert read_varint(buf) == 127

    def test_128(self):
        """Test decoding 128."""
        buf = io.BytesIO(b'\x80\x01')
        assert read_varint(buf) == 128

    def test_300(self):
        """Test decoding 300."""
        buf = io.BytesIO(b'\xac\x02')
        assert read_varint(buf) == 300

    def test_16384(self):
        """Test decoding 16384."""
        buf = io.BytesIO(b'\x80\x80\x01')
        assert read_varint(buf) == 16384

    def test_max_uint64(self):
        """Test decoding maximum uint64 value."""
        # Max uint64 encoded as VarInt (10 bytes)
        max_uint64 = 0xFFFFFFFFFFFFFFFF
        encoded = write_varint(max_uint64)
        buf = io.BytesIO(encoded)
        assert read_varint(buf) == max_uint64

    def test_empty_stream_raises_error(self):
        """Test that empty stream raises error."""
        buf = io.BytesIO(b'')
        with pytest.raises(VarIntDecodeError, match="no bytes to read"):
            read_varint(buf)

    def test_truncated_varint_raises_error(self):
        """Test that truncated VarInt raises error."""
        # Start of a multi-byte VarInt but incomplete
        buf = io.BytesIO(b'\x80')  # High bit set but no next byte
        with pytest.raises(VarIntDecodeError, match="Unexpected end of stream"):
            read_varint(buf)

    def test_too_long_varint_raises_error(self):
        """Test that VarInt longer than 10 bytes raises error."""
        # Create an invalid 11-byte VarInt
        invalid = bytes([0x80] * 11)
        buf = io.BytesIO(invalid)
        with pytest.raises(VarIntDecodeError, match="too long"):
            read_varint(buf)

    def test_multiple_varints_in_sequence(self):
        """Test reading multiple VarInts from same stream."""
        # Encode: 1, 300, 127
        data = write_varint(1) + write_varint(300) + write_varint(127)
        buf = io.BytesIO(data)

        assert read_varint(buf) == 1
        assert read_varint(buf) == 300
        assert read_varint(buf) == 127


class TestRoundTrip:
    """Tests for encoding and then decoding."""

    @pytest.mark.parametrize("value", [
        0, 1, 127, 128, 255, 256,
        300, 1000, 10000, 65535, 65536,
        0xFFFFFFFF,  # max uint32
        0xFFFFFFFFFFFFFFFF,  # max uint64
    ])
    def test_round_trip(self, value):
        """Test that encoding and decoding returns the original value."""
        encoded = write_varint(value)
        buf = io.BytesIO(encoded)
        decoded = read_varint(buf)
        assert decoded == value


class TestReadVarIntFromBytes:
    """Tests for reading VarInt from bytes."""

    def test_read_from_bytes(self):
        """Test reading VarInt from bytes object."""
        data = b'\xac\x02\xff'  # 300 followed by extra data
        value, consumed = read_varint_from_bytes(data)
        assert value == 300
        assert consumed == 2

    def test_read_with_offset(self):
        """Test reading VarInt from bytes with offset."""
        data = b'\xff\xff\xac\x02'  # 300 at offset 2
        value, consumed = read_varint_from_bytes(data, offset=2)
        assert value == 300
        assert consumed == 2

    def test_read_single_byte(self):
        """Test reading single-byte VarInt."""
        data = b'\x7f'
        value, consumed = read_varint_from_bytes(data)
        assert value == 127
        assert consumed == 1


class TestVarIntExamples:
    """Tests based on examples from FTDC specification."""

    def test_rle_zero_encoding(self):
        """Test RLE zero pairs encoding.

        In FTDC, RLE is encoded as: VarInt(0) followed by VarInt(count-1)
        """
        # Encode a zero followed by count of 2 additional zeros (total 3 zeros)
        zero = write_varint(0)
        count = write_varint(2)  # count - 1
        rle_pair = zero + count

        buf = io.BytesIO(rle_pair)
        assert read_varint(buf) == 0
        assert read_varint(buf) == 2

    def test_delta_sequence(self):
        """Test encoding a sequence of deltas."""
        # Deltas: [5, 0, 0, 0, 10, 3]
        # RLE encoding: [5, 0, 2, 10, 3] where (0, 2) represents 3 zeros
        deltas = [5, 0, 2, 10, 3]
        encoded = b''.join(write_varint(d) for d in deltas)

        buf = io.BytesIO(encoded)
        decoded = [read_varint(buf) for _ in range(5)]
        assert decoded == deltas
