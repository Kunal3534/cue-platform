"""v1 schema — all new tables and project table additions

Revision ID: 002
Revises: 001
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enum(name: str, *values: str) -> pg.ENUM:
    """Return a pg.ENUM that references an already-created PG type.

    We use pg.ENUM (not sa.Enum) because only the dialect-specific type
    reliably respects create_type=False and won't emit a second CREATE TYPE
    after we've already issued it via op.execute() above.
    """
    return pg.ENUM(*values, name=name, create_type=False)


def upgrade():
    # -----------------------------------------------------------------------
    # 1. Create all Postgres enum types
    # -----------------------------------------------------------------------
    op.execute("CREATE TYPE project_status    AS ENUM ('pre','shoot','wrap','archived')")
    op.execute("CREATE TYPE location_kind     AS ENUM ('ext','int','studio','practical')")
    op.execute("CREATE TYPE day_kind          AS ENUM ('shoot','travel','off','hold','buffer','prep')")
    op.execute("CREATE TYPE scene_dn          AS ENUM ('day','night','day_int','night_int','dusk')")
    op.execute("CREATE TYPE scene_status      AS ENUM ('planned','shot','omitted','pickup_needed')")
    op.execute("CREATE TYPE scene_char_role   AS ENUM ('speaking','non_speaking','featured','background')")
    op.execute("CREATE TYPE day_scene_status  AS ENUM ('scheduled','in_progress','shot','omitted_today')")
    op.execute("CREATE TYPE prop_category     AS ENUM ('hero_critical','hero','set_dress','background','food','paper_prop')")
    op.execute("CREATE TYPE prop_source       AS ENUM ('build_inhouse','build_studio','rental','owned','local_sourced','purchased')")
    op.execute("CREATE TYPE prop_status       AS ENUM ('planned','ordered','in_progress','ready','on_set','returned')")
    op.execute("CREATE TYPE prop_scene_role   AS ENUM ('hero','set_dress','action_prop','bg')")
    op.execute("CREATE TYPE vet_on_set        AS ENUM ('not_required','standby','required')")
    op.execute("CREATE TYPE awbi_status       AS ENUM ('not_required','exempt','applied','pending','granted','denied')")
    op.execute("CREATE TYPE vehicle_source    AS ENUM ('rental','owned','local_hired','loan')")
    op.execute("CREATE TYPE camera_kind       AS ENUM ('camera','lighting','grip','special','drone','steadi','jib')")
    op.execute("CREATE TYPE jr_grade          AS ENUM ('junior','sr','specialist','dancer','musician')")
    op.execute("CREATE TYPE jr_status         AS ENUM ('planned','briefed','confirmed','on_set')")
    op.execute("CREATE TYPE vfx_shot_type     AS ENUM ('sky_grade','crowd_aug','greenscreen','cleanup','drone_replace','muzzle_flash','aging_blend','period_cleanup','rotoscope','other')")
    op.execute("CREATE TYPE vfx_complexity    AS ENUM ('low','medium','high','hero')")
    op.execute("CREATE TYPE vfx_bid_status    AS ENUM ('estimated','bidded','extended','cancelled')")
    op.execute("CREATE TYPE vfx_status        AS ENUM ('planned','plates_delivered','comp_started','review','delivered','final')")
    op.execute("CREATE TYPE sfx_effect_kind   AS ENUM ('fire','pyro','squibs','rain','wind','breakaway','fog','water','explosion','stunt_fight','stunt_fall','stunt_vehicle','stunt_water','other')")
    op.execute("CREATE TYPE sfx_status        AS ENUM ('planned','permit_pending','cleared','rehearsed','executed')")
    op.execute("CREATE TYPE hmu_category      AS ENUM ('straight','prosthetic','wound_sfx','de_age','aged','aging','dental','hair_piece')")
    op.execute("CREATE TYPE wardrobe_era      AS ENUM ('now','1994','2008','flashback','other')")
    op.execute("CREATE TYPE wardrobe_source   AS ENUM ('in_house','tailored','rental','sourced_flea','govt_spec','purchased')")
    op.execute("CREATE TYPE art_status        AS ENUM ('planned','designing','building','ready','struck','returned')")
    op.execute("CREATE TYPE permit_kind       AS ENUM ('location','road_rto','fire','aerial_dgca','coastal','animal_awbi','closed_set','heritage_asi','police','panchayat','other')")
    op.execute("CREATE TYPE permit_status     AS ENUM ('not_applied','applied','pending','granted','denied','expired')")
    op.execute("CREATE TYPE callsheet_status  AS ENUM ('draft','ready','sent','distributed','stale')")
    op.execute("CREATE TYPE flag_kind         AS ENUM ('cast_hold','permit_lead','weather','drone_block','insurance','continuity','vendor','capacity','missing_data','cost_overrun','safety','custom')")
    op.execute("CREATE TYPE flag_severity     AS ENUM ('info','warning','blocker')")
    op.execute("CREATE TYPE flag_raised_by    AS ENUM ('system','user')")
    op.execute("CREATE TYPE propagation_status AS ENUM ('pending','confirmed','discarded','expired')")
    op.execute("CREATE TYPE chat_role         AS ENUM ('user','assistant','tool')")

    # -----------------------------------------------------------------------
    # 2. Extend the projects table with v1 columns
    # -----------------------------------------------------------------------
    op.alter_column("projects", "title", type_=sa.String(500), existing_nullable=False)
    op.alter_column("projects", "window", type_=sa.String(500), existing_nullable=True)

    op.add_column("projects", sa.Column("start_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("end_date", sa.Date, nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "status",
            _enum("project_status", "pre", "shoot", "wrap", "archived"),
            nullable=False,
            server_default="pre",
        ),
    )
    op.add_column(
        "projects",
        sa.Column("settings", pg.JSONB, nullable=False, server_default="{}"),
    )
    op.add_column("projects", sa.Column("source_filename", sa.String(500), nullable=True))
    # live_scenario_id added without FK here; FK added after scenarios table is created
    op.add_column("projects", sa.Column("live_scenario_id", sa.String(36), nullable=True))

    # -----------------------------------------------------------------------
    # 3. locations
    # -----------------------------------------------------------------------
    op.create_table(
        "locations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("area", sa.String(500)),
        sa.Column("address", sa.Text),
        sa.Column("lat", sa.Numeric(10, 6)),
        sa.Column("lng", sa.Numeric(10, 6)),
        sa.Column("kind", _enum("location_kind", "ext", "int", "studio", "practical"), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # 4. characters
    # -----------------------------------------------------------------------
    op.create_table(
        "characters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_name", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("actor_name", sa.String(500)),
        sa.Column("actor_contact", pg.JSONB),
        sa.Column("is_principal", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "canonical_name", name="uq_characters_project_canonical"),
    )

    # -----------------------------------------------------------------------
    # 5. days
    # -----------------------------------------------------------------------
    op.create_table(
        "days",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shoot_day_number", sa.Integer),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("kind", _enum("day_kind", "shoot", "travel", "off", "hold", "buffer", "prep"), nullable=False),
        sa.Column("shift_start", sa.Time),
        sa.Column("shift_end", sa.Time),
        sa.Column("primary_location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("banner_text", sa.Text),
        sa.Column("sunrise", sa.Time),
        sa.Column("sunset", sa.Time),
        sa.Column("golden_hour_start", sa.Time),
        sa.Column("golden_hour_end", sa.Time),
        sa.Column("weather", pg.JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "date", name="uq_days_project_date"),
    )
    op.create_index("ix_days_project_shoot_day", "days", ["project_id", "shoot_day_number"])

    # -----------------------------------------------------------------------
    # 6. scenes
    # -----------------------------------------------------------------------
    op.create_table(
        "scenes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_number", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("description", sa.Text),
        sa.Column("page_eighths", sa.Integer),
        sa.Column("setups_est", sa.Integer, nullable=False, server_default="0"),
        sa.Column("dn", _enum("scene_dn", "day", "night", "day_int", "night_int", "dusk"), nullable=False),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("act", sa.Integer),
        sa.Column("sequence", sa.Integer),
        sa.Column("status", _enum("scene_status", "planned", "shot", "omitted", "pickup_needed"), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "scene_number", name="uq_scenes_project_number"),
    )

    # -----------------------------------------------------------------------
    # 7. day_scenes
    # -----------------------------------------------------------------------
    op.create_table(
        "day_scenes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_in_day", sa.Integer, nullable=False),
        sa.Column("estimated_start", sa.Time),
        sa.Column("estimated_duration_minutes", sa.Integer),
        sa.Column("actual_status", _enum("day_scene_status", "scheduled", "in_progress", "shot", "omitted_today"), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("day_id", "scene_id", name="uq_day_scenes"),
    )
    op.create_index("ix_day_scenes_scene_id", "day_scenes", ["scene_id"])

    # -----------------------------------------------------------------------
    # 8. scene_characters
    # -----------------------------------------------------------------------
    op.create_table(
        "scene_characters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _enum("scene_char_role", "speaking", "non_speaking", "featured", "background"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scene_id", "character_id", name="uq_scene_characters"),
    )

    # -----------------------------------------------------------------------
    # 9. props + scene_props
    # -----------------------------------------------------------------------
    op.create_table(
        "props",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("category", _enum("prop_category", "hero_critical", "hero", "set_dress", "background", "food", "paper_prop"), nullable=False),
        sa.Column("scenes_raw", sa.Text),
        sa.Column("source", _enum("prop_source", "build_inhouse", "build_studio", "rental", "owned", "local_sourced", "purchased")),
        sa.Column("source_vendor", sa.String(500)),
        sa.Column("lead_days", sa.Integer),
        sa.Column("insurance_inr", sa.Integer),
        sa.Column("status", _enum("prop_status", "planned", "ordered", "in_progress", "ready", "on_set", "returned"), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "scene_props",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prop_id", sa.String(36), sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _enum("prop_scene_role", "hero", "set_dress", "action_prop", "bg"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scene_id", "prop_id", name="uq_scene_props"),
    )

    # -----------------------------------------------------------------------
    # 10. animals + day_animals
    # -----------------------------------------------------------------------
    op.create_table(
        "animals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("species", sa.String(200), nullable=False),
        sa.Column("count", sa.Integer, nullable=False),
        sa.Column("handler_name", sa.String(500)),
        sa.Column("handler_contact", sa.String(500)),
        sa.Column("vet_on_set", _enum("vet_on_set", "not_required", "standby", "required"), nullable=False, server_default="not_required"),
        sa.Column("vet_name", sa.String(500)),
        sa.Column("vet_contact", sa.String(500)),
        sa.Column("awbi_status", _enum("awbi_status", "not_required", "exempt", "applied", "pending", "granted", "denied"), nullable=False, server_default="not_required"),
        sa.Column("awbi_number", sa.String(100)),
        sa.Column("awbi_granted_at", sa.Date),
        sa.Column("awbi_applied_at", sa.Date),
        sa.Column("rest_window_hours", sa.Integer),
        sa.Column("insurance_inr", sa.Integer),
        sa.Column("welfare_notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "day_animals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("animal_id", sa.String(36), sa.ForeignKey("animals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # 11. picture_vehicles + vehicle_day_uses
    # -----------------------------------------------------------------------
    op.create_table(
        "picture_vehicles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("spec", sa.Text),
        sa.Column("source", _enum("vehicle_source", "rental", "owned", "local_hired", "loan")),
        sa.Column("source_vendor", sa.String(500)),
        sa.Column("driver_name", sa.String(500)),
        sa.Column("driver_contact", sa.String(500)),
        sa.Column("insurance_inr", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "vehicle_day_uses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("picture_vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("vehicle_id", "day_id", name="uq_vehicle_day_uses"),
    )

    # -----------------------------------------------------------------------
    # 12. camera_units + camera_day_uses
    # -----------------------------------------------------------------------
    op.create_table(
        "camera_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_code", sa.String(16), nullable=False),
        sa.Column("kind", _enum("camera_kind", "camera", "lighting", "grip", "special", "drone", "steadi", "jib"), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("rental_vendor", sa.String(500)),
        sa.Column("operator_name", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "unit_code", name="uq_camera_units_project_code"),
    )
    op.create_table(
        "camera_day_uses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("camera_unit_id", sa.String(36), sa.ForeignKey("camera_units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("camera_unit_id", "day_id", name="uq_camera_day_uses"),
    )

    # -----------------------------------------------------------------------
    # 13. junior_artist_calls
    # -----------------------------------------------------------------------
    op.create_table(
        "junior_artist_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("count", sa.Integer, nullable=False),
        sa.Column("grade", _enum("jr_grade", "junior", "sr", "specialist", "dancer", "musician"), nullable=False),
        sa.Column("context", sa.Text),
        sa.Column("wardrobe_notes", sa.Text),
        sa.Column("vendor_name", sa.String(500)),
        sa.Column("vendor_contact", sa.String(500)),
        sa.Column("meal_plan_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("status", _enum("jr_status", "planned", "briefed", "confirmed", "on_set"), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("day_id", "grade", name="uq_jr_calls_day_grade"),
    )

    # -----------------------------------------------------------------------
    # 14. vfx_shots
    # -----------------------------------------------------------------------
    op.create_table(
        "vfx_shots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")),
        sa.Column("shot_number", sa.String(32), nullable=False),
        sa.Column("shot_type", _enum("vfx_shot_type", "sky_grade", "crowd_aug", "greenscreen", "cleanup", "drone_replace", "muzzle_flash", "aging_blend", "period_cleanup", "rotoscope", "other"), nullable=False),
        sa.Column("complexity", _enum("vfx_complexity", "low", "medium", "high", "hero"), nullable=False),
        sa.Column("plates_required", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text),
        sa.Column("vendor_name", sa.String(500)),
        sa.Column("budget_inr", sa.Integer),
        sa.Column("bid_status", _enum("vfx_bid_status", "estimated", "bidded", "extended", "cancelled")),
        sa.Column("status", _enum("vfx_status", "planned", "plates_delivered", "comp_started", "review", "delivered", "final"), nullable=False, server_default="planned"),
        sa.Column("markers", pg.JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "shot_number", name="uq_vfx_shots_project_number"),
    )

    # -----------------------------------------------------------------------
    # 15. sfx_effects
    # -----------------------------------------------------------------------
    op.create_table(
        "sfx_effects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="SET NULL")),
        sa.Column("effect_kind", _enum("sfx_effect_kind", "fire", "pyro", "squibs", "rain", "wind", "breakaway", "fog", "water", "explosion", "stunt_fight", "stunt_fall", "stunt_vehicle", "stunt_water", "other"), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("coordinator", sa.String(500), nullable=False),
        sa.Column("coordinator_contact", sa.String(500)),
        sa.Column("safety_plan_url", sa.Text),
        sa.Column("permits_required", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("insurance_rider", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("medic_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("stunt_doubles", pg.JSONB),
        sa.Column("rehearsal_date", sa.Date),
        sa.Column("status", _enum("sfx_status", "planned", "permit_pending", "cleared", "rehearsed", "executed"), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # 16. hmu_sessions
    # -----------------------------------------------------------------------
    op.create_table(
        "hmu_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("look_id", sa.String(16), nullable=False),
        sa.Column("category", _enum("hmu_category", "straight", "prosthetic", "wound_sfx", "de_age", "aged", "aging", "dental", "hair_piece"), nullable=False),
        sa.Column("apply_minutes", sa.Integer),
        sa.Column("remove_minutes", sa.Integer),
        sa.Column("hmu_call_time", sa.Time),
        sa.Column("artist_lead", sa.String(500)),
        sa.Column("artist_vendor", sa.String(500)),
        sa.Column("mold_sessions", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("continuity_ref", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("character_id", "day_id", "look_id", name="uq_hmu_sessions_char_day_look"),
    )

    # -----------------------------------------------------------------------
    # 17. wardrobe_looks
    # -----------------------------------------------------------------------
    op.create_table(
        "wardrobe_looks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("look_id", sa.String(16), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("era", _enum("wardrobe_era", "now", "1994", "2008", "flashback", "other"), nullable=False),
        sa.Column("era_label", sa.String(100)),
        sa.Column("scenes_raw", sa.Text),
        sa.Column("multiples_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("source", _enum("wardrobe_source", "in_house", "tailored", "rental", "sourced_flea", "govt_spec", "purchased")),
        sa.Column("source_vendor", sa.String(500)),
        sa.Column("return_by", sa.Date),
        sa.Column("continuity_key", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("character_id", "look_id", name="uq_wardrobe_looks_char_look"),
    )

    # -----------------------------------------------------------------------
    # 18. art_builds
    # -----------------------------------------------------------------------
    op.create_table(
        "art_builds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("scenes_raw", sa.Text),
        sa.Column("days_ref", pg.ARRAY(sa.String(36))),
        sa.Column("build_days_lead", sa.Integer),
        sa.Column("art_dir", sa.String(500)),
        sa.Column("status", _enum("art_status", "planned", "designing", "building", "ready", "struck", "returned"), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # 19. permits
    # -----------------------------------------------------------------------
    op.create_table(
        "permits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", _enum("permit_kind", "location", "road_rto", "fire", "aerial_dgca", "coastal", "animal_awbi", "closed_set", "heritage_asi", "police", "panchayat", "other"), nullable=False),
        sa.Column("issuing_body", sa.String(500), nullable=False),
        sa.Column("reference_number", sa.String(100)),
        sa.Column("applied_at", sa.Date),
        sa.Column("granted_at", sa.Date),
        sa.Column("expires_at", sa.Date),
        sa.Column("status", _enum("permit_status", "not_applied", "applied", "pending", "granted", "denied", "expired"), nullable=False, server_default="not_applied"),
        sa.Column("fee_inr", sa.Integer),
        sa.Column("related_location_id", sa.String(36)),
        sa.Column("related_day_ids", pg.ARRAY(sa.String(36))),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # 20. call_sheets
    # -----------------------------------------------------------------------
    op.create_table(
        "call_sheets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", _enum("callsheet_status", "draft", "ready", "sent", "distributed", "stale"), nullable=False, server_default="draft"),
        sa.Column("pdf_s3_key", sa.Text),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("sent_to", pg.JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("day_id", "version", name="uq_call_sheets_day_version"),
    )
    op.create_index("ix_call_sheets_day_version", "call_sheets", ["day_id", "version"])

    # -----------------------------------------------------------------------
    # 21. flags
    # -----------------------------------------------------------------------
    op.create_table(
        "flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", _enum("flag_kind", "cast_hold", "permit_lead", "weather", "drone_block", "insurance", "continuity", "vendor", "capacity", "missing_data", "cost_overrun", "safety", "custom"), nullable=False),
        sa.Column("severity", _enum("flag_severity", "info", "warning", "blocker"), nullable=False),
        sa.Column("related_scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL")),
        sa.Column("related_day_id", sa.String(36), sa.ForeignKey("days.id", ondelete="SET NULL")),
        sa.Column("related_character_id", sa.String(36), sa.ForeignKey("characters.id", ondelete="SET NULL")),
        sa.Column("related_resource_ref", pg.JSONB),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("raised_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raised_by", _enum("flag_raised_by", "system", "user"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("dismissed", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_flags_open", "flags", ["project_id", "severity", "resolved_at"])

    # -----------------------------------------------------------------------
    # 22. edits (append-only audit log)
    # -----------------------------------------------------------------------
    op.create_table(
        "edits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("entity_table", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("old_value", pg.JSONB),
        sa.Column("new_value", pg.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("propagated", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_edits_batch_id", "edits", ["batch_id"])
    op.create_index("ix_edits_project_created", "edits", ["project_id", "created_at"])

    # -----------------------------------------------------------------------
    # 23. scenarios  (project_id → projects is fine; live_scenario FK added below)
    # -----------------------------------------------------------------------
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("parent_scenario_id", sa.String(36), sa.ForeignKey("scenarios.id")),
        sa.Column("is_live", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("forked_at_batch", sa.String(36)),
        sa.Column("merged_at", sa.DateTime(timezone=True)),
        sa.Column("discarded_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot", pg.JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Exactly one live scenario per project
    op.execute(
        "CREATE UNIQUE INDEX uq_scenarios_live ON scenarios(project_id) WHERE is_live = TRUE"
    )

    # Now add the FK from projects.live_scenario_id → scenarios.id
    op.create_foreign_key(
        "fk_projects_live_scenario",
        "projects",
        "scenarios",
        ["live_scenario_id"],
        ["id"],
        use_alter=True,
    )

    # -----------------------------------------------------------------------
    # 24. propagation_previews
    # -----------------------------------------------------------------------
    op.create_table(
        "propagation_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("diff", pg.JSONB),
        sa.Column("status", _enum("propagation_status", "pending", "confirmed", "discarded", "expired"), nullable=False, server_default="pending"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -----------------------------------------------------------------------
    # 25. chat_threads + chat_messages
    # -----------------------------------------------------------------------
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_threads_project_active", "chat_threads", ["project_id", "last_active_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _enum("chat_role", "user", "assistant", "tool"), nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("tool_calls", pg.JSONB),
        sa.Column("tool_results", pg.JSONB),
        sa.Column("edits_batch_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_thread_created", "chat_messages", ["thread_id", "created_at"])

    # -----------------------------------------------------------------------
    # 26. magic_links
    # -----------------------------------------------------------------------
    op.create_table(
        "magic_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )

    # -----------------------------------------------------------------------
    # 27. view_cache
    # -----------------------------------------------------------------------
    op.create_table(
        "view_cache",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("view_name", sa.String(100), nullable=False),
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("scenarios.id", ondelete="CASCADE")),
        sa.Column("payload", pg.JSONB, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # NULLS NOT DISTINCT: two rows with the same (project_id, view_name, NULL) are treated as dupes
    op.execute(
        "CREATE UNIQUE INDEX uq_view_cache "
        "ON view_cache(project_id, view_name, scenario_id) NULLS NOT DISTINCT"
    )


def downgrade():
    # Drop FK added via use_alter before dropping the tables
    op.drop_constraint("fk_projects_live_scenario", "projects", type_="foreignkey")

    for table in [
        "view_cache", "magic_links", "chat_messages", "chat_threads",
        "propagation_previews", "scenarios", "edits", "flags",
        "call_sheets", "permits", "art_builds", "wardrobe_looks",
        "hmu_sessions", "sfx_effects", "vfx_shots", "junior_artist_calls",
        "camera_day_uses", "camera_units", "vehicle_day_uses", "picture_vehicles",
        "day_animals", "animals", "scene_props", "props",
        "scene_characters", "day_scenes", "scenes", "days",
        "characters", "locations",
    ]:
        op.drop_table(table)

    # Remove columns added to projects
    for col in ["live_scenario_id", "source_filename", "settings", "status", "end_date", "start_date"]:
        op.drop_column("projects", col)

    op.alter_column("projects", "title", type_=sa.String(255), existing_nullable=False)
    op.alter_column("projects", "window", type_=sa.String(255), existing_nullable=True)

    for enum_name in [
        "chat_role", "propagation_status", "flag_raised_by", "flag_severity", "flag_kind",
        "callsheet_status", "permit_status", "permit_kind", "art_status",
        "wardrobe_source", "wardrobe_era", "hmu_category", "sfx_status", "sfx_effect_kind",
        "vfx_status", "vfx_bid_status", "vfx_complexity", "vfx_shot_type",
        "jr_status", "jr_grade", "camera_kind", "vehicle_source",
        "awbi_status", "vet_on_set", "prop_scene_role", "prop_status", "prop_source",
        "prop_category", "day_scene_status", "scene_char_role", "scene_status",
        "scene_dn", "day_kind", "location_kind", "project_status",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
