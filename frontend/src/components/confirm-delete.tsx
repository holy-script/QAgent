"use client";
import { useState, type ReactNode } from "react";
import { Button, inputCls } from "@/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

/**
 * A "are you sure" dialog for destructive actions. Pass `confirmText` to make the user type it first
 * (used for deleting a whole app).
 */
export function ConfirmDelete({ open, onOpenChange, title, children, confirmText, actionLabel, onConfirm, pending, error }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; children: ReactNode; confirmText?: string;
  actionLabel: string; onConfirm: () => void; pending?: boolean; error?: string;
}) {
  const [typed, setTyped] = useState("");
  const ready = !confirmText || typed.trim() === confirmText;
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setTyped(""); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription render={<div />} className="space-y-2 text-sm">{children}</DialogDescription>
        </DialogHeader>
        {confirmText && (
          <label className="block space-y-1.5 text-sm">
            <span>Type <b>{confirmText}</b> to confirm</span>
            <input className={inputCls} value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus aria-label="Type the name to confirm" />
          </label>
        )}
        {error && <p role="alert" className="text-sm text-bad">{error}</p>}
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="danger" disabled={!ready || pending} onClick={onConfirm}>{pending ? "Deleting…" : actionLabel}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
