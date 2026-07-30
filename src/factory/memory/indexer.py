"""
Repository Indexer.

Indexes the codebase into the memory server for semantic search.
Walks configured directories, chunks files, extracts symbols,
and stores everything in the memory backend.

Indexing is incremental: only re-indexes files that have changed
since the last indexing run (based on checksum comparison).

Usage:
    indexer = RepositoryIndexer(client, config)
    status = indexer.index_repository(repo_root)
    status = indexer.index_file(file_path)
    status = indexer.get_status()
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .client import MemoryClient, ServerUnavailableError
from .types import Chunk, FileInfo, IndexStatus, Language


class IndexerConfig:
    """Configuration for the repository indexer."""

    def __init__(
        self,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        include_extensions: list[str] | None = None,
        chunk_size: int = 1500,
        chunk_overlap: int = 200,
        max_file_size_kb: int = 100,
        index_symbols: bool = True,
        index_dependencies: bool = True,
    ):
        self.include_paths = include_paths or [
            "firmware/app/", "firmware/middleware/", "firmware/drivers/",
            "firmware/core/", "firmware/tests/",
        ]
        self.exclude_paths = exclude_paths or [
            ".git/", ".pio/", ".venv/", "node_modules/", "__pycache__/",
        ]
        self.include_extensions = include_extensions or [
            ".cpp", ".h", ".c", ".py", ".ts", ".tsx", ".md",
        ]
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_file_size_kb = max_file_size_kb
        self.index_symbols = index_symbols
        self.index_dependencies = index_dependencies


class RepositoryIndexer:
    """
    Indexes repository files into codebase memory.

    Responsibilities:
    - Walk directory tree respecting include/exclude rules
    - Detect file changes via checksum comparison
    - Chunk files for embedding
    - Store chunks in memory server
    - Track indexing status
    """

    def __init__(self, client: MemoryClient, config: IndexerConfig | None = None):
        self.client = client
        self.config = config or IndexerConfig()
        self._status = IndexStatus()
        self._checksums: dict[str, str] = {}

    def index_repository(self, repo_root: str | Path) -> IndexStatus:
        """
        Index the entire repository (incremental).

        Walks all configured paths, skips unchanged files,
        chunks and indexes new/modified files.

        Args:
            repo_root: Absolute path to repository root.

        Returns:
            IndexStatus with counts and timing.
        """
        repo_root = Path(repo_root).resolve()
        start_time = time.time()

        files_to_index = self._discover_files(repo_root)
        self._status.total_files = len(files_to_index)

        for file_info in files_to_index:
            if self._has_changed(file_info):
                self._index_file(repo_root, file_info)
                self._status.indexed_files += 1

        self._status.last_indexed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._status.index_duration_seconds = time.time() - start_time

        return self._status

    def index_file(self, repo_root: str | Path, file_path: str) -> bool:
        """
        Index a single file.

        Args:
            repo_root: Repository root path.
            file_path: Relative file path.

        Returns:
            True if file was indexed successfully.
        """
        repo_root = Path(repo_root).resolve()
        full_path = repo_root / file_path

        if not full_path.exists():
            return False

        file_info = self._build_file_info(repo_root, full_path)
        return self._index_file(repo_root, file_info)

    def get_status(self) -> IndexStatus:
        """Return current index status."""
        return self._status

    # --- Internal Methods ---

    def _discover_files(self, repo_root: Path) -> list[FileInfo]:
        """Walk directory tree and discover indexable files."""
        files: list[FileInfo] = []

        for include_path in self.config.include_paths:
            search_root = repo_root / include_path
            if not search_root.exists():
                continue

            for file_path in search_root.rglob("*"):
                if not file_path.is_file():
                    continue
                if self._should_exclude(repo_root, file_path):
                    continue
                if file_path.suffix not in self.config.include_extensions:
                    continue
                if file_path.stat().st_size > self.config.max_file_size_kb * 1024:
                    continue

                files.append(self._build_file_info(repo_root, file_path))

        return files

    def _build_file_info(self, repo_root: Path, file_path: Path) -> FileInfo:
        """Build FileInfo for a discovered file."""
        relative = str(file_path.relative_to(repo_root))
        stat = file_path.stat()

        return FileInfo(
            path=relative,
            language=self._detect_language(file_path),
            size_bytes=stat.st_size,
            line_count=sum(1 for _ in open(file_path, errors="ignore")),
            last_modified=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            checksum=self._compute_checksum(file_path),
        )

    def _should_exclude(self, repo_root: Path, file_path: Path) -> bool:
        """Check if file matches any exclude patterns."""
        relative = str(file_path.relative_to(repo_root))
        for exclude in self.config.exclude_paths:
            if exclude in relative:
                return True
        return False

    def _has_changed(self, file_info: FileInfo) -> bool:
        """Check if file has changed since last index."""
        previous = self._checksums.get(file_info.path)
        if previous is None:
            return True  # Never indexed
        return previous != file_info.checksum

    def _index_file(self, repo_root: Path, file_info: FileInfo) -> bool:
        """Chunk and index a single file."""
        full_path = repo_root / file_info.path
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return False

        # Chunk the file
        chunks = self._chunk_content(content, file_info)
        self._status.total_chunks += len(chunks)

        # Store chunks in memory
        for chunk in chunks:
            try:
                self.client.call_tool("store_chunk", {
                    "file_path": file_info.path,
                    "content": chunk.content,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": file_info.language.value,
                })
            except (ServerUnavailableError, Exception):
                return False

        # Update checksum cache
        self._checksums[file_info.path] = file_info.checksum

        # Track language stats
        lang = file_info.language.value
        self._status.languages[lang] = self._status.languages.get(lang, 0) + 1

        return True

    def _chunk_content(self, content: str, file_info: FileInfo) -> list[Chunk]:
        """Split file content into overlapping chunks."""
        lines = content.splitlines()
        chunks: list[Chunk] = []

        # Simple line-based chunking
        chunk_lines = self.config.chunk_size // 10  # ~10 chars per line estimate
        overlap_lines = self.config.chunk_overlap // 10

        i = 0
        while i < len(lines):
            end = min(i + chunk_lines, len(lines))
            chunk_content = "\n".join(lines[i:end])

            chunks.append(Chunk(
                file_path=file_info.path,
                content=chunk_content,
                start_line=i + 1,
                end_line=end,
                language=file_info.language,
            ))

            i += chunk_lines - overlap_lines

        return chunks

    @staticmethod
    def _compute_checksum(file_path: Path) -> str:
        """Compute MD5 checksum for change detection."""
        h = hashlib.md5()
        h.update(file_path.read_bytes())
        return h.hexdigest()

    @staticmethod
    def _detect_language(file_path: Path) -> Language:
        """Detect language from file extension."""
        ext_map = {
            ".cpp": Language.CPP, ".h": Language.CPP, ".c": Language.CPP,
            ".py": Language.PYTHON,
            ".ts": Language.TYPESCRIPT, ".tsx": Language.TYPESCRIPT,
            ".md": Language.MARKDOWN,
            ".yaml": Language.YAML, ".yml": Language.YAML,
        }
        return ext_map.get(file_path.suffix, Language.CPP)
