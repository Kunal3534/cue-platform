import ResourceGrid from "@/components/resources/ResourceGrid";

export default function HmuPage() {
  return (
    <ResourceGrid
      kind="hmu_sessions"
      title="Hair & Make-Up"
      description="HMU session scheduling per character and shoot day."
      columns={[
        { key: "character_id", label: "Character" },
        { key: "day_id", label: "Day" },
        { key: "look", label: "Look" },
        { key: "call_time", label: "Call Time" },
        { key: "duration_min", label: "Duration" },
      ]}
    />
  );
}
