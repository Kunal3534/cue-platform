import ResourceGrid from "@/components/resources/ResourceGrid";

export default function JuniorsPage() {
  return (
    <ResourceGrid
      kind="junior_artists"
      title="Junior Artists"
      description="Daily junior artist requirements across shoot days."
      columns={[
        { key: "name", label: "Description" },
        { key: "category", label: "Category" },
        { key: "count", label: "Count" },
        { key: "day_id", label: "Day" },
      ]}
    />
  );
}
