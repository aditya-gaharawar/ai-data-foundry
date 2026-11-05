"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Box,
  Check,
  ChevronsUpDown,
  CircleHelp,
  Database,
  FileText,
  Gauge,
  GitBranch,
  KeyRound,
  Layers3,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  ShieldCheck,
  Sun,
  Users,
  Webhook,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ApiCall,
  Dataset,
  Organization,
  Page,
  Project,
  SessionInfo,
} from "@/lib/api";
import { request } from "@/lib/api";
import { WorkspaceContext, useWorkspace } from "./context";
import {
  DatasetDetail,
  DatasetsPage,
  OverviewPage,
  RunDetail,
  RunsPage,
} from "./data-pages";
import { WorkflowEditor, WorkflowsPage } from "./workflow";
import {
  AnnotationTaskPage,
  CreateCurationPage,
  CurationDetail,
  CurationsPage,
  QualityProfilesPage,
} from "./curation-pages";
import {
  ApiDocsPage,
  AuditPage,
  KeysPage,
  MembersPage,
  UsagePage,
  WebhooksPage,
} from "./settings";
import { Button, ErrorNotice, Loading, Modal, useAction } from "./ui";
import { TeacherStudio, SimulationStudio } from "./studios";
import { ComputePage } from "./compute-page";
import { EvaluationPage } from "./evaluation-page";
import { GovernancePage } from "./governance-page";
import { OperationsPage } from "./operations-page";

const navigation = [
  {
    label: "Overview",
    href: "/overview",
    icon: LayoutDashboard,
    group: "WORKSPACE",
  },
  { label: "Datasets", href: "/datasets", icon: Database },
  { label: "Curation", href: "/curation", icon: ListChecks },
  { label: "Workflows", href: "/workflows", icon: GitBranch },
  { label: "Runs", href: "/runs", icon: Activity },
  {
    label: "Teacher Studio",
    href: "/teacher",
    icon: FileText,
    group: "BUILD & MEASURE",
  },
  { label: "Simulation Studio", href: "/simulations", icon: Box },
  { label: "Evaluations", href: "/evaluations", icon: ListChecks },
  { label: "Compute", href: "/compute", icon: Layers3 },
  {
    label: "API keys",
    href: "/settings/api-keys",
    icon: KeyRound,
    group: "DEVELOPERS",
    scope: "keys:manage",
  },
  {
    label: "Webhooks",
    href: "/settings/webhooks",
    icon: Webhook,
    scope: "webhooks:manage",
  },
  { label: "API reference", href: "/developers", icon: BookOpen },
  {
    label: "Members",
    href: "/settings/members",
    icon: Users,
    group: "ORGANIZATION",
    scope: "members:manage",
  },
  { label: "Usage & budgets", href: "/settings/usage", icon: Gauge },
  {
    label: "Governance",
    href: "/settings/governance",
    icon: ShieldCheck,
    scope: "governance:manage",
  },
  {
    label: "Operations",
    href: "/operations",
    icon: Activity,
    scope: "operations:manage",
  },
  {
    label: "Audit log",
    href: "/settings/audit",
    icon: ShieldCheck,
    scope: "audit:read",
  },
];

function Brand() {
  return (
    <Link href="/overview" className="brand" aria-label="Foundry overview">
      <span className="brand-symbol">
        <Layers3 size={18} strokeWidth={1.7} />
      </span>
      <span className="brand-word">
        foundry<span style={{ color: "var(--faint)" }}>.</span>
      </span>
    </Link>
  );
}

export function Console({ path }: { path: string[] }) {
  const query = useQuery({
    queryKey: ["session"],
    queryFn: () => request<SessionInfo>("/auth/session"),
    retry: false,
  });
  const [orgId, setOrgId] = useState("");
  useEffect(() => {
    if (query.data) {
      const stored = localStorage.getItem("foundry-org");
      setOrgId(
        query.data.organizations.find((org) => org.id === stored)?.id ||
          query.data.organizations[0]?.id ||
          "",
      );
    }
  }, [query.data]);
  if (query.isPending)
    return (
      <div className="login-form-wrap" style={{ minHeight: "100dvh" }}>
        <Loading />
      </div>
    );
  if (!query.data) return <LoginPage />;
  const organization = query.data.organizations.find((org) => org.id === orgId);
  if (!organization) return <Loading />;
  return (
    <Workspace
      key={organization.id}
      session={query.data}
      organization={organization}
      path={path}
      changeOrganization={(value) => {
        localStorage.setItem("foundry-org", value);
        setOrgId(value);
      }}
    />
  );
}

function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const action = useAction();
  const queryClient = useQueryClient();
  const router = useRouter();
  return (
    <div className="login-page">
      <div className="login-art">
        <Brand />
        <div className="login-message">
          <div className="eyebrow">AI DATA FOUNDRY</div>
          <h1>
            Good models start
            <br />
            with better data.
          </h1>
          <p>
            One workspace to create, validate, and version the data behind your
            next breakthrough.
          </p>
          <div className="detail-meta" style={{ marginTop: 28 }}>
            <ShieldCheck size={15} /> Governed by design. Traceable at every
            step.
          </div>
        </div>
        <div className="login-foot">From source to training-ready.</div>
      </div>
      <div className="login-form-wrap">
        <form
          className="login-form"
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await action.perform(() =>
              request<SessionInfo>("/auth/login", {
                method: "POST",
                body: { email, password },
              }),
            );
            if (result) {
              queryClient.clear();
              queryClient.setQueryData(["session"], result);
              router.replace("/overview");
            }
          }}
        >
          <div className="mobile-brand">
            <Brand />
          </div>
          <div className="eyebrow">YOUR DATA WORKSPACE</div>
          <h1>Welcome to Foundry</h1>
          <p>Sign in to build something worth training on.</p>
          <label className="field">
            <span>Email address</span>
            <input
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              placeholder="Enter your password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <ErrorNotice error={action.error} />
          <Button type="submit" busy={action.busy}>
            Sign in <ArrowRight size={14} />
          </Button>
          <div className="login-disclaimer">
            <span className="local-badge">LOCAL · DEMO DATA</span>
            <p style={{ marginTop: 10 }}>
              Use an account provisioned by your workspace administrator.
              Development credentials are stored in your private local
              configuration.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

function Workspace({
  session,
  organization,
  path,
  changeOrganization,
}: {
  session: SessionInfo;
  organization: Organization;
  path: string[];
  changeOrganization: (value: string) => void;
}) {
  const [project, setProject] = useState("");
  const [message, setMessage] = useState("");
  const [mobile, setMobile] = useState(false);
  const [palette, setPalette] = useState(false);
  const [create, setCreate] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [help, setHelp] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const router = useRouter();
  const queryClient = useQueryClient();
  const call = useCallback<ApiCall>(
    (route, options) =>
      request(route, options, organization.id, session.csrf_token),
    [organization.id, session.csrf_token],
  );
  const projects = useQuery({
    queryKey: [organization.id, "/projects"],
    queryFn: () => call<Page<Project>>("/projects"),
  });
  useEffect(() => {
    if (
      projects.data?.items.length &&
      !projects.data.items.some((item) => item.id === project)
    ) {
      const saved = localStorage.getItem(`foundry-project:${organization.id}`);
      setProject(
        projects.data.items.find((item) => item.id === saved)?.id ||
          projects.data.items[0].id,
      );
    }
  }, [projects.data, project, organization.id]);
  useEffect(() => {
    setCollapsed(localStorage.getItem("foundry-collapsed") === "true");
  }, []);
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(""), 4500);
    return () => clearTimeout(timer);
  }, [message]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette((value) => !value);
      }
      if (
        event.key === "?" &&
        !(event.target instanceof HTMLInputElement) &&
        !(event.target instanceof HTMLTextAreaElement)
      ) {
        setHelp((value) => !value);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const current = "/" + path.join("/");
  const active = navigation.find(
    (item) => current === item.href || current.startsWith(item.href + "/"),
  );
  const allowed = navigation.filter(
    (item) => !item.scope || organization.scopes.includes(item.scope),
  );
  const logout = async () => {
    try {
      await call("/auth/logout", { method: "POST" });
      queryClient.clear();
      router.replace("/login");
    } catch {
      setMessage("Sign-out failed. Please retry.");
    }
  };
  const sidebar = (
    <>
      <Brand />
      <div className="workspace-label">WORKSPACE</div>
      <div className="workspace-box">
        <span className="workspace-avatar">
          {organization.name.slice(0, 1)}
        </span>
        <select
          aria-label="Organization"
          value={organization.id}
          onChange={(event) => changeOrganization(event.target.value)}
        >
          {session.organizations.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name}
            </option>
          ))}
        </select>
        <ChevronsUpDown size={12} />
      </div>
      <div className="project-switch">
        <label className="field">
          <span>Project</span>
          <select
            value={project}
            onChange={(event) => {
              setProject(event.target.value);
              localStorage.setItem(
                `foundry-project:${organization.id}`,
                event.target.value,
              );
            }}
            aria-label="Active project"
          >
            {projects.data?.items.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <nav aria-label="Main navigation">
        {allowed.map((item) => (
          <div key={item.href}>
            {item.group && item.group !== "WORKSPACE" && (
              <div className="nav-label">{item.group}</div>
            )}
            <Link
              href={item.href}
              aria-label={item.label}
              aria-current={active?.href === item.href ? "page" : undefined}
              className={`nav-item ${active?.href === item.href ? "active" : ""}`}
              onClick={() => setMobile(false)}
            >
              <item.icon size={16} />
              <span className="nav-title">{item.label}</span>
            </Link>
          </div>
        ))}
      </nav>
      <div className="sidebar-spacer" />
      <div className="environment-card">
        <div className="environment-title">
          <span className="environment-dot" /> Local workspace
        </div>
        <p>Private by default. No external charges.</p>
      </div>
      <div className="profile">
        <span className="avatar">
          {session.user.name
            .split(" ")
            .map((part) => part[0])
            .slice(0, 2)
            .join("")}
        </span>
        <div className="profile-text">
          <div className="profile-name">{session.user.name}</div>
          <div className="profile-role">{organization.role}</div>
        </div>
        <button className="icon-button" aria-label="Sign out" onClick={logout}>
          <LogOut size={15} />
        </button>
      </div>
    </>
  );
  let page: React.ReactNode;
  if (path[0] === "overview" || path[0] === "login")
    page = <OverviewPage onCreate={() => setCreate(true)} />;
  else if (path[0] === "datasets")
    page = path[1] ? (
      <DatasetDetail id={path[1]} />
    ) : (
      <DatasetsPage onCreate={() => setCreate(true)} />
    );
  else if (path[0] === "curation")
    page =
      path[1] === "profiles" ? (
        <QualityProfilesPage />
      ) : path[1] === "new" ? (
        <CreateCurationPage />
      ) : path[1] === "tasks" && path[2] ? (
        <AnnotationTaskPage id={path[2]} />
      ) : path[1] ? (
        <CurationDetail id={path[1]} />
      ) : (
        <CurationsPage />
      );
  else if (path[0] === "workflows")
    page = path[1] ? <WorkflowEditor id={path[1]} /> : <WorkflowsPage />;
  else if (path[0] === "runs")
    page = path[1] ? <RunDetail id={path[1]} /> : <RunsPage />;
  else if (path[0] === "developers") page = <ApiDocsPage />;
  else if (path[0] === "teacher") page = <TeacherStudio />;
  else if (path[0] === "simulations") page = <SimulationStudio />;
  else if (path[0] === "compute") page = <ComputePage />;
  else if (path[0] === "evaluations") page = <EvaluationPage />;
  else if (path[0] === "operations") page = <OperationsPage />;
  else if (path[0] === "settings" && path[1] === "governance")
    page = <GovernancePage />;
  else if (path[0] === "settings" && path[1] === "api-keys")
    page = <KeysPage />;
  else if (path[0] === "settings" && path[1] === "webhooks")
    page = <WebhooksPage />;
  else if (path[0] === "settings" && path[1] === "members")
    page = <MembersPage />;
  else if (path[0] === "settings" && path[1] === "usage") page = <UsagePage />;
  else if (path[0] === "settings" && path[1] === "audit") page = <AuditPage />;
  else
    page = (
      <div className="empty">
        <h1>Page not found</h1>
        <p>This workspace page does not exist.</p>
        <Link className="button secondary" href="/overview">
          Back to overview
        </Link>
      </div>
    );
  const context = useMemo(
    () => ({
      call,
      organization,
      project,
      projects: projects.data?.items || [],
      session,
      toast: setMessage,
    }),
    [call, organization, project, projects.data, session],
  );
  if (active?.scope && !organization.scopes.includes(active.scope)) {
    page = (
      <>
        <h1>Access restricted</h1>
        <ErrorNotice
          error={new Error(`This action requires ${active.scope}.`)}
        />
      </>
    );
  }
  return (
    <WorkspaceContext value={context}>
      <div className={`shell ${collapsed ? "is-collapsed" : ""}`}>
        <a href="#main-content" className="skip-link">
          Skip to content
        </a>
        <aside
          className="sidebar desktop-sidebar"
          aria-label="Workspace navigation"
        >
          {sidebar}
        </aside>
        <div className="main-wrap">
          <header className="topbar">
            <div className="breadcrumbs">
              <button
                className="icon-button mobile-toggle"
                aria-label="Open navigation"
                onClick={() => setMobile(true)}
              >
                <Menu size={18} />
              </button>
              <button
                className="icon-button collapse-toggle"
                aria-label={
                  collapsed ? "Expand navigation" : "Collapse navigation"
                }
                onClick={() => {
                  setCollapsed(!collapsed);
                  localStorage.setItem("foundry-collapsed", String(!collapsed));
                }}
              >
                {collapsed ? (
                  <PanelLeftOpen size={15} />
                ) : (
                  <PanelLeftClose size={15} />
                )}
              </button>
              <span className="org-crumb">{organization.name}</span>
              <span className="org-crumb">/</span>
              <span>{active?.label || "Workspace"}</span>
            </div>
            <div className="topbar-actions">
              <div className="search-container">
                <button
                  className="search-trigger"
                  onClick={() => setPalette(true)}
                  aria-label="Search workspace"
                >
                  <Search size={13} />
                  <span>Search workspace</span>
                </button>
                <kbd aria-hidden="true">⌘ K</kbd>
              </div>
              <button
                className="icon-button"
                aria-label="Toggle color theme"
                onClick={() =>
                  setTheme(resolvedTheme === "dark" ? "light" : "dark")
                }
              >
                {resolvedTheme === "dark" ? (
                  <Sun size={15} />
                ) : (
                  <Moon size={15} />
                )}
              </button>
              <span className="local-badge">LOCAL · DEMO DATA</span>
            </div>
          </header>
          <main className="content" id="main-content">
            <ErrorNotice error={projects.error} />
            {page}
            <footer className="page-footer">
              <span>
                <Box size={12} /> AI Data Foundry{" "}
                <span className="mono" style={{ fontSize: 9 }}>
                  v0.1
                </span>
              </span>
              <div style={{ display: "flex", gap: 16 }}>
                <Link href="/developers">Documentation</Link>
                <button
                  className="text-link"
                  style={{
                    border: 0,
                    background: "transparent",
                    padding: 0,
                    fontSize: 10,
                  }}
                  onClick={() => setHelp(true)}
                >
                  <CircleHelp size={12} /> Keyboard shortcuts
                </button>
              </div>
            </footer>
          </main>
        </div>
        <Modal
          open={mobile}
          setOpen={setMobile}
          title="Workspace navigation"
          description="Navigate your workspace"
          className="mobile-menu"
        >
          <aside className="sidebar" aria-label="Workspace navigation">
            {sidebar}
          </aside>
        </Modal>
        <CommandPalette open={palette} setOpen={setPalette} items={allowed} />
        <CreateDataset open={create} setOpen={setCreate} />
        <Modal
          open={help}
          setOpen={setHelp}
          title="Keyboard shortcuts"
          description="Move through your workspace without leaving the keyboard."
        >
          <dl className="key-values">
            <dt>Search and navigate</dt>
            <dd>⌘ / Ctrl + K</dd>
            <dt>Show this guide</dt>
            <dd>?</dd>
            <dt>Close a dialog</dt>
            <dd>Escape</dd>
            <dt>Move between controls</dt>
            <dd>Tab / Shift + Tab</dd>
          </dl>
        </Modal>
        {message && (
          <div className="toast" role="status">
            <Check size={16} />
            {message}
          </div>
        )}
      </div>
    </WorkspaceContext>
  );
}

function CreateDataset({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (value: boolean) => void;
}) {
  const { call, projects, project, toast } = useWorkspace();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rights, setRights] = useState(false);
  const [modality, setModality] = useState("text");
  const [selected, setSelected] = useState("");
  const action = useAction();
  return (
    <Modal
      open={open}
      setOpen={setOpen}
      title="Create a dataset"
      description="A versioned home for your training data."
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const result = await action.perform(() =>
            call<Dataset>("/datasets", {
              method: "POST",
              body: {
                name,
                description,
                project_id: selected || project,
                modality,
                policy: {
                  origin: "local",
                  license: "user-declared-local",
                  allowed_training_use: rights,
                },
              },
            }),
          );
          if (result) {
            setOpen(false);
            setName("");
            setDescription("");
            setRights(false);
            queryClient.invalidateQueries();
            toast("Dataset created.");
            router.push(`/datasets/${result.id}`);
          }
        }}
      >
        <label className="field">
          <span>Dataset name</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            maxLength={160}
            placeholder="e.g. Reasoning instruction set"
          />
        </label>
        <label className="field">
          <span>
            Description <small style={{ display: "inline" }}>(optional)</small>
          </span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What will this dataset help your model learn?"
            maxLength={4000}
          />
        </label>
        <div className="field-row">
          <label className="field">
            <span>Project</span>
            <select
              value={selected || project}
              onChange={(event) => setSelected(event.target.value)}
              required
            >
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Modality</span>
            <select
              value={modality}
              onChange={(event) => setModality(event.target.value)}
              aria-label="Modality"
            >
              <option value="text">Text · JSONL</option>
              <option value="image">Image · PNG/JPEG</option>
            </select>
          </label>
        </div>
        <label className="check-field">
          <input
            type="checkbox"
            checked={rights}
            onChange={(event) => setRights(event.target.checked)}
            required
          />
          <span>
            I have permission to process this source data and use it for the
            intended training purpose.
          </span>
        </label>
        <ErrorNotice error={action.error} />
        <div className="modal-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            busy={action.busy}
            disabled={!project || !rights}
          >
            <Plus size={14} />
            Create dataset
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function CommandPalette({
  open,
  setOpen,
  items,
}: {
  open: boolean;
  setOpen: (value: boolean) => void;
  items: typeof navigation;
}) {
  const { call, organization } = useWorkspace();
  const [search, setSearch] = useState("");
  const data = useQuery({
    queryKey: [organization.id, "command", search],
    queryFn: () =>
      call<Page<Dataset>>(`/datasets?q=${encodeURIComponent(search)}&limit=5`),
    enabled: open && search.length > 1,
  });
  return (
    <Modal
      open={open}
      setOpen={setOpen}
      title="Search workspace"
      description="Find a page or search your datasets."
    >
      <input
        className="command-input"
        autoFocus
        aria-label="Search pages and datasets"
        placeholder="Where would you like to go?"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      <div className="command-results">
        {items
          .filter((item) =>
            item.label.toLowerCase().includes(search.toLowerCase()),
          )
          .map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
            >
              <item.icon size={15} />
              {item.label}
              <small>Page</small>
            </Link>
          ))}
        {data.data?.items.map((item) => (
          <Link
            key={item.id}
            href={`/datasets/${item.id}`}
            onClick={() => setOpen(false)}
          >
            <Database size={15} />
            {item.name}
            <small>Dataset</small>
          </Link>
        ))}
        <ErrorNotice error={data.error} />
      </div>
      <p className="keyboard-hint">
        Tab to move · Enter to open · Escape to close
      </p>
    </Modal>
  );
}
