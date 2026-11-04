import { Console } from "@/components/console";
import { Suspense } from "react";
export default async function Page({
  params,
}: {
  params: Promise<{ path?: string[] }>;
}) {
  const { path = ["overview"] } = await params;
  return (
    <Suspense fallback={<div role="status" aria-label="Loading workspace" />}>
      <Console path={path} />
    </Suspense>
  );
}
