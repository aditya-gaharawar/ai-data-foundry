"use client";
import { createContext, useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ApiCall, Organization, Project, SessionInfo } from "@/lib/api";

type AuthContext = {
  call: ApiCall;
  organization: Organization;
  project: string;
  projects: Project[];
  session: SessionInfo;
  toast: (value: string) => void;
};
export const WorkspaceContext = createContext<AuthContext | null>(null);
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("Workspace provider is missing.");
  return value;
}
export function useResource<T>(path: string, poll = false, enabled = true) {
  const { call, organization } = useWorkspace();
  return useQuery({
    queryKey: [organization.id, path],
    queryFn: () => call<T>(path),
    enabled,
    refetchInterval: poll ? 2000 : false,
  });
}
