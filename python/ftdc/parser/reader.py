"""FTDC file reader with iterators.

Provides high-level interface for reading MongoDB FTDC files.
Supports lazy loading, filtering, and multiple iteration modes.
"""

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, Optional

from bson import decode as bson_decode

from .chunk import parse_chunk
from .types import Chunk, FTDCDocument, FTDCType


class FTDCReadError(Exception):
    """Raised when FTDC file reading fails."""
    pass


class FTDCReader:
    """Reader for MongoDB FTDC files.

    FTDC files are sequences of BSON documents with different types:
    - Type 0: Metadata (process/system info)
    - Type 1: Metric chunks (compressed time-series data)
    - Type 2: Periodic metadata (deltas)

    Example:
        >>> reader = FTDCReader('metrics.2025-11-13T17-15-32Z-00000')
        >>> for chunk in reader.iter_chunks():
        ...     print(f"Chunk with {chunk.num_metrics()} metrics, {chunk.size()} samples")
        >>>
        >>> # Or iterate all samples
        >>> for sample in reader.iter_samples():
        ...     print(sample['serverStatus']['connections']['current'])
    """

    def __init__(self, file_path: str | Path):
        """Initialize reader for an FTDC file.

        Args:
            file_path: Path to FTDC file

        Raises:
            FTDCReadError: If file doesn't exist or can't be opened
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FTDCReadError(f"File not found: {self.file_path}")

        self._file_size = self.file_path.stat().st_size
        self._metadata_docs = []

    def __repr__(self) -> str:
        return f"FTDCReader('{self.file_path}', size={self._file_size:,} bytes)"

    def iter_documents(self) -> Iterator[FTDCDocument]:
        """Iterate over all BSON documents in the file.

        This is the lowest-level iterator. Documents are returned as-is
        without parsing metric chunks.

        Yields:
            FTDCDocument objects

        Example:
            >>> reader = FTDCReader('metrics.ftdc')
            >>> for doc in reader.iter_documents():
            ...     print(f"Type {doc.doc_type}, ID: {doc.doc_id}")
        """
        with open(self.file_path, 'rb') as f:
            while True:
                doc = self._read_document(f)
                if doc is None:
                    break
                yield doc

    def iter_chunks(self) -> Iterator[Chunk]:
        """Iterate over decompressed metric chunks.

        Automatically parses type=1 documents into Chunk objects.
        Skips metadata documents.

        Yields:
            Chunk objects with decompressed metrics

        Example:
            >>> for chunk in reader.iter_chunks():
            ...     print(f"{chunk.num_metrics()} metrics")
            ...     for metric in chunk.metrics[:5]:
            ...         print(f"  {metric.key()}")
        """
        for doc in self.iter_documents():
            if doc.doc_type == FTDCType.METRIC_CHUNK:
                # Parse the compressed chunk
                binary_data = doc.data.get('data')
                if binary_data:
                    try:
                        chunk = parse_chunk(binary_data)

                        # Set chunk_id, ensuring it's timezone-aware (UTC)
                        # FTDC timestamps are always UTC
                        if doc.doc_id and isinstance(doc.doc_id, datetime):
                            if doc.doc_id.tzinfo is None:
                                chunk.chunk_id = doc.doc_id.replace(tzinfo=timezone.utc)
                            else:
                                chunk.chunk_id = doc.doc_id
                        else:
                            chunk.chunk_id = doc.doc_id

                        # Attach metadata if we have it
                        if self._metadata_docs:
                            chunk.metadata = self._metadata_docs[-1]

                        yield chunk
                    except Exception as e:
                        raise FTDCReadError(f"Failed to parse chunk at {doc.doc_id}: {e}")

            elif doc.doc_type == FTDCType.METADATA:
                # Store metadata for attaching to chunks
                metadata_content = doc.data.get('doc', {})
                self._metadata_docs.append(metadata_content)

    def iter_samples(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Iterator[dict]:
        """Iterate over all samples across all chunks.

        Reconstructs full BSON documents from metric chunks.
        Optionally filters by time range.

        Args:
            start_time: Optional start time (inclusive)
            end_time: Optional end time (inclusive)

        Yields:
            Reconstructed BSON documents (one per sample)

        Example:
            >>> from datetime import datetime
            >>> start = datetime(2025, 11, 13, 17, 0, 0)
            >>> for sample in reader.iter_samples(start_time=start):
            ...     print(sample['serverStatus']['uptime'])
        """
        from .chunk import reconstruct_document

        for chunk in self.iter_chunks():
            # Check time range if specified
            if start_time and chunk.chunk_id and chunk.chunk_id < start_time:
                continue
            if end_time and chunk.chunk_id and chunk.chunk_id > end_time:
                break

            # Reconstruct each sample in the chunk
            for sample_idx in range(chunk.size()):
                doc = reconstruct_document(chunk.reference, chunk.metrics, sample_idx)
                yield doc

    def get_metadata(self) -> list[dict]:
        """Get all metadata documents from the file.

        Returns:
            List of metadata documents (type=0)

        Example:
            >>> metadata = reader.get_metadata()
            >>> if metadata:
            ...     print(metadata[0]['start'])  # Start time
        """
        metadata = []
        for doc in self.iter_documents():
            if doc.doc_type == FTDCType.METADATA:
                metadata.append(doc.data.get('doc', {}))
        return metadata

    def get_time_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        """Get the time range covered by this FTDC file.

        Returns:
            Tuple of (start_time, end_time) or (None, None) if no chunks

        Example:
            >>> start, end = reader.get_time_range()
            >>> print(f"Data from {start} to {end}")
        """
        first_time = None
        last_time = None

        for doc in self.iter_documents():
            if doc.doc_type == FTDCType.METRIC_CHUNK:
                if first_time is None:
                    first_time = doc.doc_id
                last_time = doc.doc_id

        return first_time, last_time

    def count_chunks(self) -> int:
        """Count the number of metric chunks in the file.

        Returns:
            Number of type=1 documents
        """
        count = 0
        for doc in self.iter_documents():
            if doc.doc_type == FTDCType.METRIC_CHUNK:
                count += 1
        return count

    def _read_document(self, f: BinaryIO) -> Optional[FTDCDocument]:
        """Read one BSON document from file.

        Args:
            f: File handle

        Returns:
            FTDCDocument or None if EOF

        Raises:
            FTDCReadError: If document is malformed
        """
        # Read document size (first 4 bytes)
        size_bytes = f.read(4)
        if not size_bytes:
            return None  # EOF

        if len(size_bytes) < 4:
            raise FTDCReadError("Truncated document: incomplete size field")

        doc_size = struct.unpack('<I', size_bytes)[0]

        # Validate size
        if doc_size < 5:  # Minimum BSON doc is 5 bytes
            raise FTDCReadError(f"Invalid document size: {doc_size}")

        if doc_size > 100_000_000:  # 100MB sanity check
            raise FTDCReadError(f"Document too large: {doc_size:,} bytes")

        # Read rest of document
        rest = f.read(doc_size - 4)
        if len(rest) != doc_size - 4:
            raise FTDCReadError(
                f"Truncated document: expected {doc_size} bytes, got {len(rest) + 4}"
            )

        # Decode BSON
        doc_bytes = size_bytes + rest
        try:
            doc = bson_decode(doc_bytes)
        except Exception as e:
            raise FTDCReadError(f"Failed to decode BSON: {e}")

        # Parse document fields
        doc_id = doc.get('_id')
        doc_type_val = doc.get('type')

        # Validate type
        if doc_type_val is None:
            raise FTDCReadError("Document missing 'type' field")

        try:
            doc_type = FTDCType(doc_type_val)
        except ValueError:
            raise FTDCReadError(f"Unknown document type: {doc_type_val}")

        return FTDCDocument(
            doc_id=doc_id,
            doc_type=doc_type,
            data=doc,
        )


def read_ftdc_file(file_path: str | Path) -> list[Chunk]:
    """Convenience function to read all chunks from an FTDC file.

    Args:
        file_path: Path to FTDC file

    Returns:
        List of all chunks in the file

    Example:
        >>> chunks = read_ftdc_file('metrics.ftdc')
        >>> print(f"Read {len(chunks)} chunks")
    """
    reader = FTDCReader(file_path)
    return list(reader.iter_chunks())


def read_ftdc_samples(
    file_path: str | Path,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[dict]:
    """Convenience function to read all samples from an FTDC file.

    Args:
        file_path: Path to FTDC file
        start_time: Optional start time filter
        end_time: Optional end time filter

    Returns:
        List of reconstructed BSON documents

    Example:
        >>> samples = read_ftdc_samples('metrics.ftdc')
        >>> print(f"Read {len(samples)} samples")
        >>> print(samples[0]['serverStatus']['uptime'])
    """
    reader = FTDCReader(file_path)
    return list(reader.iter_samples(start_time=start_time, end_time=end_time))
