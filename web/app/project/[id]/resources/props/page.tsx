import ResourceGrid from "@/components/resources/ResourceGrid";

export default function PropsPage() {
  return (
    <ResourceGrid
      kind="props"
      title="Props"
      description="Property requirements per scene and shoot day."
      columns={[
        { key: "name", label: "Prop" },
        { key: "category", label: "Category" },
        { key: "source", label: "Source" },
        { key: "notes", label: "Notes" },
      ]}
    />
  );
}
