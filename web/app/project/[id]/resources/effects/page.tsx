import ResourceGrid from "@/components/resources/ResourceGrid";

export default function EffectsPage() {
  return (
    <ResourceGrid
      kind="sfx_effects"
      title="SFX & Stunts"
      description="Special effects and stunt sequences."
      columns={[
        { key: "name", label: "Effect" },
        { key: "kind", label: "Type" },
        { key: "scene_id", label: "Scene" },
        { key: "coordinator", label: "Coordinator" },
        { key: "notes", label: "Notes" },
      ]}
    />
  );
}
