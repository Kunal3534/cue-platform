import ResourceGrid from "@/components/resources/ResourceGrid";

export default function VfxPage() {
  return (
    <ResourceGrid
      kind="vfx_shots"
      title="VFX Shots"
      description="Visual effects shot tracking across scenes and days."
      columns={[
        { key: "shot_code", label: "Shot" },
        { key: "description", label: "Description" },
        { key: "complexity", label: "Complexity" },
        { key: "vendor", label: "Vendor" },
        { key: "status", label: "Status" },
      ]}
    />
  );
}
