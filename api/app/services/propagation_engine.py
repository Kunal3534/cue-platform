"""PropagationEngine — preview edits before committing.

Stores per-field audit rows in `edits` and a preview summary in
`propagation_previews`. The commit endpoint reads back the original
edit intent from preview.diff["request"] and delegates to EditApplicator.

_build_diff is split into three explicit stages so Week 5 FlagDetector
can plug in without restructuring:
  _compute_impacts()     — which views to regenerate (done)
  _detect_breaks()       — hard constraints that block commit (stub, Week 5)
  _collect_side_effects() — notifications / re-sends triggered (stub, Week 5)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .propagation_dag import views_for_edits
from ..models import Edit, PropagationPreview


class PropagationEngine:

    # ----------------------------------------------------------------
    # Stage 1 — view impacts (always runs)
    # ----------------------------------------------------------------

    @staticmethod
    def _compute_impacts(raw_edits: list[dict]) -> list[dict]:
        affected = views_for_edits(raw_edits)
        return [
            {
                "view": v,
                "rows_changed": -1,
                "detail": "View will be fully regenerated.",
            }
            for v in affected
        ]

    # ----------------------------------------------------------------
    # Stage 2 — hard breaks (stub; Week 5 FlagDetector plugs in here)
    # ----------------------------------------------------------------

    @staticmethod
    def _detect_breaks(raw_edits: list[dict]) -> list[dict]:
        # TODO Week 5 — FlagDetector will add checks for:
        #   - cast availability: character already W on destination day
        #   - permit lead time: location change < lead_time_days before shoot
        #   - weather conflicts: outdoor location on a weather-hold day
        #   - drone permit block: drone unit on day without a valid permit
        return []

    # ----------------------------------------------------------------
    # Stage 3 — side effects (stub; Week 5 plugs in here)
    # ----------------------------------------------------------------

    @staticmethod
    def _collect_side_effects(raw_edits: list[dict]) -> list[dict]:
        # TODO Week 5 — will generate:
        #   - re_email when jr_count changes above vendor notification threshold
        #   - flag_raised when schedule change conflicts with a vendor booking
        #   - call_sheet_stale when day content changes after sheet is 'sent'
        return []

    # ----------------------------------------------------------------
    # Assemble diff
    # ----------------------------------------------------------------

    @staticmethod
    def _build_diff(raw_edits: list[dict]) -> dict:
        impacts = PropagationEngine._compute_impacts(raw_edits)
        return {
            "views_affected": sorted({imp["view"] for imp in impacts}),
            "impacts": impacts,
            "side_effects": PropagationEngine._collect_side_effects(raw_edits),
            "breaks": PropagationEngine._detect_breaks(raw_edits),
        }

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    @staticmethod
    async def preview(
        project_id: str,
        user_id: str,
        raw_edits: list[dict],
        session: AsyncSession,
    ) -> PropagationPreview:
        batch_id = str(uuid.uuid4())
        diff = PropagationEngine._build_diff(raw_edits)

        # Audit rows (one per field change; old_value left null for v1)
        for item in raw_edits:
            op = item["op"]
            entity = item["entity"]
            entity_id = item.get("id") or str(uuid.uuid4())
            fields: dict = item.get("fields") or {}

            if op == "delete":
                session.add(Edit(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    user_id=user_id,
                    batch_id=batch_id,
                    entity_table=entity,
                    entity_id=entity_id,
                    field="__delete__",
                    old_value=None,
                    new_value=None,
                ))
            else:
                for field, value in fields.items():
                    session.add(Edit(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        user_id=user_id,
                        batch_id=batch_id,
                        entity_table=entity,
                        entity_id=entity_id,
                        field=field,
                        old_value=None,
                        new_value={"v": value},
                    ))

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        preview = PropagationPreview(
            id=str(uuid.uuid4()),
            project_id=project_id,
            batch_id=batch_id,
            user_id=user_id,
            diff={**diff, "request": {"edits": raw_edits}},
            expires_at=expires_at,
        )
        session.add(preview)
        await session.commit()
        await session.refresh(preview)
        return preview

    @staticmethod
    async def get_preview(
        batch_id: str,
        session: AsyncSession,
    ) -> PropagationPreview | None:
        result = await session.execute(
            sa.select(PropagationPreview).where(PropagationPreview.batch_id == batch_id)
        )
        return result.scalar_one_or_none()
