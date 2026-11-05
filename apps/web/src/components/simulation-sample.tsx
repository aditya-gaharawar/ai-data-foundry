"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import { PrivateImage } from "./annotation-image";
import { Code } from "./ui";

const SceneViewer = dynamic(() => import("./scene-viewer"), {
  ssr: false,
  loading: () => <p role="status">Loading 3D viewer…</p>,
});

export function SimulationSample({
  versionId,
  sampleId,
  metadata,
}: {
  versionId: string;
  sampleId: string;
  metadata: unknown;
}) {
  const [open, setOpen] = useState(false);
  const prefix = `/v1/versions/${versionId}/samples/${sampleId}/artifacts`;
  return (
    <details
      className="evidence-details"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Inspect scene, object mask & sensor metadata</summary>
      {open && (
        <div className="simulation-inspector">
          <SceneViewer path={`${prefix}/scene`} />
          <figure>
            <PrivateImage
              path={`${prefix}/mask`}
              alt="Rendered object-index mask"
            />
            <figcaption>Aligned object-index mask</figcaption>
          </figure>
          <Code value={metadata} />
        </div>
      )}
    </details>
  );
}
