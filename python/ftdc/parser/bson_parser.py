"""BSON parser that preserves duplicate keys.

Python's bson library silently deduplicates keys when decoding BSON to dict.
This parser extracts metrics directly from BSON bytes, preserving all duplicate
entries in the order they appear.
"""

import io
import struct
from datetime import datetime
from typing import BinaryIO

from bson import Timestamp

from .metrics import BSONType, Metric


class BSONParseError(Exception):
    """Raised when BSON parsing fails."""
    pass


def read_cstring(buffer: BinaryIO) -> str:
    """Read null-terminated C string from buffer."""
    chars = []
    while True:
        byte = buffer.read(1)
        if not byte:
            raise BSONParseError("Unexpected end of buffer reading C string")
        if byte == b'\x00':
            break
        chars.append(byte)

    try:
        return b''.join(chars).decode('utf-8')
    except UnicodeDecodeError as e:
        raise BSONParseError(f"Invalid UTF-8 in C string: {e}")


def read_int32(buffer: BinaryIO) -> int:
    """Read little-endian int32."""
    data = buffer.read(4)
    if len(data) != 4:
        raise BSONParseError("Unexpected end of buffer reading int32")
    return struct.unpack('<i', data)[0]


def read_int64(buffer: BinaryIO) -> int:
    """Read little-endian int64."""
    data = buffer.read(8)
    if len(data) != 8:
        raise BSONParseError("Unexpected end of buffer reading int64")
    return struct.unpack('<q', data)[0]


def read_uint64(buffer: BinaryIO) -> int:
    """Read little-endian uint64."""
    data = buffer.read(8)
    if len(data) != 8:
        raise BSONParseError("Unexpected end of buffer reading uint64")
    return struct.unpack('<Q', data)[0]


def read_double(buffer: BinaryIO) -> float:
    """Read little-endian double."""
    data = buffer.read(8)
    if len(data) != 8:
        raise BSONParseError("Unexpected end of buffer reading double")
    return struct.unpack('<d', data)[0]


def read_boolean(buffer: BinaryIO) -> bool:
    """Read boolean (1 byte)."""
    data = buffer.read(1)
    if len(data) != 1:
        raise BSONParseError("Unexpected end of buffer reading boolean")
    return data[0] != 0


def skip_bytes(buffer: BinaryIO, count: int) -> None:
    """Skip specified number of bytes."""
    data = buffer.read(count)
    if len(data) != count:
        raise BSONParseError(f"Unexpected end of buffer skipping {count} bytes")


def parse_bson_document_to_metrics(
    bson_bytes: bytes,
    parent_path: list[str] | None = None
) -> list[Metric]:
    """Parse BSON document and extract metrics, preserving duplicate keys.

    This function parses BSON directly from bytes without converting to dict,
    which preserves duplicate keys that would otherwise be lost.

    Args:
        bson_bytes: Raw BSON document bytes
        parent_path: Parent path for nested documents

    Returns:
        List of Metric objects in the order they appear in BSON

    Raises:
        BSONParseError: If BSON parsing fails
    """
    if parent_path is None:
        parent_path = []

    import io
    buffer = io.BytesIO(bson_bytes)

    # Read document size
    doc_size = read_int32(buffer)

    # Verify document size matches
    if doc_size != len(bson_bytes):
        raise BSONParseError(
            f"Document size mismatch: header says {doc_size}, got {len(bson_bytes)}"
        )

    metrics = []

    # Parse elements until we hit the terminator
    while True:
        # Read type byte
        type_data = buffer.read(1)
        if not type_data:
            raise BSONParseError("Unexpected end of document")

        type_byte = type_data[0]

        # 0x00 = end of document
        if type_byte == 0x00:
            break

        # Read field name
        field_name = read_cstring(buffer)

        # Parse value based on type
        metrics.extend(_parse_element(buffer, type_byte, field_name, parent_path))

    return metrics


def _parse_element(
    buffer: BinaryIO,
    type_byte: int,
    field_name: str,
    parent_path: list[str]
) -> list[Metric]:
    """Parse a single BSON element and extract metrics.

    Args:
        buffer: Buffer positioned at element value
        type_byte: BSON type code
        field_name: Field name
        parent_path: Parent path

    Returns:
        List of metrics extracted from this element
    """
    metrics = []

    if type_byte == 0x01:  # double
        value = read_double(buffer)
        metric = Metric(
            parent_path=parent_path,
            key_name=field_name,
            values=[value],
            original_type=BSONType.DOUBLE,
        )
        metrics.append(metric)

    elif type_byte == 0x02:  # string
        str_len = read_int32(buffer)
        skip_bytes(buffer, str_len)  # Skip string data (including null terminator)
        # Strings are not metrics - skip

    elif type_byte == 0x05:  # binary
        bin_len = read_int32(buffer)
        skip_bytes(buffer, 1)  # Skip subtype byte
        skip_bytes(buffer, bin_len)  # Skip binary data
        # Binary is not a metric - skip

    elif type_byte == 0x07:  # ObjectId
        skip_bytes(buffer, 12)  # ObjectId is 12 bytes
        # Note: ObjectId is NOT extracted by MongoDB FTDC - it is skipped
        # See MongoDB server source: src/mongo/db/ftdc/util.cpp

    elif type_byte == 0x03:  # embedded document
        doc_size = read_int32(buffer)
        # Read document bytes (including the size we just read)
        buffer.seek(buffer.tell() - 4)
        doc_bytes = buffer.read(doc_size)

        # Recursively parse embedded document
        new_path = parent_path + [field_name]
        metrics.extend(parse_bson_document_to_metrics(doc_bytes, new_path))

    elif type_byte == 0x04:  # array
        arr_size = read_int32(buffer)
        # Read array bytes (including the size we just read)
        buffer.seek(buffer.tell() - 4)
        arr_bytes = buffer.read(arr_size)

        # Parse array as document (array elements have numeric string keys)
        # We need to extract the numeric indices and create indexed paths
        arr_buffer = io.BytesIO(arr_bytes)
        arr_buffer.read(4)  # Skip size

        while True:
            type_data = arr_buffer.read(1)
            if not type_data or type_data[0] == 0x00:
                break

            arr_type = type_data[0]
            arr_index = read_cstring(arr_buffer)  # This is "0", "1", "2", etc.

            # Create indexed path
            indexed_path = parent_path + [field_name, arr_index]

            # Parse array element
            metrics.extend(_parse_element(arr_buffer, arr_type, arr_index, indexed_path[:-1]))

    elif type_byte == 0x08:  # boolean
        value = read_boolean(buffer)
        metric = Metric(
            parent_path=parent_path,
            key_name=field_name,
            values=[value],
            original_type=BSONType.BOOLEAN,
        )
        metrics.append(metric)

    elif type_byte == 0x09:  # UTC datetime
        millis = read_int64(buffer)
        # Store as integer milliseconds (not datetime object)
        # Will be converted back to datetime during reconstruction
        metric = Metric(
            parent_path=parent_path,
            key_name=field_name,
            values=[millis],
            original_type=BSONType.DATE,
        )
        metrics.append(metric)

    elif type_byte == 0x10:  # int32
        value = read_int32(buffer)
        metric = Metric(
            parent_path=parent_path,
            key_name=field_name,
            values=[value],
            original_type=BSONType.INT32,
        )
        metrics.append(metric)

    elif type_byte == 0x11:  # Timestamp
        # Timestamp is 8 bytes: increment (4 bytes) + time (4 bytes)
        # IMPORTANT: In BSON wire format, increment comes FIRST
        value_bytes = buffer.read(8)
        if len(value_bytes) != 8:
            raise BSONParseError("Unexpected end of buffer reading Timestamp")

        inc, time = struct.unpack('<II', value_bytes)
        ts = Timestamp(time, inc)

        # Timestamp creates TWO metrics:
        # 1. field_name (the time component)
        # 2. field_name.inc (the increment component)
        time_metric = Metric(
            parent_path=parent_path,
            key_name=field_name,
            values=[time],
            original_type=BSONType.TIMESTAMP,
        )
        inc_metric = Metric(
            parent_path=parent_path,
            key_name=f"{field_name}.inc",
            values=[inc],
            original_type=BSONType.TIMESTAMP,
        )
        metrics.append(time_metric)
        metrics.append(inc_metric)

    elif type_byte == 0x12:  # int64
        value = read_int64(buffer)
        metric = Metric(
            parent_path=parent_path,
            key_name=field_name,
            values=[value],
            original_type=BSONType.INT64,
        )
        metrics.append(metric)

    else:
        raise BSONParseError(f"Unsupported BSON type: 0x{type_byte:02x} for field '{field_name}'")

    return metrics
