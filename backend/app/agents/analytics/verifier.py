"""Read-only SQL guard for analytics.

Multi-table SELECT (UNION ALL, JOIN across ``shipments`` and ``extracted_documents``) is
allowed. Any write/DDL keyword is rejected regardless of which table it names — cross-table
analytics must remain SELECT-only (NFR8 / Epic 5 alignment).
"""
import re

# Block write/DDL/admin keywords. ATTACH and PRAGMA are SQLite-specific risks
# (ATTACH can mount arbitrary external files; PRAGMA can alter DB settings).
_UNSAFE_RE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|PRAGMA|EXEC)\b",
    re.IGNORECASE,
)


class AnalyticsVerifier:
    def verify(self, sql: str) -> str:
        """Return sql unchanged if safe; raise ValueError if unsafe keywords found."""
        if _UNSAFE_RE.search(sql):
            raise ValueError(f"Unsafe SQL rejected: {sql[:200]}")
        return sql
