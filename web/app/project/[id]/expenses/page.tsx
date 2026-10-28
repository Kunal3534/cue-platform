"use client";
import { useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getExpenses,
  getEditorialSchedule,
  createExpense,
  uploadExpenseReceipt,
  updateExpense,
  deleteExpense,
  rereadExpenseReceipt,
  expenseReceiptUrl,
  expenseReportUrl,
  exportReportToSlides,
  getMe,
} from "@/lib/api";
import type { ExpenseItem, ExpensePatch } from "@/lib/api/types";
import ReceiptScanner from "@/components/editorial/ReceiptScanner";

const CATEGORY_LABELS: Record<string, string> = {
  travel: "Travel",
  food: "Food & catering",
  location: "Location",
  equipment: "Equipment",
  styling: "Styling",
  hmu: "Hair & makeup",
  production: "Production",
  misc: "Miscellaneous",
};

function inr(n: number): string {
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

function StatusChip({ status }: { status: ExpenseItem["status"] }) {
  if (status === "processing") return <ReceiptScanner />;
  if (status === "needs_review")
    return <span className="gq-exp-status gq-exp-status--review">Check details</span>;
  return null;
}

/** Inline edit form for one expense. */
function ExpenseEditor({
  item,
  dayOptions,
  categories,
  onSave,
  onCancel,
}: {
  item: ExpenseItem;
  dayOptions: { date: string; label: string }[];
  categories: string[];
  onSave: (patch: ExpensePatch) => Promise<void>;
  onCancel: () => void;
}) {
  const [vendor, setVendor] = useState(item.vendor ?? "");
  const [description, setDescription] = useState(item.description ?? "");
  const [amount, setAmount] = useState(item.amount != null ? String(item.amount) : "");
  const [category, setCategory] = useState(item.category ?? "misc");
  const [date, setDate] = useState(item.date ?? "");
  const [notes, setNotes] = useState(item.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  const save = async () => {
    const parsed = amount.trim() === "" ? null : Number(amount.replace(/[,₹\s]/g, ""));
    if (parsed !== null && Number.isNaN(parsed)) {
      setError(true);
      return;
    }
    setSaving(true);
    setError(false);
    try {
      await onSave({
        vendor: vendor.trim() || null,
        description: description.trim() || null,
        amount: parsed,
        category,
        notes: notes.trim() || null,
        ...(date ? { date } : { clear_date: true }),
      });
    } catch {
      setError(true);
      setSaving(false);
    }
  };

  return (
    <div className="gq-exp-edit">
      <div className="gq-form__grid">
        <div>
          <label className="gq-label">Paid to</label>
          <input className="gq-input" value={vendor} placeholder="Vendor / store"
                 onChange={(e) => setVendor(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">What for</label>
          <input className="gq-input" value={description} placeholder="What was this spend?"
                 onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Amount (₹)</label>
          <input className="gq-input" inputMode="decimal" value={amount} placeholder="0.00"
                 onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Category</label>
          <select className="gq-input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABELS[c] ?? c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="gq-label">Shoot</label>
          <select className="gq-input" value={date} onChange={(e) => setDate(e.target.value)}>
            <option value="">General — no specific shoot</option>
            {dayOptions.map((d) => (
              <option key={d.date} value={d.date}>{d.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="gq-label">Notes</label>
          <input className="gq-input" value={notes} placeholder="Anything accounts should know"
                 onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
      {error && (
        <p style={{ color: "#C33", fontSize: 12, marginTop: 8 }}>
          Could not save — check the amount and try again.
        </p>
      )}
      <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
        <button type="button" className="gq-btn" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" className="gq-btn gq-btn--ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function ExpensesPage() {
  const params = useParams();
  const projectId = params.id as string;
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["expenses", projectId],
    queryFn: () => getExpenses(projectId),
    // Keep polling while any receipt is still being read
    refetchInterval: (query) =>
      query.state.data?.items.some((i) => i.status === "processing") ? 4000 : false,
  });
  const { data: schedule } = useQuery({
    queryKey: ["editorial-schedule", projectId],
    queryFn: () => getEditorialSchedule(projectId),
  });

  const dayOptions = (schedule?.days ?? []).map((d) => ({
    date: d.date,
    label: `${fmtDay(d.date)}${d.headline ? ` — ${d.headline}` : ""}`,
  }));

  const [uploadDate, setUploadDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [slidesBusy, setSlidesBusy] = useState(false);
  const [slidesError, setSlidesError] = useState<string | null>(null);
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: 60_000 });

  const openAsSlides = async () => {
    setSlidesBusy(true);
    setSlidesError(null);
    try {
      const { url } = await exportReportToSlides(projectId);
      window.open(url, "_blank", "noopener");
    } catch (e) {
      setSlidesError(e instanceof Error ? e.message : "Could not create the Slides deck");
    } finally {
      setSlidesBusy(false);
    }
  };

  const refresh = () => qc.invalidateQueries({ queryKey: ["expenses", projectId] });

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    try {
      for (const file of Array.from(files)) {
        await uploadExpenseReceipt(projectId, file, uploadDate || null);
      }
      await refresh();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed — try again");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (isLoading || !data) {
    return <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>;
  }

  // Group by shoot day; untagged items go last
  const groups = new Map<string, ExpenseItem[]>();
  for (const item of data.items) {
    const key = item.date ?? "general";
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  const orderedKeys = [
    ...[...groups.keys()].filter((k) => k !== "general").sort(),
    ...(groups.has("general") ? ["general"] : []),
  ];

  const headlineFor = (date: string) =>
    schedule?.days.find((d) => d.date === date)?.headline ?? null;

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <div className="gq-detail__date">Expenses</div>
      <div className="gq-detail__headline">Shoot spend tracker</div>
      <p className="gq-exp-note">
        Only producers see this — it never appears on any share link. Upload
        receipt or bill photos and Cue reads the amounts for you, or add
        expenses by hand.
      </p>

      {/* Totals */}
      <div className="gq-exp-totals">
        <div className="gq-exp-grand">
          <span className="gq-exp-grand__label">Total spend</span>
          <span className="gq-exp-grand__num">{inr(data.totals.grand)}</span>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {me?.google_calendar_connected && (
            <button type="button" className="gq-btn" onClick={openAsSlides} disabled={slidesBusy}>
              {slidesBusy ? "Creating Slides…" : "Open as Google Slides"}
            </button>
          )}
          <a className={`gq-btn${me?.google_calendar_connected ? " gq-btn--ghost" : ""}`}
             href={expenseReportUrl(projectId)} download>
            Download .pptx
          </a>
        </div>
      </div>
      {slidesError && (
        <p style={{ color: "#C33", fontSize: 12, marginTop: 8 }}>{slidesError}</p>
      )}
      <p className="gq-exp-note" style={{ marginTop: 6 }}>
        {me?.google_calendar_connected
          ? "One click drops the deck into your Google Drive as native Slides, ready for the accounts team."
          : "The report is a .pptx — drop it into Google Drive and it opens as Google Slides, ready for the accounts team."}
      </p>

      {/* Upload */}
      <div className="gq-form__sec">Add a receipt</div>
      <div className="gq-form__grid">
        <div>
          <label className="gq-label">Which shoot is this for?</label>
          <select className="gq-input" value={uploadDate} onChange={(e) => setUploadDate(e.target.value)}>
            <option value="">General — no specific shoot</option>
            {dayOptions.map((d) => (
              <option key={d.date} value={d.date}>{d.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="gq-label">Receipt photos or PDFs</label>
          <input
            ref={fileRef}
            className="gq-input"
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            multiple
            disabled={uploading}
            onChange={(e) => void handleFiles(e.target.files)}
          />
        </div>
      </div>
      {uploading && (
        <p style={{ marginTop: 12 }}>
          <ReceiptScanner label="Uploading receipts…" />
        </p>
      )}
      {uploadError && (
        <p style={{ color: "#C33", fontSize: 12, marginTop: 8 }}>{uploadError}</p>
      )}

      {/* Manual entry */}
      <div style={{ marginTop: 18 }}>
        {adding ? (
          <>
            <div className="gq-form__sec">Add an expense by hand</div>
            <ExpenseEditor
              item={{
                id: "", date: uploadDate || null, vendor: null, description: null,
                category: "misc", amount: null, currency: "INR", source: "manual",
                has_receipt: false, filename: null, content_type: null,
                status: "ready", extracted: null, notes: null, created_by: null,
                created_at: "",
              }}
              dayOptions={dayOptions}
              categories={data.categories}
              onSave={async (patch) => {
                await createExpense(projectId, patch);
                setAdding(false);
                await refresh();
              }}
              onCancel={() => setAdding(false)}
            />
          </>
        ) : (
          <button type="button" className="gq-btn gq-btn--ghost"
                  style={{ padding: "9px 16px", fontSize: 10 }}
                  onClick={() => setAdding(true)}>
            + Add an expense without a receipt
          </button>
        )}
      </div>

      {/* Grouped list */}
      {data.items.length === 0 ? (
        <p style={{ color: "#999", marginTop: 40, textAlign: "center" }}>
          No expenses yet — upload the first receipt above.
        </p>
      ) : (
        orderedKeys.map((key) => {
          const items = groups.get(key)!;
          const subtotal = data.totals.by_date[key] ?? 0;
          return (
            <div key={key} style={{ marginTop: 36 }}>
              <div className="gq-exp-group">
                <span>
                  {key === "general"
                    ? "General"
                    : `${fmtDay(key)}${headlineFor(key) ? ` — ${headlineFor(key)}` : ""}`}
                </span>
                <span className="gq-exp-group__total">{inr(subtotal)}</span>
              </div>
              {items.map((item) =>
                editingId === item.id ? (
                  <ExpenseEditor
                    key={item.id}
                    item={item}
                    dayOptions={dayOptions}
                    categories={data.categories}
                    onSave={async (patch) => {
                      await updateExpense(projectId, item.id, patch);
                      setEditingId(null);
                      await refresh();
                    }}
                    onCancel={() => setEditingId(null)}
                  />
                ) : (
                  <div key={item.id} className="gq-exp-row">
                    <div className="gq-exp-row__main">
                      <div className="gq-exp-row__vendor">
                        {item.vendor || item.description || item.filename || "Untitled expense"}
                        <StatusChip status={item.status} />
                      </div>
                      <div className="gq-exp-row__sub">
                        {[
                          item.vendor && item.description ? item.description : null,
                          item.category ? (CATEGORY_LABELS[item.category] ?? item.category) : null,
                          item.notes,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </div>
                      <div className="gq-exp-row__actions">
                        {item.status === "needs_review" && item.amount != null && (
                          <button
                            type="button"
                            className="gq-exp-approve"
                            onClick={async () => {
                              await updateExpense(projectId, item.id, { approve: true });
                              await refresh();
                            }}
                          >
                            Approve ✓
                          </button>
                        )}
                        {item.has_receipt && (
                          <a href={expenseReceiptUrl(projectId, item.id)} target="_blank" rel="noreferrer">
                            View receipt ↗
                          </a>
                        )}
                        {item.has_receipt && item.status === "needs_review" && (
                          <button
                            type="button"
                            onClick={async () => {
                              await rereadExpenseReceipt(projectId, item.id);
                              await refresh();
                            }}
                          >
                            Read again
                          </button>
                        )}
                        <button type="button" onClick={() => setEditingId(item.id)}>Edit</button>
                        <button
                          type="button"
                          onClick={async () => {
                            if (!window.confirm("Delete this expense?")) return;
                            await deleteExpense(projectId, item.id);
                            await refresh();
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                    <div className="gq-exp-row__amt">
                      {item.amount != null ? inr(item.amount) : "—"}
                    </div>
                  </div>
                ),
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
