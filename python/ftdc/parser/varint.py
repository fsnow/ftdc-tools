"""Variable-length integer encoding/decoding.

FTDC uses unsigned VarInt encoding (same as Protocol Buffers):
- Each byte has 7 bits of data + 1 continuation bit (high bit)
- If high bit is 1, more bytes follow
- If high bit is 0, this is the last byte
- Little-endian order
- Maximum of 10 bytes for uint64 (64 bits / 7 bits per byte = 9.14)
"""

import io
from typing import BinaryIO


class VarIntDecodeError(Exception):
    """Raised when VarInt decoding fails."""
    pass


def read_varint(buffer: BinaryIO) -> int:
    """Read an unsigned variable-length integer from a buffer.

    Args:
        buffer: A binary buffer to read from (file-like object)

    Returns:
        The decoded unsigned integer value (0 to 2^64-1)

    Raises:
        VarIntDecodeError: If the VarInt is malformed or too long

    Example:
        >>> import io
        >>> buf = io.BytesIO(b'\\xac\\x02')  # 300 in VarInt
        >>> read_varint(buf)
        300
    """
    result = 0
    shift = 0
    bytes_read = 0

    while True:
        # Read one byte
        byte_data = buffer.read(1)
        if not byte_data:
            if bytes_read == 0:
                raise VarIntDecodeError("Unexpected end of stream: no bytes to read")
            else:
                raise VarIntDecodeError(f"Unexpected end of stream after {bytes_read} bytes")

        byte = byte_data[0]
        bytes_read += 1

        # Check for overflow (max 10 bytes for uint64)
        if bytes_read > 10:
            raise VarIntDecodeError("VarInt too long: exceeds 10 bytes")

        # Extract the lower 7 bits
        value = byte & 0x7F

        # Add to result with appropriate shift
        result |= (value << shift)

        # Check if this is the last byte (high bit is 0)
        if (byte & 0x80) == 0:
            break

        shift += 7

    return result


def write_varint(value: int) -> bytes:
    """Encode an unsigned integer as a variable-length integer.

    Args:
        value: An unsigned integer (0 to 2^64-1)

    Returns:
        Bytes representing the VarInt encoding

    Raises:
        ValueError: If value is negative or too large

    Example:
        >>> write_varint(300)
        b'\\xac\\x02'
        >>> write_varint(1)
        b'\\x01'
        >>> write_varint(0)
        b'\\x00'
    """
    if value < 0:
        raise ValueError(f"VarInt must be non-negative, got {value}")

    if value > 0xFFFFFFFFFFFFFFFF:  # 2^64 - 1
        raise ValueError(f"VarInt too large: {value} exceeds uint64 max")

    # Special case for zero
    if value == 0:
        return b'\x00'

    result = bytearray()

    while value > 0:
        # Extract lower 7 bits
        byte = value & 0x7F
        value >>= 7

        # If there are more bytes to come, set the high bit
        if value > 0:
            byte |= 0x80

        result.append(byte)

    return bytes(result)


def read_varint_from_bytes(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Read a VarInt from a bytes object.

    Args:
        data: Bytes containing VarInt
        offset: Starting position in the bytes

    Returns:
        Tuple of (decoded_value, bytes_consumed)

    Example:
        >>> data = b'\\xac\\x02\\xff'
        >>> value, consumed = read_varint_from_bytes(data)
        >>> value
        300
        >>> consumed
        2
    """
    buffer = io.BytesIO(data[offset:])
    value = read_varint(buffer)
    bytes_consumed = buffer.tell()
    return value, bytes_consumed
