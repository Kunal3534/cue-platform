import ResourceGrid from "@/components/resources/ResourceGrid";

export default function VehiclesPage() {
  return (
    <ResourceGrid
      kind="picture_vehicles"
      title="Picture Vehicles"
      description="Vehicle scheduling and availability across shoot days."
      columns={[
        { key: "name", label: "Vehicle" },
        { key: "kind", label: "Type" },
        { key: "make", label: "Make/Model" },
        { key: "colour", label: "Colour" },
      ]}
    />
  );
}
