"""
Source contract — every source module implements this Protocol.
New sources slot in by matching this interface; no other changes needed.
"""

from typing import Protocol, TypedDict, runtime_checkable


class Candidate(TypedDict):
    url: str
    source: str   # source module name, e.g. "edgar", "nse", "web_search"
    note: str     # human-readable reason this URL was chosen (for logs)


@runtime_checkable
class Source(Protocol):
    name: str

    def supports(self, intent: dict) -> bool:
        """Return True if this source can handle the given intent."""
        ...

    def find_candidates(self, intent: dict) -> list[Candidate]:
        """Return ordered list of candidate URLs for the given intent.

        Must never fabricate URLs — all candidates must come from
        authoritative API responses or verified page scrapes.
        """
        ...
