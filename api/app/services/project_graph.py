"""ProjectGraph — in-memory snapshot of all project data needed by reports.

Load once async, then pass to synchronous xlsx/PDF renderers.
Factory: `await ProjectGraph.load(project_id, scenario_id, session)`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProjectMeta:
    id: str
    title: str
    window: str | None
    status: str
    start_date: date | None
    end_date: date | None
    live_scenario_id: str | None


@dataclass
class SceneData:
    id: str
    scene_number: str
    title: str | None
    description: str | None
    dn: str
    page_eighths: int | None
    setups_est: int
    location_name: str | None
    location_kind: str | None
    characters: list[str] = field(default_factory=list)  # canonical names


@dataclass
class DayData:
    id: str
    date: date
    kind: str
    shoot_day_number: int | None
    shift_start: time | None
    shift_end: time | None
    location_id: str | None
    location_name: str | None
    location_area: str | None
    location_kind: str | None
    banner_text: str | None
    notes: str | None
    scenes: list[SceneData] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)       # union of scene characters
    jr_count: int = 0
    camera_uses: list[tuple[str, str, int]] = field(default_factory=list)  # (code, kind, count)
    vehicle_names: list[str] = field(default_factory=list)


@dataclass
class CharacterData:
    id: str
    canonical_name: str
    display_name: str
    actor_name: str | None
    is_principal: bool


@dataclass
class CameraUnitData:
    id: str
    unit_code: str
    kind: str
    description: str | None
    rental_vendor: str | None
    operator_name: str | None


@dataclass
class VehicleData:
    id: str
    name: str
    spec: str | None
    source: str | None
    source_vendor: str | None
    day_ids: list[str] = field(default_factory=list)


@dataclass
class JrCallData:
    day_id: str
    day_date: date
    shoot_day_number: int | None
    count: int
    grade: str
    context: str | None
    vendor_name: str | None


@dataclass
class PropData:
    id: str
    name: str
    category: str
    source: str | None
    source_vendor: str | None
    lead_days: int | None
    status: str


@dataclass
class ScenePropLink:
    scene_number: str
    prop_name: str
    prop_category: str
    role: str


@dataclass
class AnimalData:
    id: str
    species: str
    count: int
    handler_name: str | None
    vet_on_set: bool
    awbi_status: str | None
    day_ids: list[str] = field(default_factory=list)


@dataclass
class VfxShotData:
    id: str
    shot_number: str
    shot_type: str
    complexity: str
    plates_required: bool
    vendor: str | None
    bid_status: str | None
    status: str
    scene_number: str | None


@dataclass
class SfxEffectData:
    id: str
    scene_number: str | None
    day_id: str | None
    effect_kind: str
    coordinator: str | None
    status: str
    medic_required: bool
    permits_required: Any


@dataclass
class HmuSessionData:
    id: str
    character_name: str
    day_date: date | None
    look_id: str | None
    category: str
    apply_minutes: int | None
    artist_vendor: str | None


@dataclass
class WardrobeLookData:
    id: str
    character_name: str
    look_id: str | None
    era: str
    description: str | None
    source: str | None
    source_vendor: str | None
    multiples_count: int


# ---------------------------------------------------------------------------
# ProjectGraph
# ---------------------------------------------------------------------------

class ProjectGraph:
    def __init__(self, project_id: str, scenario_id: str | None = None) -> None:
        self.project_id = project_id
        self.scenario_id = scenario_id

        self.project: ProjectMeta
        self.days: list[DayData] = []
        self.shoot_days: list[DayData] = []
        self.characters: list[CharacterData] = []
        self.character_dood: dict[str, dict[int, str]] = {}  # char_id → {sdn → status}
        self.camera_units: list[CameraUnitData] = []
        self.vehicles: list[VehicleData] = []
        self.jr_calls: list[JrCallData] = []
        self.props: list[PropData] = []
        self.scene_props: list[ScenePropLink] = []
        self.animals: list[AnimalData] = []
        self.vfx_shots: list[VfxShotData] = []
        self.sfx_effects: list[SfxEffectData] = []
        self.hmu_sessions: list[HmuSessionData] = []
        self.wardrobe_looks: list[WardrobeLookData] = []

    @classmethod
    async def load(
        cls,
        project_id: str,
        scenario_id: str | None,
        session: AsyncSession,
    ) -> "ProjectGraph":
        pg = cls(project_id, scenario_id)
        await pg._load(session)
        return pg

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    async def _load(self, s: AsyncSession) -> None:
        await self._load_project(s)
        await self._load_days(s)
        await self._load_characters(s)
        await self._load_camera_units(s)
        await self._load_vehicles(s)
        await self._load_jr_calls(s)
        await self._load_props(s)
        await self._load_animals(s)
        await self._load_vfx(s)
        await self._load_sfx(s)
        await self._load_hmu(s)
        await self._load_wardrobe(s)
        self._compute_dood()

    async def _load_project(self, s: AsyncSession) -> None:
        row = (await s.execute(
            sa.text(
                "SELECT id, title, \"window\", status, start_date, end_date, live_scenario_id "
                "FROM projects WHERE id = :pid"
            ),
            {"pid": self.project_id},
        )).first()
        self.project = ProjectMeta(
            id=row.id, title=row.title, window=row.window,
            status=row.status, start_date=row.start_date,
            end_date=row.end_date, live_scenario_id=row.live_scenario_id,
        )

    async def _load_days(self, s: AsyncSession) -> None:
        day_rows = (await s.execute(
            sa.text("""
                SELECT d.id, d.shoot_day_number, d.date, d.kind,
                       d.shift_start, d.shift_end, d.primary_location_id,
                       d.banner_text, d.notes,
                       l.name AS loc_name, l.area AS loc_area, l.kind AS loc_kind
                FROM days d
                LEFT JOIN locations l ON l.id = d.primary_location_id
                WHERE d.project_id = :pid ORDER BY d.date
            """),
            {"pid": self.project_id},
        )).fetchall()

        scene_rows = (await s.execute(
            sa.text("""
                SELECT ds.day_id, ds.order_in_day,
                       s.id, s.scene_number, s.title, s.description,
                       s.dn, s.page_eighths, s.setups_est, s.location_id,
                       l.name AS loc_name, l.kind AS loc_kind
                FROM day_scenes ds
                JOIN scenes s ON s.id = ds.scene_id
                JOIN days d   ON d.id = ds.day_id
                LEFT JOIN locations l ON l.id = s.location_id
                WHERE d.project_id = :pid
                ORDER BY ds.day_id, ds.order_in_day
            """),
            {"pid": self.project_id},
        )).fetchall()

        char_rows = (await s.execute(
            sa.text("""
                SELECT sc.scene_id, c.canonical_name
                FROM scene_characters sc
                JOIN characters c ON c.id = sc.character_id
                WHERE c.project_id = :pid
            """),
            {"pid": self.project_id},
        )).fetchall()

        cam_rows = (await s.execute(
            sa.text("""
                SELECT cdu.day_id, cu.unit_code, cu.kind, cdu.count
                FROM camera_day_uses cdu
                JOIN camera_units cu ON cu.id = cdu.camera_unit_id
                WHERE cu.project_id = :pid
            """),
            {"pid": self.project_id},
        )).fetchall()

        jr_rows = (await s.execute(
            sa.text("SELECT day_id, SUM(count) AS total FROM junior_artist_calls WHERE project_id=:pid GROUP BY day_id"),
            {"pid": self.project_id},
        )).fetchall()

        pv_rows = (await s.execute(
            sa.text("""
                SELECT vdu.day_id, pv.name
                FROM vehicle_day_uses vdu
                JOIN picture_vehicles pv ON pv.id = vdu.vehicle_id
                WHERE pv.project_id = :pid
            """),
            {"pid": self.project_id},
        )).fetchall()

        # Build lookup dicts
        from collections import defaultdict
        scene_chars: dict[str, list[str]] = defaultdict(list)
        for r in char_rows:
            scene_chars[r.scene_id].append(r.canonical_name)

        scenes_by_day: dict[str, list[SceneData]] = defaultdict(list)
        for r in scene_rows:
            sc = SceneData(
                id=r.id, scene_number=r.scene_number, title=r.title,
                description=r.description, dn=r.dn,
                page_eighths=r.page_eighths, setups_est=r.setups_est or 0,
                location_name=r.loc_name, location_kind=r.loc_kind,
                characters=scene_chars.get(r.id, []),
            )
            scenes_by_day[r.day_id].append(sc)

        cam_by_day: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
        for r in cam_rows:
            cam_by_day[r.day_id].append((r.unit_code, r.kind, r.count))

        jr_by_day: dict[str, int] = {r.day_id: int(r.total) for r in jr_rows}

        pv_by_day: dict[str, list[str]] = defaultdict(list)
        for r in pv_rows:
            pv_by_day[r.day_id].append(r.name)

        for r in day_rows:
            day_scenes = scenes_by_day.get(r.id, [])
            # Cast = union of all scene characters
            seen: set[str] = set()
            cast: list[str] = []
            for sc in day_scenes:
                for cn in sc.characters:
                    if cn not in seen:
                        seen.add(cn)
                        cast.append(cn)
            day = DayData(
                id=r.id, date=r.date, kind=r.kind,
                shoot_day_number=r.shoot_day_number,
                shift_start=r.shift_start, shift_end=r.shift_end,
                location_id=r.primary_location_id,
                location_name=r.loc_name, location_area=r.loc_area,
                location_kind=r.loc_kind,
                banner_text=r.banner_text, notes=r.notes,
                scenes=day_scenes, cast=cast,
                jr_count=jr_by_day.get(r.id, 0),
                camera_uses=cam_by_day.get(r.id, []),
                vehicle_names=pv_by_day.get(r.id, []),
            )
            self.days.append(day)

        self.shoot_days = [d for d in self.days if d.kind == "shoot"]

    async def _load_characters(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("SELECT id, canonical_name, display_name, actor_name, is_principal FROM characters WHERE project_id=:pid ORDER BY is_principal DESC, canonical_name"),
            {"pid": self.project_id},
        )).fetchall()
        self.characters = [
            CharacterData(id=r.id, canonical_name=r.canonical_name,
                          display_name=r.display_name, actor_name=r.actor_name,
                          is_principal=r.is_principal)
            for r in rows
        ]

    async def _load_camera_units(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("SELECT id, unit_code, kind, description, rental_vendor, operator_name FROM camera_units WHERE project_id=:pid ORDER BY unit_code"),
            {"pid": self.project_id},
        )).fetchall()
        self.camera_units = [
            CameraUnitData(id=r.id, unit_code=r.unit_code, kind=r.kind,
                           description=r.description, rental_vendor=r.rental_vendor,
                           operator_name=r.operator_name)
            for r in rows
        ]

    async def _load_vehicles(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("SELECT id, name, spec, source, source_vendor FROM picture_vehicles WHERE project_id=:pid ORDER BY name"),
            {"pid": self.project_id},
        )).fetchall()
        day_use_rows = (await s.execute(
            sa.text("SELECT vdu.vehicle_id, vdu.day_id FROM vehicle_day_uses vdu JOIN picture_vehicles pv ON pv.id=vdu.vehicle_id WHERE pv.project_id=:pid"),
            {"pid": self.project_id},
        )).fetchall()
        from collections import defaultdict
        day_ids_by_vehicle: dict[str, list[str]] = defaultdict(list)
        for r in day_use_rows:
            day_ids_by_vehicle[r.vehicle_id].append(r.day_id)
        self.vehicles = [
            VehicleData(id=r.id, name=r.name, spec=r.spec, source=r.source,
                        source_vendor=r.source_vendor,
                        day_ids=day_ids_by_vehicle.get(r.id, []))
            for r in rows
        ]

    async def _load_jr_calls(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("""
                SELECT j.day_id, d.date, d.shoot_day_number, j.count, j.grade, j.context, j.vendor_name
                FROM junior_artist_calls j
                JOIN days d ON d.id = j.day_id
                WHERE j.project_id = :pid ORDER BY d.date, j.grade
            """),
            {"pid": self.project_id},
        )).fetchall()
        self.jr_calls = [
            JrCallData(day_id=r.day_id, day_date=r.date,
                       shoot_day_number=r.shoot_day_number,
                       count=r.count, grade=r.grade,
                       context=r.context, vendor_name=r.vendor_name)
            for r in rows
        ]

    async def _load_props(self, s: AsyncSession) -> None:
        prop_rows = (await s.execute(
            sa.text("SELECT id, name, category, source, source_vendor, lead_days, status FROM props WHERE project_id=:pid ORDER BY category, name"),
            {"pid": self.project_id},
        )).fetchall()
        self.props = [
            PropData(id=r.id, name=r.name, category=r.category,
                     source=r.source, source_vendor=r.source_vendor,
                     lead_days=r.lead_days, status=r.status)
            for r in prop_rows
        ]
        link_rows = (await s.execute(
            sa.text("""
                SELECT s.scene_number, p.name AS prop_name, p.category, sp.role
                FROM scene_props sp
                JOIN scenes s ON s.id = sp.scene_id
                JOIN props p  ON p.id  = sp.prop_id
                WHERE s.project_id = :pid ORDER BY s.scene_number
            """),
            {"pid": self.project_id},
        )).fetchall()
        self.scene_props = [
            ScenePropLink(scene_number=r.scene_number, prop_name=r.prop_name,
                          prop_category=r.category, role=r.role)
            for r in link_rows
        ]

    async def _load_animals(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("SELECT id, species, count, handler_name, vet_on_set, awbi_status FROM animals WHERE project_id=:pid ORDER BY species"),
            {"pid": self.project_id},
        )).fetchall()
        from collections import defaultdict
        day_ids_by_animal: dict[str, list[str]] = defaultdict(list)
        day_use_rows = (await s.execute(
            sa.text("SELECT da.animal_id, da.day_id FROM day_animals da JOIN animals a ON a.id=da.animal_id WHERE a.project_id=:pid"),
            {"pid": self.project_id},
        )).fetchall()
        for r in day_use_rows:
            day_ids_by_animal[r.animal_id].append(r.day_id)
        self.animals = [
            AnimalData(id=r.id, species=r.species, count=r.count,
                       handler_name=r.handler_name, vet_on_set=r.vet_on_set,
                       awbi_status=r.awbi_status,
                       day_ids=day_ids_by_animal.get(r.id, []))
            for r in rows
        ]

    async def _load_vfx(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("""
                SELECT v.id, v.shot_number, v.shot_type, v.complexity,
                       v.plates_required, v.vendor, v.bid_status, v.status,
                       s.scene_number
                FROM vfx_shots v
                LEFT JOIN scenes s ON s.id = v.scene_id
                WHERE v.project_id = :pid ORDER BY v.shot_number
            """),
            {"pid": self.project_id},
        )).fetchall()
        self.vfx_shots = [
            VfxShotData(id=r.id, shot_number=r.shot_number, shot_type=r.shot_type,
                        complexity=r.complexity, plates_required=r.plates_required,
                        vendor=r.vendor, bid_status=r.bid_status, status=r.status,
                        scene_number=r.scene_number)
            for r in rows
        ]

    async def _load_sfx(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("""
                SELECT e.id, e.effect_kind, e.coordinator, e.status, e.medic_required,
                       e.permits_required, e.day_id, s.scene_number
                FROM sfx_effects e
                LEFT JOIN scenes s ON s.id = e.scene_id
                WHERE e.project_id = :pid ORDER BY e.effect_kind
            """),
            {"pid": self.project_id},
        )).fetchall()
        self.sfx_effects = [
            SfxEffectData(id=r.id, scene_number=r.scene_number, day_id=r.day_id,
                          effect_kind=r.effect_kind, coordinator=r.coordinator,
                          status=r.status, medic_required=r.medic_required,
                          permits_required=r.permits_required)
            for r in rows
        ]

    async def _load_hmu(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("""
                SELECT h.id, h.look_id, h.category, h.apply_minutes, h.artist_vendor,
                       c.canonical_name, d.date AS day_date
                FROM hmu_sessions h
                JOIN characters c ON c.id = h.character_id
                LEFT JOIN days d ON d.id = h.day_id
                WHERE c.project_id = :pid ORDER BY d.date, c.canonical_name
            """),
            {"pid": self.project_id},
        )).fetchall()
        self.hmu_sessions = [
            HmuSessionData(id=r.id, character_name=r.canonical_name,
                           day_date=r.day_date, look_id=r.look_id,
                           category=r.category, apply_minutes=r.apply_minutes,
                           artist_vendor=r.artist_vendor)
            for r in rows
        ]

    async def _load_wardrobe(self, s: AsyncSession) -> None:
        rows = (await s.execute(
            sa.text("""
                SELECT w.id, w.look_id, w.era, w.description, w.source,
                       w.source_vendor, w.multiples_count, c.canonical_name
                FROM wardrobe_looks w
                JOIN characters c ON c.id = w.character_id
                WHERE c.project_id = :pid ORDER BY c.canonical_name, w.look_id
            """),
            {"pid": self.project_id},
        )).fetchall()
        self.wardrobe_looks = [
            WardrobeLookData(id=r.id, character_name=r.canonical_name,
                             look_id=r.look_id, era=r.era,
                             description=r.description, source=r.source,
                             source_vendor=r.source_vendor,
                             multiples_count=r.multiples_count or 1)
            for r in rows
        ]

    # ------------------------------------------------------------------
    # DOOD computation
    # ------------------------------------------------------------------

    def _compute_dood(self) -> None:
        """Populate character_dood: char_id → {shoot_day_number → W/H/.}."""
        char_working: dict[str, set[int]] = {}
        for char in self.characters:
            char_working[char.id] = set()

        # Map canonical_name → char_id
        name_to_id: dict[str, str] = {c.canonical_name: c.id for c in self.characters}

        for day in self.shoot_days:
            sdn = day.shoot_day_number
            if sdn is None:
                continue
            for cn in day.cast:
                cid = name_to_id.get(cn)
                if cid:
                    char_working[cid].add(sdn)

        shoot_day_nums = [d.shoot_day_number for d in self.shoot_days if d.shoot_day_number is not None]

        for char in self.characters:
            w_days = sorted(char_working.get(char.id, set()))
            dood: dict[int, str] = {}
            if not w_days:
                dood = {n: "." for n in shoot_day_nums}
            else:
                first_w, last_w = min(w_days), max(w_days)
                for sdn in shoot_day_nums:
                    if sdn in w_days:
                        dood[sdn] = "W"
                    elif first_w <= sdn <= last_w:
                        dood[sdn] = "H"
                    else:
                        dood[sdn] = "."
            self.character_dood[char.id] = dood


# ---------------------------------------------------------------------------
# Helpers used by multiple reports
# ---------------------------------------------------------------------------

def fmt_pages(eighths: int | None) -> str:
    """Convert integer eighths to '2 1/8' notation."""
    if not eighths:
        return ""
    full, rem = divmod(eighths, 8)
    if full and rem:
        return f"{full} {rem}/8"
    if full:
        return str(full)
    return f"{rem}/8"


def fmt_shift(start: time | None, end: time | None) -> str:
    if start and end:
        return f"{start.strftime('%H:%M')} — {end.strftime('%H:%M')}"
    if start:
        return start.strftime("%H:%M")
    return ""
