"""Rule: cast_holds — character is scheduled W on a day where a hold was requested.

In v1 there is no explicit 'hold' field on characters per day, so we infer from
the DOOD: a character who appears both W (working) and was already marked H in
the DOOD computation is logically impossible.  We flag any shoot day where a
character has both statuses simultaneously (shouldn't happen in practice but
can arise from bad data or concurrent edits).

More practically: flag any principal character whose working-day window (first W
to last W) spans more than 30 consecutive calendar days — indicative of a hold
cost liability that has not been acknowledged.
"""
from __future__ import annotations

from ..project_graph import ProjectGraph


def detect(graph: ProjectGraph) -> list[dict]:
    flags: list[dict] = []

    for char in graph.characters:
        if not char.is_principal:
            continue
        dood = graph.character_dood.get(char.id, {})
        w_days = [graph.shoot_days[i] for i, sdn in enumerate(
            [d.shoot_day_number for d in graph.shoot_days if d.shoot_day_number]
        ) if dood.get(sdn) == "W"]

        if len(w_days) < 2:
            continue

        dates = sorted(d.date for d in w_days)
        span = (dates[-1] - dates[0]).days
        if span > 30:
            flags.append({
                "kind": "cast_hold",
                "severity": "warning",
                "title": f"{char.display_name}: working span {span} days",
                "description": (
                    f"{char.display_name} ({char.actor_name or 'no actor assigned'}) "
                    f"works across {span} calendar days "
                    f"({dates[0].strftime('%-d %b')} – {dates[-1].strftime('%-d %b')}). "
                    "Hold fees may apply for non-working days in this window."
                ),
                "related_character_id": char.id,
            })
    return flags
