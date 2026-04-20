"""EditApplicator — apply a validated list of edit items to the database.

Entity names and field names are whitelisted before use in dynamic SQL to
prevent injection. All values are passed as bound parameters.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------

# Entities with a project_id column that should be auto-populated on create.
_HAS_PROJECT_ID: frozenset[str] = frozenset({
    "scenes",
    "days",
    "characters",
    "camera_units",
    "junior_artist_calls",
    "locations",
    "picture_vehicles",
    # Week 6 additions
    "props",
    "animals",
    "vfx_shots",
    "sfx_effects",
    "hmu_sessions",
    "wardrobe_looks",
    "art_builds",
    "permits",
})

# Per-entity allowed fields for patch / create operations.
ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "scenes": frozenset({
        "title", "dn", "location_id", "scene_number", "description",
        "page_eighths", "setups_est", "notes", "status", "sequence", "act",
    }),
    "day_scenes": frozenset({
        "day_id", "order_in_day", "actual_status",
    }),
    "scene_characters": frozenset({
        "scene_id", "character_id", "role",
    }),
    "days": frozenset({
        "shift_start", "shift_end", "notes", "banner_text",
        "primary_location_id", "kind", "shoot_day_number",
    }),
    "characters": frozenset({
        "display_name", "actor_name", "is_principal", "notes",
    }),
    "camera_day_uses": frozenset({
        "camera_unit_id", "day_id", "count",
    }),
    "junior_artist_calls": frozenset({
        "day_id", "count", "grade", "context", "vendor_name",
    }),
    "locations": frozenset({
        "name", "area", "kind", "notes",
    }),
    "picture_vehicles": frozenset({
        "name",
    }),
    "vehicle_day_uses": frozenset({
        "vehicle_id", "day_id", "count",
    }),
    # ---- Week 6: resource kinds ----
    "props": frozenset({
        "name", "category", "scenes_raw", "source", "source_vendor",
        "lead_days", "insurance_inr", "status", "notes",
    }),
    "animals": frozenset({
        "species", "count", "handler_name", "handler_contact",
        "vet_on_set", "vet_name", "vet_contact",
        "awbi_status", "awbi_number", "awbi_granted_at", "awbi_applied_at",
        "rest_window_hours", "insurance_inr", "welfare_notes",
    }),
    "vfx_shots": frozenset({
        "scene_id", "shot_number", "shot_type", "complexity",
        "plates_required", "description", "vendor_name", "budget_inr",
        "bid_status", "status", "notes",
    }),
    "sfx_effects": frozenset({
        "scene_id", "day_id", "effect_kind", "description",
        "coordinator", "coordinator_contact", "safety_plan_url",
        "insurance_rider", "medic_required", "rehearsal_date",
        "status", "notes",
    }),
    "hmu_sessions": frozenset({
        "character_id", "day_id", "look_id", "category",
        "apply_minutes", "remove_minutes", "hmu_call_time",
        "artist_lead", "artist_vendor", "continuity_ref", "notes",
    }),
    "wardrobe_looks": frozenset({
        "character_id", "look_id", "description", "era", "era_label",
        "scenes_raw", "multiples_count", "source", "source_vendor",
        "return_by", "continuity_key", "notes",
    }),
    "art_builds": frozenset({
        "name", "scenes_raw", "build_days_lead", "art_dir", "status", "notes",
    }),
    "permits": frozenset({
        "kind", "issuing_body", "reference_number",
        "applied_at", "granted_at", "expires_at",
        "status", "fee_inr", "related_location_id", "notes",
    }),
}


def _validate(entity: str, fields: dict) -> None:
    if entity not in ALLOWED_FIELDS:
        raise ValueError(f"Unsupported entity: {entity!r}")
    bad = set(fields) - ALLOWED_FIELDS[entity]
    if bad:
        raise ValueError(f"Invalid fields for {entity!r}: {bad}")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

async def apply(
    project_id: str,
    edit_items: list[dict],
    session: AsyncSession,
) -> None:
    """Apply a list of {op, entity, id?, fields?} dicts to the DB."""
    for item in edit_items:
        op: str = item["op"]
        entity: str = item["entity"]
        entity_id: str | None = item.get("id")
        fields: dict = item.get("fields") or {}

        _validate(entity, fields)

        if op == "patch":
            if not entity_id:
                raise ValueError(f"patch on {entity!r} requires 'id'")
            if not fields:
                continue
            set_clause = ", ".join(f'"{k}" = :{k}' for k in fields)
            await session.execute(
                sa.text(f'UPDATE {entity} SET {set_clause} WHERE id = :_eid'),
                {**fields, "_eid": entity_id},
            )

        elif op == "create":
            insert_fields: dict = {"id": str(uuid.uuid4()), **fields}
            if entity in _HAS_PROJECT_ID:
                insert_fields["project_id"] = project_id
            cols = ", ".join(f'"{k}"' for k in insert_fields)
            vals = ", ".join(f":{k}" for k in insert_fields)
            await session.execute(
                sa.text(f"INSERT INTO {entity} ({cols}) VALUES ({vals})"),
                insert_fields,
            )

        elif op == "delete":
            if not entity_id:
                raise ValueError(f"delete on {entity!r} requires 'id'")
            await session.execute(
                sa.text(f"DELETE FROM {entity} WHERE id = :_eid"),
                {"_eid": entity_id},
            )

        else:
            raise ValueError(f"Unknown op: {op!r}")
