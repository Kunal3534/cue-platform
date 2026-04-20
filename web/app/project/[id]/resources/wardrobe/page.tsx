import ResourceGrid from "@/components/resources/ResourceGrid";

export default function WardrobePage() {
  return (
    <ResourceGrid
      kind="wardrobe_looks"
      title="Wardrobe"
      description="Wardrobe looks per character and scene."
      columns={[
        { key: "character_id", label: "Character" },
        { key: "look_code", label: "Look" },
        { key: "description", label: "Description" },
        { key: "scene_ids", label: "Scenes" },
        { key: "continuity_notes", label: "Continuity" },
      ]}
    />
  );
}
