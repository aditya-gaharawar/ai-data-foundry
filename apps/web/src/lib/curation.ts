import type { components } from "../../../../packages/sdk-ts/src/schema";

export type QualityProfile = components["schemas"]["QualityProfileOut"];
export type Curation = components["schemas"]["CurationOut"] & {
  quality?: CurationQuality | null;
};
export type CurationQuality = {
  passed: boolean;
  reasons: string[];
  total: number;
  eligible: number;
  accepted: number;
  rejected: number;
  excluded: number;
  pending: number;
  invalid: number;
  review_coverage: number;
  agreement: { paired_tasks: number; agreed: number; ratio: number | null };
  limitations: string[];
};
export type Box = {
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
};
export type Annotation =
  | { kind: "category"; label: string }
  | { kind: "boxes"; boxes: Box[] };
export type Review = {
  id: string;
  user_id: string;
  round: number;
  decision: string;
  annotation: Annotation | null;
  note: string;
  created_at: string;
};
export type Task = Omit<
  components["schemas"]["AnnotationTaskOut"],
  "annotation" | "payload" | "reviews"
> & {
  annotation: Annotation | null;
  payload: {
    image?: { width: number; height: number };
    [key: string]: unknown;
  };
  reviews: Review[];
};
export type Reviewer = { id: string; name: string; role: string };
export const cardFields = [
  ["purpose", "Purpose"],
  ["intended_use", "Intended training use"],
  ["limitations", "Known limitations"],
  ["content_risks", "Content risks"],
  ["restrictions", "Use restrictions"],
] as const;
