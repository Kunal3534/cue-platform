"use client";
import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { createProject } from "@/lib/api";
import NavBar from "@/components/nav/NavBar";

export default function NewProjectPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const project = await createProject(file);
      router.push(`/project/${project.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".xlsx")) setFile(dropped);
  };

  return (
    <>
      <NavBar />
      <main className="page" style={{ paddingTop: "56px" }}>
        <div className="upload">
          <div className="meta meta--red" style={{ marginBottom: "8px" }}>
            New project
          </div>
          <h1 className="display" style={{ fontSize: "44px" }}>
            Upload a master<span className="red">.</span>
          </h1>
          <p className="voice" style={{ marginTop: "16px" }}>
            Any Katakirr-style .xlsx breakdown. Cue builds the project graph
            and renders the main schedule. The rest of the views come for free.
          </p>

          <div
            className={`dropzone${drag ? " dropzone--active" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={handleDrop}
          >
            {file ? (
              <>
                <div className="dropzone__headline">{file.name}</div>
                <div className="dropzone__sub">
                  {(file.size / 1024).toFixed(1)} KB — click to change
                </div>
              </>
            ) : (
              <>
                <div className="dropzone__headline">Drop an .xlsx here</div>
                <div className="dropzone__sub">
                  or click to pick from your computer
                </div>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {error && (
            <p
              className="mono-xs"
              style={{ color: "var(--cue-red)", marginTop: "12px" }}
            >
              {error}
            </p>
          )}

          <button
            className="btn btn--primary"
            style={{ marginTop: "24px" }}
            disabled={!file || busy}
            onClick={handleSubmit}
          >
            {busy ? "Parsing…" : "Build project →"}
          </button>
        </div>
      </main>
    </>
  );
}
