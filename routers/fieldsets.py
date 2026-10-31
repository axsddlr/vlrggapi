"""
`include=` fieldset support for responses that mirror a whole scraped page.

A few V2 endpoints return one fat object per scrape (per-map performance and
economy matrices, the full round replay, an event's standings). Callers that
need two fields still download all of them, so those routes accept an
``include`` allowlist.

Trimming deliberately happens here, in the router, *after* the handler
returns: the scrapers cache the untrimmed payload under a key that knows
nothing about ``include``, so the cache must only ever see the full result and
``include`` must never become part of a cache key. Both functions are pure and
build new dicts; a cached payload is never mutated in place.
"""
from collections.abc import Collection

from fastapi import HTTPException


def parse_include(
    raw: str | None, valid: Collection[str]
) -> frozenset[str] | None:
    """Turn an ``include`` query value into an allowlist, or ``None``.

    ``None`` means "do not narrow": the parameter is absent, empty, or only
    whitespace/commas. Otherwise the value is split on commas, each item is
    stripped and lowercased, empty items are dropped, and every remaining name
    must be one of ``valid`` — an unknown name raises 400 naming it and listing
    the accepted ones.

    Args:
        raw: The raw query parameter value.
        valid: Accepted field names for the endpoint (including any IDs the
            endpoint always keeps, so naming them explicitly is not an error).
    """
    if raw is None:
        return None

    names = [part.strip().lower() for part in raw.split(",")]
    names = [name for name in names if name]
    if not names:
        return None

    accepted = frozenset(valid)
    unknown = sorted(set(names) - accepted)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid include '{unknown[0]}'. "
                f"Valid fields: {', '.join(sorted(accepted))}"
            ),
        )

    return frozenset(names)


def apply_include(
    payload: dict,
    keep: frozenset[str] | None,
    always_keep: Collection[str] = (),
) -> dict:
    """Return ``payload`` with ``data.segments`` narrowed to ``keep``.

    ``segments`` is a list of dicts for match detail/logs and a single dict for
    event detail; both shapes are handled by dropping the keys the caller did
    not ask for. Keys in ``always_keep`` survive regardless of ``keep``.

    Anything unexpected — no payload/``data`` dict, a missing ``segments``, or
    a ``segments`` value that is neither a list nor a dict — is returned
    unchanged instead of raising, because this runs after an expensive scrape.
    """
    if keep is None or not isinstance(payload, dict):
        return payload

    data = payload.get("data")
    if not isinstance(data, dict) or "segments" not in data:
        return payload

    segments = data["segments"]
    required = frozenset(always_keep) | keep

    if isinstance(segments, list):
        narrowed = [
            _keep_fields(segment, required) if isinstance(segment, dict) else segment
            for segment in segments
        ]
    elif isinstance(segments, dict):
        narrowed = _keep_fields(segments, required)
    else:
        return payload

    return {**payload, "data": {**data, "segments": narrowed}}


def _keep_fields(mapping: dict, keep: Collection[str]) -> dict:
    """Copy ``mapping`` keeping only ``keep`` keys, in their original order."""
    return {key: value for key, value in mapping.items() if key in keep}
