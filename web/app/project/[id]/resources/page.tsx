import Link from "next/link";
import { useParams } from "next/navigation";

const RESOURCES = [
  { slug: "cast", cat: "Department", name: "Cast DOOD", description: "Day-out-of-days grid for all characters" },
  { slug: "juniors", cat: "Department", name: "Junior Artists", description: "Daily junior artist requirements" },
  { slug: "vehicles", cat: "Equipment", name: "Picture Vehicles", description: "Vehicle scheduling across shoot days" },
  { slug: "cameras", cat: "Equipment", name: "Camera Units", description: "Multi-unit camera scheduling" },
  { slug: "props", cat: "Art", name: "Props", description: "Property requirements per scene" },
  { slug: "animals", cat: "Art", name: "Animals", description: "Animal wrangling requirements" },
  { slug: "vfx", cat: "Post", name: "VFX Shots", description: "Visual effects shot tracking" },
  { slug: "effects", cat: "SFX", name: "SFX & Stunts", description: "Special effects and stunt sequences" },
  { slug: "hmu", cat: "Department", name: "Hair & MU", description: "Hair and makeup scheduling" },
  { slug: "wardrobe", cat: "Department", name: "Wardrobe", description: "Wardrobe looks per character per day" },
] as const;

export default function ResourcesPage({ params }: { params: { id: string } }) {
  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="meta meta--red" style={{ marginBottom: "8px" }}>Resources</div>
      <h2 className="display--sm" style={{ marginBottom: "8px" }}>
        Resource Hub<span className="red">.</span>
      </h2>
      <p className="voice" style={{ fontSize: "15px", marginBottom: "32px" }}>
        All departments and equipment, visualised day-by-day.
      </p>

      <div className="res-grid">
        {RESOURCES.map((r) => (
          <Link
            key={r.slug}
            href={`/project/${params.id}/resources/${r.slug}`}
            className="res-tile"
          >
            <div className="res-tile__cat">{r.cat}</div>
            <div className="res-tile__name">{r.name}</div>
            <div className="res-tile__count-lbl">{r.description}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
