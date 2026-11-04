"use client";
import * as Dialog from "@radix-ui/react-dialog";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Copy as CopyIcon,
  LoaderCircle,
  X,
} from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/lib/api";

export function Button({
  children,
  variant = "primary",
  busy,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      {...props}
      disabled={props.disabled || busy}
      className={`button ${variant} ${className}`}
    >
      {busy && <LoaderCircle size={14} className="spin" />}
      {children}
    </button>
  );
}
export function Modal({
  open,
  setOpen,
  title,
  description,
  children,
  className = "",
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  title: string;
  description: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className={`modal ${className}`}>
          <div className="modal-heading">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>{description}</Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button className="icon-button" aria-label="Close dialog">
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred.";
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={17} />
      <div>
        {message}
        {error instanceof ApiError && error.requestId && (
          <span className="request-id">Request {error.requestId}</span>
        )}
      </div>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  const positive = [
    "SUCCEEDED",
    "READY",
    "COMPLETED",
    "DELIVERED",
    "PASS",
    "ACCEPTED",
    "ADJUDICATED",
    "FROZEN",
  ].includes(value);
  const negative = [
    "FAILED",
    "REJECTED",
    "DEAD_LETTER",
    "UNAVAILABLE",
    "FAIL",
  ].includes(value);
  return (
    <span
      className={`status ${positive ? "positive" : negative ? "negative" : "neutral"}`}
    >
      <span />
      {value.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}
export function Copy({
  value,
  label = "Copy",
}: {
  value: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  return (
    <button
      className="icon-button"
      aria-label={error ? "Copy failed; select the text manually" : label}
      title={error ? "Select the text and copy manually" : label}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        } catch {
          setError(true);
        }
      }}
    >
      {copied ? <Check size={15} /> : <CopyIcon size={15} />}
    </button>
  );
}
export function Code({ value }: { value: unknown }) {
  const text =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <div className="code-box">
      <Copy value={text} />
      <pre>
        <code>{text}</code>
      </pre>
    </div>
  );
}
export function Empty({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: React.ComponentType<{ size?: number }>;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={23} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="page-actions">{children}</div>
    </div>
  );
}
export function Loading() {
  return (
    <div
      role="status"
      aria-label="Loading content"
      aria-busy="true"
      className="loading-state"
    >
      <div className="skeleton" />
      <div className="skeleton" />
      <div className="skeleton" />
    </div>
  );
}
export function TextLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <a className="text-link" href={href}>
      {children}
      <ArrowUpRight size={14} />
    </a>
  );
}
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function perform<T>(action: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (failure) {
      setError(failure);
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, perform, setError };
}
