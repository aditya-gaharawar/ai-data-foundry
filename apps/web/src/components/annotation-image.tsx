"use client";

import { useEffect, useRef, useState } from "react";
import type { Box } from "@/lib/curation";
import { ApiError } from "@/lib/api";
import { useWorkspace } from "./context";
import { Button, ErrorNotice, Loading } from "./ui";

function usePrivateImage(path: string) {
  const { organization } = useWorkspace();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    const abort = new AbortController();
    let objectUrl = "";
    setUrl("");
    setError(null);
    async function load() {
      try {
        const response = await fetch(`/api${path}`, {
          headers: { "X-Organization-Id": organization.id },
          signal: abort.signal,
        });
        if (!response.ok) {
          const problem = await response.json();
          throw new ApiError(
            response.status,
            problem.code,
            problem.detail,
            problem.request_id,
          );
        }
        objectUrl = URL.createObjectURL(await response.blob());
        if (abort.signal.aborted) URL.revokeObjectURL(objectUrl);
        else setUrl(objectUrl);
      } catch (failure) {
        if (!abort.signal.aborted) setError(failure);
      }
    }
    void load();
    return () => {
      abort.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [organization.id, path]);
  return { url, error };
}

export function PrivateImage({ path, alt }: { path: string; alt: string }) {
  const { url, error } = usePrivateImage(path);
  if (error) return <ErrorNotice error={error} />;
  if (!url) return <Loading />;
  // Authenticated blob URLs must not be sent to an image optimization service.
  return <img src={url} alt={alt} className="private-image" />;
}

export function BoxEditor({
  path,
  width,
  height,
  categories,
  boxes,
  onChange,
  readOnly = false,
}: {
  path: string;
  width: number;
  height: number;
  categories: string[];
  boxes: Box[];
  onChange: (boxes: Box[]) => void;
  readOnly?: boolean;
}) {
  const { url, error } = usePrivateImage(path);
  const start = useRef<{ x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<Box | null>(null);
  function point(event: React.PointerEvent<SVGSVGElement>) {
    const inverse = event.currentTarget.getScreenCTM()?.inverse();
    if (!inverse) return { x: 0, y: 0 };
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(
      inverse,
    );
    return {
      x: Math.max(0, Math.min(width, p.x)),
      y: Math.max(0, Math.min(height, p.y)),
    };
  }
  function change(index: number, field: keyof Box, value: string) {
    onChange(
      boxes.map((box, i) =>
        i === index
          ? { ...box, [field]: field === "label" ? value : Number(value) }
          : box,
      ),
    );
  }
  return (
    <>
      <ErrorNotice error={error} />
      {!url && !error ? (
        <Loading />
      ) : (
        <div className="annotation-canvas">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label={`Image annotation preview, ${width} by ${height} pixels, ${boxes.length} boxes`}
            style={{
              touchAction: readOnly ? "auto" : "none",
              cursor: readOnly ? "default" : "crosshair",
            }}
            onPointerDown={(event) => {
              if (readOnly || boxes.length >= 100) return;
              start.current = point(event);
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (!start.current) return;
              const end = point(event);
              setDraft({
                label: categories[0],
                x: Math.min(start.current.x, end.x),
                y: Math.min(start.current.y, end.y),
                width: Math.abs(end.x - start.current.x),
                height: Math.abs(end.y - start.current.y),
              });
            }}
            onPointerUp={(event) => {
              if (!start.current) return;
              const end = point(event);
              const box = {
                label: categories[0],
                x: Math.min(start.current.x, end.x),
                y: Math.min(start.current.y, end.y),
                width: Math.abs(end.x - start.current.x),
                height: Math.abs(end.y - start.current.y),
              };
              if (box.width >= 1 && box.height >= 1) onChange([...boxes, box]);
              start.current = null;
              setDraft(null);
            }}
            onPointerCancel={() => {
              start.current = null;
              setDraft(null);
            }}
          >
            <image href={url} width={width} height={height} />
            {[...boxes, ...(draft ? [draft] : [])].map((box, index) => (
              <g key={index}>
                <rect
                  x={box.x}
                  y={box.y}
                  width={box.width}
                  height={box.height}
                  fill="#0070f318"
                  stroke="#0070f3"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                >
                  <title>{`${index + 1}: ${box.label}, x ${box.x}, y ${box.y}, width ${box.width}, height ${box.height}`}</title>
                </rect>
              </g>
            ))}
          </svg>
        </div>
      )}
      <div className="detail-meta" style={{ margin: "12px 0" }}>
        {width} × {height} pixels · {boxes.length} boxes
        {!readOnly && " · Drag to draw, or use the coordinate fields below."}
      </div>
      <div className="stack">
        {boxes.map((box, index) => (
          <fieldset className="box-fields" key={index} disabled={readOnly}>
            <legend>Box {index + 1}</legend>
            <label className="field">
              <span>Box {index + 1} category</span>
              <select
                value={box.label}
                onChange={(event) => change(index, "label", event.target.value)}
              >
                {categories.map((category) => (
                  <option key={category}>{category}</option>
                ))}
              </select>
            </label>
            <div className="box-coordinates">
              {(["x", "y", "width", "height"] as const).map((field) => (
                <label className="field" key={field}>
                  <span>
                    Box {index + 1} {field}
                  </span>
                  <input
                    type="number"
                    step="any"
                    min={field === "width" || field === "height" ? 0.000001 : 0}
                    max={field === "x" || field === "width" ? width : height}
                    required
                    value={box[field]}
                    onChange={(event) =>
                      change(index, field, event.target.value)
                    }
                  />
                </label>
              ))}
            </div>
            {!readOnly && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => onChange(boxes.filter((_, i) => i !== index))}
              >
                Remove box {index + 1}
              </Button>
            )}
          </fieldset>
        ))}
      </div>
      {!readOnly && (
        <Button
          type="button"
          variant="secondary"
          disabled={boxes.length >= 100}
          onClick={() =>
            onChange([
              ...boxes,
              {
                label: categories[0],
                x: 0,
                y: 0,
                width: Math.min(100, width / 2),
                height: Math.min(100, height / 2),
              },
            ])
          }
        >
          Add box
        </Button>
      )}
      {!boxes.length && (
        <p className="muted">
          No objects labeled. An accepted empty list explicitly records an image
          with no target objects.
        </p>
      )}
    </>
  );
}
