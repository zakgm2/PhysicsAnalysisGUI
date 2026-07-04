"""
marker_labels.py
-----------------
Shared display-text helpers for markers: store rename overrides (the raw
TDT store code, e.g. 'PP1_' or 'L1P', stays the internal id used for
grouping/filtering everywhere — only how it's *shown* changes) and the
high/low phase superscript. Used by both plot engines, the marker
dialogs, and the Event Intervals table so they all agree on what a
marker's name and store currently look like.
"""

_PHASE_SUFFIX = {'high': '¹', 'low': '⁰'}  # superscript 1 / 0


def store_display_name(ctx, store_id):
    """The name shown for a store id — the renamed name if one's been set
    via 'Rename all', otherwise the raw store id unchanged."""
    if store_id is None:
        return store_id
    return ctx.store_labels.get(store_id, store_id)


def marker_display_label(ctx, m):
    """Full text to draw for a marker: its store's renamed display name,
    plus a superscript ¹/⁰ if it's a high/low phase marker.

    Only markers with a 'phase' key get the store-name substitution —
    those are exactly the auto-generated onset/offset markers whose label
    IS the store name by convention (see processing_TDT.get_event_markers).
    Everything else (Note markers, whose label is the actual note text
    like 'Clap' even though they share store == 'Note'; manually-placed
    markers) keeps its own label untouched — renaming a store must not
    clobber a marker whose label was never derived from that store name."""
    if m.get('phase') is not None:
        label = store_display_name(ctx, m['store'])
    else:
        label = m['label']
    return f"{label}{_PHASE_SUFFIX.get(m.get('phase'), '')}"
