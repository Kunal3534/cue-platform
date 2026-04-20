import ResourceGrid from "@/components/resources/ResourceGrid";

export default function CamerasPage() {
  return (
    <ResourceGrid
      kind="camera_units"
      title="Camera Units"
      description="Multi-unit camera scheduling across the production."
      columns={[
        { key: "unit_code", label: "Unit" },
        { key: "kind", label: "Type" },
        { key: "camera_model", label: "Camera" },
        { key: "operator", label: "Operator" },
      ]}
    />
  );
}
