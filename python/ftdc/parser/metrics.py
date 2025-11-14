"""Metric extraction from BSON documents.

FTDC extracts numeric values from BSON documents via depth-first traversal.
Only numeric types (double, int32, int64, bool, date, timestamp) are considered metrics.
"""

import struct
from datetime import datetime
from typing import Optional

from bson import decode
from bson.codec_options import CodecOptions
from bson.son import SON

from .types import Metric, MetricsExtraction


# BSON type codes (from BSON spec)
class BSONType:
    """BSON type identifiers."""
    DOUBLE = 1
    STRING = 2
    DOCUMENT = 3
    ARRAY = 4
    BINARY = 5
    UNDEFINED = 6  # Deprecated
    OBJECT_ID = 7
    BOOLEAN = 8
    DATE = 9
    NULL = 10
    REGEX = 11
    DBPOINTER = 12  # Deprecated
    JAVASCRIPT = 13
    SYMBOL = 14  # Deprecated
    JAVASCRIPT_WITH_SCOPE = 15
    INT32 = 16
    TIMESTAMP = 17
    INT64 = 18
    DECIMAL128 = 19
    MIN_KEY = 255
    MAX_KEY = 127


def normalize_float(value: float) -> int:
    """Convert a float to int64 by reinterpreting the IEEE 754 bits.

    Args:
        value: A float64 value

    Returns:
        int64 representation of the float's bit pattern

    Example:
        >>> normalize_float(1.5)
        4609434218613702656
    """
    # Pack as double, unpack as signed int64
    packed = struct.pack('<d', value)
    return struct.unpack('<q', packed)[0]


def restore_float(value: int) -> float:
    """Convert an int64 back to float by reinterpreting the bits.

    Args:
        value: int64 bit pattern

    Returns:
        float64 value

    Example:
        >>> restore_float(4609434218613702656)
        1.5
    """
    # Pack as signed int64, unpack as double
    packed = struct.pack('<q', value)
    return struct.unpack('<d', packed)[0]


def epoch_ms(dt: datetime) -> int:
    """Convert datetime to milliseconds since Unix epoch.

    Args:
        dt: datetime object

    Returns:
        Milliseconds since epoch as int64
    """
    return int(dt.timestamp() * 1000)


def is_numeric_type(bson_type: int) -> bool:
    """Check if a BSON type is considered numeric for FTDC purposes.

    Args:
        bson_type: BSON type code

    Returns:
        True if type is numeric (double, int32, int64, bool, date, timestamp)
    """
    return bson_type in (
        BSONType.DOUBLE,
        BSONType.INT32,
        BSONType.INT64,
        BSONType.BOOLEAN,
        BSONType.DATE,
        BSONType.TIMESTAMP,
    )


def is_container_type(bson_type: int) -> bool:
    """Check if a BSON type is a container (document or array).

    Args:
        bson_type: BSON type code

    Returns:
        True if type is a container
    """
    return bson_type in (BSONType.DOCUMENT, BSONType.ARRAY)


def extract_metrics_from_value(
    value: any,
    parent_path: list[str],
    extraction: MetricsExtraction,
) -> None:
    """Extract metrics from a single value (recursive).

    Args:
        value: The value to extract from
        parent_path: Path to this value in the document
        extraction: MetricsExtraction object to append to
    """
    # Import here to avoid circular dependency
    from bson.timestamp import Timestamp

    if isinstance(value, bool):
        # Boolean: convert to 1 or 0
        extraction.values.append(1 if value else 0)
        extraction.types.append(BSONType.BOOLEAN)

    elif isinstance(value, Timestamp):
        # BSON Timestamp: encoded as TWO values (time, increment)
        extraction.values.append(value.time)
        extraction.values.append(value.inc)
        extraction.types.append(BSONType.TIMESTAMP)
        extraction.types.append(BSONType.TIMESTAMP)

    elif isinstance(value, int):
        # Python int (maps to INT32 or INT64 depending on size)
        if -(2**31) <= value < 2**31:
            extraction.values.append(value)
            extraction.types.append(BSONType.INT32)
        else:
            extraction.values.append(value)
            extraction.types.append(BSONType.INT64)

    elif isinstance(value, float):
        # Float: convert to int64 bit pattern
        extraction.values.append(normalize_float(value))
        extraction.types.append(BSONType.DOUBLE)

    elif isinstance(value, datetime):
        # DateTime: convert to milliseconds since epoch
        extraction.values.append(epoch_ms(value))
        extraction.types.append(BSONType.DATE)
        if extraction.timestamp is None:
            extraction.timestamp = value

    # Note: ObjectId is NOT extracted by MongoDB FTDC - it is skipped
    # See MongoDB server source: src/mongo/db/ftdc/util.cpp
    # The switch statement has no case for BSONType::jstOID

    elif isinstance(value, dict):
        # Embedded document: recurse
        extract_metrics_from_document(value, parent_path, extraction)

    elif isinstance(value, list):
        # Array: recurse into each element
        extract_metrics_from_array(value, parent_path, extraction)


def extract_metrics_from_array(
    array: list,
    parent_path: list[str],
    extraction: MetricsExtraction,
) -> None:
    """Extract metrics from an array (recursive).

    Args:
        array: List to extract from
        parent_path: Path to this array in the document
        extraction: MetricsExtraction object to append to
    """
    for item in array:
        extract_metrics_from_value(item, parent_path, extraction)


def extract_metrics_from_document(
    doc: dict,
    parent_path: Optional[list[str]] = None,
    extraction: Optional[MetricsExtraction] = None,
) -> MetricsExtraction:
    """Extract metrics from a BSON document via depth-first traversal.

    Args:
        doc: Dictionary representation of BSON document
        parent_path: Path to this document (for nested docs)
        extraction: Existing extraction to append to (or None to create new)

    Returns:
        MetricsExtraction with all numeric values

    Example:
        >>> doc = {'a': 1, 'b': {'c': 2.5}, 'd': True}
        >>> result = extract_metrics_from_document(doc)
        >>> len(result.values)
        3
        >>> result.values
        [1, ..., 1]  # 1, 2.5 as int64, True as 1
    """
    if parent_path is None:
        parent_path = []

    if extraction is None:
        extraction = MetricsExtraction()

    # Depth-first traversal of document
    # NOTE: MongoDB FTDC includes fields starting with $ (e.g., aggregation stage counters)
    # So we don't skip them
    for key, value in doc.items():
        extract_metrics_from_value(value, parent_path + [key], extraction)

    return extraction


def metric_for_document(
    doc: dict,
    parent_path: Optional[list[str]] = None,
) -> list[Metric]:
    """Create Metric objects for each numeric field in a document.

    This is used to create the metrics list for the reference document.

    Args:
        doc: Dictionary representation of BSON document
        parent_path: Path to this document (for nested docs)

    Returns:
        List of Metric objects, one per numeric field

    Example:
        >>> doc = {'connections': {'current': 10, 'available': 100}}
        >>> metrics = metric_for_document(doc)
        >>> len(metrics)
        2
        >>> metrics[0].key()
        'connections.current'
    """
    from bson.timestamp import Timestamp

    if parent_path is None:
        parent_path = []

    metrics = []

    # MongoDB FTDC includes fields starting with $ (e.g., aggregation stage counters)
    for key, value in doc.items():
        current_path = parent_path + [key]

        if isinstance(value, bool):
            metric = Metric(
                parent_path=parent_path,
                key_name=key,
                values=[1 if value else 0],
                original_type=BSONType.BOOLEAN,
            )
            metrics.append(metric)

        elif isinstance(value, Timestamp):
            # Timestamp creates TWO separate metrics
            # MongoDB FTDC pattern:
            #   1st metric: field name as-is (seconds/time)
            #   2nd metric: field name + ".inc" (increment)
            time_metric = Metric(
                parent_path=parent_path,
                key_name=key,
                values=[value.time],
                original_type=BSONType.TIMESTAMP,
            )
            inc_metric = Metric(
                parent_path=parent_path,
                key_name=f"{key}.inc",
                values=[value.inc],
                original_type=BSONType.TIMESTAMP,
            )
            metrics.append(time_metric)
            metrics.append(inc_metric)

        elif isinstance(value, int):
            if -(2**31) <= value < 2**31:
                bson_type = BSONType.INT32
            else:
                bson_type = BSONType.INT64

            metric = Metric(
                parent_path=parent_path,
                key_name=key,
                values=[value],
                original_type=bson_type,
            )
            metrics.append(metric)

        elif isinstance(value, float):
            metric = Metric(
                parent_path=parent_path,
                key_name=key,
                values=[normalize_float(value)],
                original_type=BSONType.DOUBLE,
            )
            metrics.append(metric)

        elif isinstance(value, datetime):
            metric = Metric(
                parent_path=parent_path,
                key_name=key,
                values=[epoch_ms(value)],
                original_type=BSONType.DATE,
            )
            metrics.append(metric)

        # Note: ObjectId is NOT extracted by MongoDB FTDC - it is skipped
        # See MongoDB server source: src/mongo/db/ftdc/util.cpp

        elif isinstance(value, dict):
            # Recurse into subdocument
            metrics.extend(metric_for_document(value, current_path))

        elif isinstance(value, list):
            # Recurse into array with indexed paths
            # MongoDB FTDC creates indexed paths: array.0.field, array.1.field, etc.
            for idx, item in enumerate(value):
                # Add array index to path: key.0, key.1, etc.
                indexed_path = current_path + [str(idx)]

                if isinstance(item, dict):
                    metrics.extend(metric_for_document(item, indexed_path))
                elif isinstance(item, (bool, int, float, datetime)):
                    # Scalar values in arrays are treated as metrics with indexed key
                    # This handles cases like arrays of numbers
                    if isinstance(item, bool):
                        metric = Metric(
                            parent_path=current_path,
                            key_name=str(idx),
                            values=[1 if item else 0],
                            original_type=BSONType.BOOLEAN,
                        )
                    elif isinstance(item, float):
                        metric = Metric(
                            parent_path=current_path,
                            key_name=str(idx),
                            values=[normalize_float(item)],
                            original_type=BSONType.DOUBLE,
                        )
                    elif isinstance(item, datetime):
                        metric = Metric(
                            parent_path=current_path,
                            key_name=str(idx),
                            values=[epoch_ms(item)],
                            original_type=BSONType.DATE,
                        )
                    elif isinstance(item, int):
                        if -(2**31) <= item < 2**31:
                            bson_type = BSONType.INT32
                        else:
                            bson_type = BSONType.INT64
                        metric = Metric(
                            parent_path=current_path,
                            key_name=str(idx),
                            values=[item],
                            original_type=bson_type,
                        )
                    else:
                        continue
                    metrics.append(metric)

    return metrics


def validate_schema(reference_doc: dict, sample_doc: dict) -> bool:
    """Validate that two documents have the same schema.

    Two documents have the same schema if:
    1. Same number of fields (depth-first)
    2. Same field names in same order
    3. Same types (with numeric types considered equivalent)

    Args:
        reference_doc: Reference document defining the schema
        sample_doc: Document to validate against reference

    Returns:
        True if schemas match, False otherwise
    """
    # Use metric_for_document to get field paths
    ref_metrics = metric_for_document(reference_doc)
    sample_metrics = metric_for_document(sample_doc)

    # Check if same number of metrics
    if len(ref_metrics) != len(sample_metrics):
        return False

    # Check if each metric has the same key and compatible type
    for ref_metric, sample_metric in zip(ref_metrics, sample_metrics):
        # Check that the field paths match
        if ref_metric.key() != sample_metric.key():
            return False

        # Check that types are compatible
        if not types_compatible(ref_metric.original_type, sample_metric.original_type):
            return False

    return True


def types_compatible(type1: int, type2: int) -> bool:
    """Check if two BSON types are compatible for FTDC purposes.

    Numeric types (DOUBLE, INT32, INT64) are considered compatible.

    Args:
        type1: First BSON type
        type2: Second BSON type

    Returns:
        True if types are compatible
    """
    numeric_types = {BSONType.DOUBLE, BSONType.INT32, BSONType.INT64}

    if type1 in numeric_types and type2 in numeric_types:
        return True

    return type1 == type2
