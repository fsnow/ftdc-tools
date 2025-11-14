"""Data structures for FTDC parsing."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional

# We don't actually need to import BSON types here since we define our own


class FTDCType(IntEnum):
    """Type of FTDC document.

    These values are persisted in BSON documents as the 'type' field.
    """
    # Metadata document: header + array of BSON documents
    METADATA = 0

    # Metric chunk: header + compressed metric chunk
    METRIC_CHUNK = 1

    # Periodic metadata: header + counter + delta document
    PERIODIC_METADATA = 2


@dataclass
class Metric:
    """Represents a single metric time series from an FTDC chunk.

    A metric is extracted from a BSON document via depth-first traversal.
    For nested documents, the path is preserved to allow reconstruction.
    """
    # Path to the field in the source document (e.g., ['parent', 'child'])
    parent_path: list[str] = field(default_factory=list)

    # Field name of this metric (not including parent path)
    key_name: str = ""

    # Time series values for this metric across all samples
    # After delta decoding, these are absolute values
    values: list[int] = field(default_factory=list)

    # Original BSON type (for restoring proper type during reconstruction)
    original_type: Optional[int] = None

    def key(self) -> str:
        """Get the fully-qualified dotted key for this metric.

        Returns:
            Dot-separated path like 'parent.child.fieldName'

        Example:
            >>> m = Metric(parent_path=['serverStatus', 'connections'], key_name='current')
            >>> m.key()
            'serverStatus.connections.current'
        """
        if self.parent_path:
            return '.'.join(self.parent_path + [self.key_name])
        return self.key_name


@dataclass
class Chunk:
    """Represents a decompressed FTDC metric chunk.

    A chunk contains:
    - Reference document (first sample, defines schema)
    - Array of metrics (one per numeric field in reference doc)
    - Metadata (optional, from type=0 documents)
    """
    # List of metrics extracted from the chunk
    metrics: list[Metric] = field(default_factory=list)

    # Number of sample points in this chunk
    # Total samples = npoints (includes reference doc + deltas)
    npoints: int = 0

    # Timestamp ID of this chunk
    chunk_id: Optional[datetime] = None

    # Metadata document (if any)
    metadata: Optional[dict] = None

    # Reference BSON document (first sample)
    reference: Optional[dict] = None

    def size(self) -> int:
        """Get the number of sample points in this chunk.

        Returns:
            Number of samples (reference + deltas)
        """
        return self.npoints

    def num_metrics(self) -> int:
        """Get the number of metrics in this chunk.

        Returns:
            Number of metrics extracted from reference document
        """
        return len(self.metrics)


@dataclass
class FTDCDocument:
    """Wrapper for a BSON document read from an FTDC file."""
    # The _id field (timestamp)
    doc_id: datetime

    # Document type (0=metadata, 1=metrics, 2=periodic metadata)
    doc_type: FTDCType

    # The document data (varies by type)
    # - Type 0: 'doc' field contains metadata
    # - Type 1: 'data' field contains compressed binary chunk
    # - Type 2: 'doc' field contains delta, 'count' field has counter
    data: dict


@dataclass
class MetricsExtraction:
    """Result of extracting metrics from a BSON document."""
    # Extracted metric values (as int64)
    values: list[int] = field(default_factory=list)

    # Original BSON types for each value
    types: list[int] = field(default_factory=list)

    # Timestamp found in document (if any)
    timestamp: Optional[datetime] = None

    def num_metrics(self) -> int:
        """Get the number of extracted metrics."""
        return len(self.values)
