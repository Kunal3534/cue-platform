import ResourceGrid from "@/components/resources/ResourceGrid";

export default function AnimalsPage() {
  return (
    <ResourceGrid
      kind="animals"
      title="Animals"
      description="Animal wrangling requirements across shoot days."
      columns={[
        { key: "name", label: "Animal" },
        { key: "species", label: "Species" },
        { key: "wrangler", label: "Wrangler" },
        { key: "scenes", label: "Scenes" },
      ]}
    />
  );
}
