import { useCallback, useEffect, useRef, useState } from "react";

import { api, errorText } from "../api/client";
import type {
  ApplicationDetail,
  ApplicationStatus,
  ApplicationSummary,
  AuthUser,
  Company,
  Feed as FeedData,
  Preapproval,
  Product,
  PurposeCategory,
} from "../api/types";
import { money } from "../utils/format";
import { usePolling } from "../utils/hooks";
import { IN_PROGRESS, PRODUCT_NAMES } from "../utils/labels";
import CreditApplicationForm from "./CreditApplicationForm";
import Feed from "./Feed";
import MyApplications from "./MyApplications";
import ProductCatalog, { type Preset } from "./ProductCatalog";

type Tab = "applications" | "products" | "feed";

type FormState = {
  product: Product;
  purpose: PurposeCategory | null;
  draft?: ApplicationDetail;
  /** Amount and term of a pre-approved offer. */
  preset?: Preset;
};

type Toast = { id: number; text: string };

function toSummary(d: ApplicationDetail): ApplicationSummary {
  return {
    id: d.id,
    status: d.status,
    status_label: d.status_label,
    client_stage: d.client_stage,
    stage_label: d.stage_label,
    product_id: d.product_id,
    amount: d.amount,
    term_months: d.term_months,
    company_inn: d.company_inn,
    company_name: d.company_name,
    risk_class: d.risk_class,
    created_at: d.created_at,
    updated_at: d.updated_at,
  };
}

export default function ClientCabinet({ user }: { user: AuthUser }) {
  const [tab, setTab] = useState<Tab | null>(null);
  const [applications, setApplications] = useState<ApplicationSummary[] | null>(null);
  const [details, setDetails] = useState<Record<string, ApplicationDetail>>({});
  const [products, setProducts] = useState<Product[]>([]);
  const [company, setCompany] = useState<Company | null>(null);
  const [preapproval, setPreapproval] = useState<Preapproval | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [feed, setFeed] = useState<FeedData | null>(null);
  const [feedError, setFeedError] = useState("");
  const [unread, setUnread] = useState(0);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [error, setError] = useState("");

  const detailsRef = useRef(details);
  const statusesRef = useRef<Record<string, ApplicationStatus>>({});
  const toastSeq = useRef(0);

  useEffect(() => {
    detailsRef.current = details;
  }, [details]);

  const pushToast = useCallback((text: string) => {
    toastSeq.current += 1;
    const id = toastSeq.current;
    setToasts((current) => [...current, { id, text }]);
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 6000);
  }, []);

  const loadApplications = useCallback(async () => {
    try {
      const items = await api.applications();
      const previous = statusesRef.current;
      for (const item of items) {
        const before = previous[item.id];
        if (before !== undefined && before !== item.status) {
          pushToast(`${PRODUCT_NAMES[item.product_id]} на ${money(item.amount)}: ${item.status_label}`);
        }
      }
      statusesRef.current = Object.fromEntries(items.map((a) => [a.id, a.status]));
      setApplications(items);
      setTab((current) => current ?? (items.length > 0 ? "applications" : "products"));

      const stale = items.filter((a) => detailsRef.current[a.id]?.updated_at !== a.updated_at);
      if (stale.length > 0) {
        const fresh = await Promise.all(stale.map((a) => api.application(a.id)));
        setDetails((current) => {
          const next = { ...current };
          for (const d of fresh) next[d.id] = d;
          return next;
        });
      }
      setError("");
    } catch (caught) {
      setError(errorText(caught));
    }
  }, [pushToast]);

  const loadFeed = useCallback(async () => {
    try {
      const data = await api.feed();
      setFeed(data);
      setUnread(data.unread_events);
      setFeedError("");
    } catch (caught) {
      setFeedError(errorText(caught));
    }
  }, []);

  useEffect(() => {
    void loadApplications();
    void loadFeed();
    api
      .products()
      .then(setProducts)
      .catch(() => undefined);
    // Without a pre-approval (sources down, no data) the catalog simply has no offer block.
    api
      .preapproved()
      .then(setPreapproval)
      .catch(() => undefined);
    if (user.company_inn) {
      api
        .company(user.company_inn)
        .then(setCompany)
        .catch(() => undefined);
    }
  }, [loadApplications, loadFeed, user.company_inn]);

  // Fast polling while the bank's pipeline works on something, slow otherwise.
  const working =
    applications?.some((a) => IN_PROGRESS.includes(a.status) || details[a.id]?.waiting_external) ??
    false;
  usePolling(loadApplications, working ? 2000 : 8000);
  usePolling(loadFeed, 10000);

  useEffect(() => {
    if (tab !== "feed" || unread === 0) return undefined;
    const timer = window.setTimeout(() => {
      api
        .markFeedRead()
        .then(() => setUnread(0))
        .catch(() => undefined);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [tab, unread]);

  useEffect(() => {
    if (!highlightId || tab !== "applications") return undefined;
    const frame = window.requestAnimationFrame(() =>
      document
        .getElementById(`application-${highlightId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
    const timer = window.setTimeout(() => setHighlightId(null), 4000);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [highlightId, tab]);

  function handleChanged(detail: ApplicationDetail) {
    statusesRef.current = { ...statusesRef.current, [detail.id]: detail.status };
    setDetails((current) => ({ ...current, [detail.id]: detail }));
    setApplications((current) => {
      const list = current ?? [];
      const summary = toSummary(detail);
      return list.some((a) => a.id === detail.id)
        ? list.map((a) => (a.id === detail.id ? summary : a))
        : [summary, ...list];
    });
    void loadFeed();
  }

  function openApplication(id: string) {
    setForm(null);
    setTab("applications");
    setHighlightId(id);
  }

  function editDraft(draft: ApplicationDetail) {
    const product = products.find((p) => p.id === draft.product_id);
    if (!product) {
      setError("Не удалось загрузить параметры продукта. Обновите страницу.");
      return;
    }
    setForm({ product, purpose: draft.purpose_category, draft });
  }

  function switchTab(next: Tab) {
    setForm(null);
    setTab(next);
    if (next === "feed") void loadFeed();
  }

  const active = applications?.filter((a) => a.client_stage !== "completed").length ?? 0;

  return (
    <div className="cabinet">
      <div className="tabs-bar">
        <nav className="tabs container" role="tablist" aria-label="Разделы кабинета">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "applications" && !form}
            className="tab"
            onClick={() => switchTab("applications")}
          >
            Мои заявки{active > 0 && <span className="tab__count">{active}</span>}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "products" || Boolean(form)}
            className="tab"
            onClick={() => switchTab("products")}
          >
            Кредитные продукты
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "feed" && !form}
            className="tab"
            onClick={() => switchTab("feed")}
          >
            Уведомления{unread > 0 && <span className="tab__badge">{unread}</span>}
          </button>
        </nav>
      </div>

      <div className="container page">
        {error && (
          <p className="form-error banner" role="alert">
            {error}
          </p>
        )}

        {form ? (
          <CreditApplicationForm
            key={form.draft?.id ?? form.product.id}
            product={form.product}
            purpose={form.purpose}
            company={company}
            draft={form.draft}
            preset={form.preset}
            onCancel={() => setForm(null)}
            onDone={(detail, submitted) => {
              setForm(null);
              handleChanged(detail);
              pushToast(submitted ? "Заявка отправлена, банк начал проверку" : "Черновик сохранён");
              openApplication(detail.id);
            }}
          />
        ) : tab === null || (tab === "applications" && applications === null) ? (
          <section className="card">
            <p className="muted">Загружаем заявки…</p>
          </section>
        ) : tab === "applications" ? (
          <MyApplications
            applications={applications ?? []}
            details={details}
            highlightId={highlightId}
            onChanged={handleChanged}
            onEdit={editDraft}
            onNew={() => switchTab("products")}
          />
        ) : tab === "products" ? (
          <ProductCatalog
            offers={preapproval?.offers ?? []}
            onApply={(product, purpose, preset) => setForm({ product, purpose, preset })}
          />
        ) : (
          <Feed feed={feed} error={feedError} onOpenApplication={openApplication} />
        )}
      </div>

      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className="toast">
            {toast.text}
          </div>
        ))}
      </div>
    </div>
  );
}
