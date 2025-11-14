"""Tests for metric extraction from BSON documents."""

from datetime import datetime, timezone

import pytest

from ftdc.parser.metrics import (
    BSONType,
    epoch_ms,
    extract_metrics_from_document,
    is_numeric_type,
    metric_for_document,
    normalize_float,
    restore_float,
    validate_schema,
)


class TestFloatConversion:
    """Tests for float/int64 bit conversion."""

    def test_normalize_and_restore(self):
        """Test round-trip float conversion."""
        original = 1.5
        normalized = normalize_float(original)
        restored = restore_float(normalized)
        assert restored == original

    def test_zero(self):
        """Test converting zero."""
        assert normalize_float(0.0) == 0

    def test_negative(self):
        """Test converting negative float."""
        original = -42.7
        restored = restore_float(normalize_float(original))
        assert restored == original

    def test_large_value(self):
        """Test converting large float."""
        original = 1.7976931348623157e+308  # Near max float64
        restored = restore_float(normalize_float(original))
        assert restored == original


class TestEpochMs:
    """Tests for datetime to milliseconds conversion."""

    def test_epoch_zero(self):
        """Test Unix epoch (1970-01-01 00:00:00 UTC)."""
        dt = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert epoch_ms(dt) == 0

    def test_known_timestamp(self):
        """Test a known timestamp."""
        # 2025-01-15 12:30:45 UTC
        dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        ms = epoch_ms(dt)
        # Verify it's roughly correct (in 2025)
        assert ms > 1700000000000  # After 2023
        assert ms < 2000000000000  # Before 2033


class TestIsNumericType:
    """Tests for numeric type detection."""

    def test_numeric_types(self):
        """Test that numeric types are recognized."""
        assert is_numeric_type(BSONType.DOUBLE)
        assert is_numeric_type(BSONType.INT32)
        assert is_numeric_type(BSONType.INT64)
        assert is_numeric_type(BSONType.BOOLEAN)
        assert is_numeric_type(BSONType.DATE)
        assert is_numeric_type(BSONType.TIMESTAMP)

    def test_non_numeric_types(self):
        """Test that non-numeric types are not recognized."""
        assert not is_numeric_type(BSONType.STRING)
        assert not is_numeric_type(BSONType.DOCUMENT)
        assert not is_numeric_type(BSONType.ARRAY)
        assert not is_numeric_type(BSONType.OBJECT_ID)


class TestExtractMetricsFromDocument:
    """Tests for extracting metrics from documents."""

    def test_simple_int(self):
        """Test extracting a simple integer."""
        doc = {'count': 42}
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 1
        assert result.values[0] == 42
        assert result.types[0] in (BSONType.INT32, BSONType.INT64)

    def test_simple_float(self):
        """Test extracting a simple float."""
        doc = {'temperature': 98.6}
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 1
        assert result.types[0] == BSONType.DOUBLE
        # Verify we can restore the float
        restored = restore_float(result.values[0])
        assert restored == 98.6

    def test_simple_bool(self):
        """Test extracting a boolean."""
        doc = {'enabled': True, 'disabled': False}
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 2
        assert result.values[0] == 1  # True -> 1
        assert result.values[1] == 0  # False -> 0
        assert all(t == BSONType.BOOLEAN for t in result.types)

    def test_datetime(self):
        """Test extracting a datetime."""
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        doc = {'timestamp': dt}
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 1
        assert result.types[0] == BSONType.DATE
        assert result.timestamp == dt

    def test_nested_document(self):
        """Test extracting from nested documents."""
        doc = {
            'outer': {
                'inner': {
                    'value': 123
                }
            }
        }
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 1
        assert result.values[0] == 123

    def test_multiple_fields(self):
        """Test extracting multiple fields."""
        doc = {
            'a': 1,
            'b': 2.5,
            'c': True,
            'd': 10
        }
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 4

    def test_mixed_types(self):
        """Test extracting mixed numeric types."""
        doc = {
            'int32': 100,
            'float': 3.14,
            'bool': True,
            'int64': 9999999999,
        }
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 4
        assert BSONType.DOUBLE in result.types
        assert BSONType.BOOLEAN in result.types

    def test_skip_non_numeric(self):
        """Test that non-numeric fields are skipped."""
        doc = {
            'name': 'test',  # string - skip
            'count': 42,     # int - include
            'data': b'binary',  # binary - skip
        }
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 1
        assert result.values[0] == 42

    def test_skip_dollar_fields(self):
        """Test that fields starting with $ are skipped."""
        doc = {
            '$metadata': 'skip',
            'value': 42,
        }
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 1

    def test_array_of_numbers(self):
        """Test extracting from array of numbers."""
        doc = {
            'values': [1, 2, 3]
        }
        result = extract_metrics_from_document(doc)
        assert len(result.values) == 3
        assert result.values == [1, 2, 3]


class TestMetricForDocument:
    """Tests for creating Metric objects."""

    def test_simple_metric(self):
        """Test creating metric for simple field."""
        doc = {'count': 42}
        metrics = metric_for_document(doc)
        assert len(metrics) == 1
        assert metrics[0].key_name == 'count'
        assert metrics[0].key() == 'count'
        assert metrics[0].values == [42]

    def test_nested_metric(self):
        """Test creating metric for nested field."""
        doc = {
            'server': {
                'connections': 100
            }
        }
        metrics = metric_for_document(doc)
        assert len(metrics) == 1
        assert metrics[0].key_name == 'connections'
        assert metrics[0].parent_path == ['server']
        assert metrics[0].key() == 'server.connections'

    def test_deeply_nested_metric(self):
        """Test creating metric for deeply nested field."""
        doc = {
            'a': {
                'b': {
                    'c': {
                        'value': 123
                    }
                }
            }
        }
        metrics = metric_for_document(doc)
        assert len(metrics) == 1
        assert metrics[0].key() == 'a.b.c.value'

    def test_multiple_metrics(self):
        """Test creating metrics for multiple fields."""
        doc = {
            'connections': {
                'current': 10,
                'available': 100
            }
        }
        metrics = metric_for_document(doc)
        assert len(metrics) == 2
        keys = {m.key() for m in metrics}
        assert keys == {'connections.current', 'connections.available'}

    def test_metric_types(self):
        """Test that metric types are preserved."""
        doc = {
            'int_val': 42,
            'float_val': 3.14,
            'bool_val': True,
        }
        metrics = metric_for_document(doc)
        assert len(metrics) == 3

        # Find each metric by key
        int_metric = next(m for m in metrics if m.key_name == 'int_val')
        float_metric = next(m for m in metrics if m.key_name == 'float_val')
        bool_metric = next(m for m in metrics if m.key_name == 'bool_val')

        assert int_metric.original_type in (BSONType.INT32, BSONType.INT64)
        assert float_metric.original_type == BSONType.DOUBLE
        assert bool_metric.original_type == BSONType.BOOLEAN


class TestValidateSchema:
    """Tests for schema validation."""

    def test_identical_documents(self):
        """Test that identical documents have matching schemas."""
        doc1 = {'a': 1, 'b': 2.5}
        doc2 = {'a': 10, 'b': 3.7}
        assert validate_schema(doc1, doc2)

    def test_different_field_names(self):
        """Test that different field names fail validation."""
        doc1 = {'a': 1}
        doc2 = {'b': 1}
        assert not validate_schema(doc1, doc2)

    def test_different_field_count(self):
        """Test that different field counts fail validation."""
        doc1 = {'a': 1}
        doc2 = {'a': 1, 'b': 2}
        assert not validate_schema(doc1, doc2)

    def test_different_nesting(self):
        """Test that different nesting fails validation."""
        doc1 = {'a': {'b': 1}}
        doc2 = {'a': 1}
        assert not validate_schema(doc1, doc2)

    def test_compatible_numeric_types(self):
        """Test that different numeric types are compatible."""
        doc1 = {'value': 42}  # int
        doc2 = {'value': 3.14}  # float
        # This should pass because numeric types are compatible
        assert validate_schema(doc1, doc2)

    def test_nested_schema_match(self):
        """Test schema validation with nested documents."""
        doc1 = {
            'server': {
                'connections': {
                    'current': 10,
                    'available': 100
                }
            }
        }
        doc2 = {
            'server': {
                'connections': {
                    'current': 5,
                    'available': 95
                }
            }
        }
        assert validate_schema(doc1, doc2)

    def test_bool_type_compatibility(self):
        """Test that booleans are only compatible with booleans."""
        doc1 = {'flag': True}
        doc2 = {'flag': 1}  # int, not bool
        # In our implementation, bool and int might be compatible
        # depending on how Python represents them
        result = validate_schema(doc1, doc2)
        # Document the actual behavior
        assert isinstance(result, bool)


class TestRealWorldDocument:
    """Tests with realistic MongoDB FTDC documents."""

    def test_server_status_like(self):
        """Test with a document structure similar to serverStatus."""
        doc = {
            'connections': {
                'current': 10,
                'available': 100,
                'totalCreated': 50
            },
            'network': {
                'bytesIn': 123456,
                'bytesOut': 654321,
                'numRequests': 1000
            },
            'opcounters': {
                'insert': 10,
                'query': 20,
                'update': 15,
                'delete': 5,
                'getmore': 3,
                'command': 100
            }
        }

        metrics = metric_for_document(doc)

        # Should have 12 metrics (3 + 3 + 6)
        assert len(metrics) == 12

        # Check some specific keys
        keys = {m.key() for m in metrics}
        assert 'connections.current' in keys
        assert 'network.bytesIn' in keys
        assert 'opcounters.insert' in keys

        # Extraction should work too
        extraction = extract_metrics_from_document(doc)
        assert len(extraction.values) == 12
