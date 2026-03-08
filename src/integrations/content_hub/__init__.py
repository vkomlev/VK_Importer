# Canonical write-path через content_hub_client (P2B). Локального SQL/DAO нет.

from .adapter import write_canonical_if_enabled

__all__ = ["write_canonical_if_enabled"]
