"use client";

import { ChangeEvent, FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getStoredDocuments, storedDocumentDownloadUrl, uploadDocument, type IngestedDocument, type StoredDocument } from "@/services/documents";
import {
  connectVectorStore,
  deleteCollectionChunk,
  getCollectionChunks,
  getVectorStoreCollections,
  getVectorStoreConnection,
  searchCollectionChunks,
  type CollectionSearchMode,
  type VectorCollection,
  type VectorChunk,
  type VectorStoreConnection,
  type VectorStoreConnectionInput,
  type VectorStoreProvider,
} from "@/services/vector-store";

type View = "chat" | "knowledge" | "cloud";

type IconProps = { className?: string };

function Icon({ children, className = "" }: IconProps & { children: ReactNode }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className={`fill-none stroke-current stroke-[1.8] ${className}`}>
      {children}
    </svg>
  );
}

const ChatIcon = ({ className }: IconProps) => (
  <Icon className={className}><path d="M20 14a4 4 0 0 1-4 4H9l-5 3v-7a4 4 0 0 1-1-2.6V7a4 4 0 0 1 4-4h9a4 4 0 0 1 4 4Z" strokeLinecap="round" strokeLinejoin="round" /></Icon>
);

const DatabaseIcon = ({ className }: IconProps) => (
  <Icon className={className}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" strokeLinecap="round" /></Icon>
);

const CloudIcon = ({ className }: IconProps) => (
  <Icon className={className}><path d="M7.5 18H18a4 4 0 0 0 .5-8 6.5 6.5 0 0 0-12.4-1.7A5 5 0 0 0 7.5 18Z" strokeLinecap="round" strokeLinejoin="round" /></Icon>
);

const SparkIcon = ({ className }: IconProps) => (
  <svg aria-hidden="true" viewBox="0 0 24 24" className={`fill-current ${className ?? ""}`}><path d="M12 0c.8 7.7 4.3 11.2 12 12-7.7.8-11.2 4.3-12 12C11.2 16.3 7.7 12.8 0 12 7.7 11.2 11.2 7.7 12 0Z" /></svg>
);

const SearchIcon = ({ className }: IconProps) => (
  <Icon className={className}><circle cx="11" cy="11" r="7" /><path d="m16 16 4 4" strokeLinecap="round" /></Icon>
);

const SendIcon = ({ className }: IconProps) => (
  <Icon className={className}><path d="m4 4 16 8-16 8 3-8-3-8Z" strokeLinecap="round" strokeLinejoin="round" /><path d="M7 12h13" /></Icon>
);

const MenuIcon = ({ className }: IconProps) => (
  <Icon className={className}><path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" /></Icon>
);

const CloseIcon = ({ className }: IconProps) => (
  <Icon className={className}><path d="m6 6 12 12M18 6 6 18" strokeLinecap="round" /></Icon>
);

const navigation: { id: View; label: string; shortLabel: string; icon: (props: IconProps) => ReactNode }[] = [
  { id: "chat", label: "Chat", shortLabel: "Chat", icon: ChatIcon },
  { id: "knowledge", label: "Manage Knowledge Base", shortLabel: "Knowledge", icon: DatabaseIcon },
  { id: "cloud", label: "Cloud", shortLabel: "Cloud", icon: CloudIcon },
];

const viewDetails: Record<View, { eyebrow: string; title: string; description: string }> = {
  chat: { eyebrow: "Research notes", title: "Ask your knowledge", description: "Answers grounded in 12 indexed documents" },
  knowledge: { eyebrow: "Data connection", title: "Manage knowledge base", description: "Connect and configure your vector database" },
  cloud: { eyebrow: "Document library", title: "Your cloud", description: "All documents available to your knowledge base" },
};

const databaseProviders = [
  { id: "chroma_self_hosted", name: "Self-hosted Chroma", detail: "Your own Chroma server", mark: "CH", color: "bg-primary-50 text-primary-700" },
  { id: "chroma_cloud", name: "Chroma Cloud", detail: "Managed Chroma database", mark: "CC", color: "bg-[#e8f0ff] text-[#315eb0]" },
  { id: "pinecone_cloud", name: "Pinecone Cloud", detail: "Managed Pinecone index", mark: "PC", color: "bg-secondary-200 text-secondary-900" },
  { id: "qdrant_self_hosted", name: "Self-hosted Qdrant", detail: "Your own Qdrant server", mark: "QD", color: "bg-[#ffebe8] text-[#b63d35]" },
  { id: "qdrant_cloud", name: "Qdrant Cloud", detail: "Managed Qdrant cluster", mark: "QC", color: "bg-[#e6f7f0] text-[#167052]" },
] as const;

// Keyboard map: Enter/Space/ArrowDown opens; Arrow keys move; Home/End jump;
// Enter/Space selects; Escape closes and returns focus to the trigger.
function ProviderSelect({ value, onChange }: { value: VectorStoreProvider; onChange: (provider: VectorStoreProvider) => void }) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const selected = databaseProviders.find((provider) => provider.id === value) ?? databaseProviders[0];

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  function openList() {
    const selectedIndex = databaseProviders.findIndex((provider) => provider.id === value);
    setActiveIndex(selectedIndex);
    setOpen(true);
    requestAnimationFrame(() => optionRefs.current[selectedIndex]?.focus());
  }

  function closeList(returnFocus = true) {
    setOpen(false);
    if (returnFocus) requestAnimationFrame(() => triggerRef.current?.focus());
  }

  function selectProvider(index: number) {
    onChange(databaseProviders[index].id);
    setActiveIndex(index);
    closeList();
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      openList();
    }
  }

  function handleListKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    let nextIndex = activeIndex;
    if (event.key === "ArrowDown") nextIndex = (activeIndex + 1) % databaseProviders.length;
    else if (event.key === "ArrowUp") nextIndex = (activeIndex - 1 + databaseProviders.length) % databaseProviders.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = databaseProviders.length - 1;
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectProvider(activeIndex);
      return;
    } else if (event.key === "Escape" || event.key === "Tab") {
      if (event.key === "Escape") event.preventDefault();
      closeList(event.key === "Escape");
      return;
    } else return;

    event.preventDefault();
    setActiveIndex(nextIndex);
    optionRefs.current[nextIndex]?.focus();
  }

  return (
    <div ref={rootRef} className="relative">
      <span id="provider-label" className="mb-2 block text-xs font-semibold text-ink/65">Database provider</span>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-labelledby="provider-label provider-value"
        aria-controls="provider-options"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => open ? closeList(false) : openList()}
        onKeyDown={handleTriggerKeyDown}
        className={`flex w-full items-center gap-3 rounded-xl border bg-canvas px-3 py-2.5 text-left outline-none transition ${open ? "border-primary-600 ring-3 ring-primary-600/10" : "border-ink/10 hover:border-primary-600/35"}`}
      >
        <span className={`grid size-9 shrink-0 place-items-center rounded-lg text-[9px] font-bold tracking-wide ${selected.color}`}>{selected.mark}</span>
        <span className="min-w-0 flex-1"><span id="provider-value" className="block text-sm font-semibold">{selected.name}</span><span className="mt-0.5 block truncate text-[10px] text-ink/35">{selected.detail}</span></span>
        <svg aria-hidden="true" viewBox="0 0 20 20" className={`size-4 shrink-0 fill-none stroke-current text-ink/35 transition-transform ${open ? "rotate-180 text-primary-600" : ""}`}><path d="m5 7.5 5 5 5-5" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>

      {open && (
        <div
          id="provider-options"
          role="listbox"
          aria-labelledby="provider-label"
          onKeyDown={handleListKeyDown}
          className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-ink/10 bg-white p-1.5 shadow-[0_20px_55px_rgba(32,26,46,0.18)]"
        >
          {databaseProviders.map((provider, index) => {
            const isSelected = provider.id === value;
            return (
              <button
                key={provider.id}
                ref={(element) => { optionRefs.current[index] = element; }}
                type="button"
                role="option"
                aria-selected={isSelected}
                tabIndex={index === activeIndex ? 0 : -1}
                onFocus={() => setActiveIndex(index)}
                onClick={() => selectProvider(index)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left outline-none transition ${index === activeIndex ? "bg-primary-50" : "hover:bg-ink/[0.035]"}`}
              >
                <span className={`grid size-9 shrink-0 place-items-center rounded-lg text-[9px] font-bold tracking-wide ${provider.color}`}>{provider.mark}</span>
                <span className="min-w-0 flex-1"><span className={`block text-sm font-semibold ${index === activeIndex ? "text-primary-700" : ""}`}>{provider.name}</span><span className="mt-0.5 block truncate text-[10px] text-ink/35">{provider.detail}</span></span>
                <span className={`grid size-5 place-items-center rounded-full text-[10px] font-bold ${isSelected ? "bg-primary-600 text-white" : "text-transparent"}`}>✓</span>
              </button>
            );
          })}
        </div>
      )}
      <input type="hidden" name="provider" value={value} />
    </div>
  );
}

function Sidebar({ activeView, onChange, mobileOpen, onClose }: { activeView: View; onChange: (view: View) => void; mobileOpen: boolean; onClose: () => void }) {
  return (
    <>
      {mobileOpen && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-ink/35 backdrop-blur-sm lg:hidden" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-white/8 bg-ink px-4 py-5 text-white transition-transform duration-300 lg:static lg:w-[264px] lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between px-2">
          <Link href="/" className="flex items-center gap-3" aria-label="pRAwG home">
            <span className="grid size-9 place-items-center rounded-xl bg-primary-600 text-white shadow-[0_8px_28px_rgba(92,68,199,0.4)]"><SparkIcon className="size-4" /></span>
            <span className="text-lg font-semibold tracking-[-0.04em]">pRAwG</span>
          </Link>
          <button aria-label="Close navigation" onClick={onClose} className="grid size-9 place-items-center rounded-xl text-white/55 hover:bg-white/10 hover:text-white lg:hidden"><CloseIcon className="size-5" /></button>
        </div>

        <div className="mt-10 px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/30">Workspace</div>
        <nav className="mt-3 space-y-1.5" aria-label="Workspace navigation">
          {navigation.map((item) => {
            const NavIcon = item.icon;
            const active = item.id === activeView;
            return (
              <button
                key={item.id}
                onClick={() => { onChange(item.id); onClose(); }}
                aria-current={active ? "page" : undefined}
                className={`group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${active ? "bg-white text-ink shadow-lg" : "text-white/55 hover:bg-white/8 hover:text-white"}`}
              >
                <NavIcon className={`size-5 ${active ? "text-primary-600" : "text-white/45 group-hover:text-secondary-300"}`} />
                <span className="flex-1">{item.label}</span>
                {active && <span className="size-1.5 rounded-full bg-secondary-500" />}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.055] p-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold">Storage</span>
            <span className="text-white/40">1.8 / 5 GB</span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full w-[36%] rounded-full bg-secondary-300" /></div>
          <p className="mt-3 text-[11px] leading-5 text-white/35">12 documents across 3 collections</p>
        </div>

        <div className="mt-4 flex items-center gap-3 border-t border-white/8 px-2 pt-4">
          <div className="grid size-9 place-items-center rounded-full bg-primary-600 text-xs font-bold">IH</div>
          <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">Irteza Hussain</p><p className="mt-0.5 truncate text-[10px] text-white/35">Local workspace</p></div>
          <span className="size-2 rounded-full bg-secondary-400 shadow-[0_0_10px_rgba(188,244,103,0.65)]" />
        </div>
      </aside>
    </>
  );
}

function Topbar({ activeView, onMenu }: { activeView: View; onMenu: () => void }) {
  const detail = viewDetails[activeView];
  return (
    <header className="flex min-h-[84px] items-center gap-4 border-b border-ink/8 bg-white/65 px-4 backdrop-blur-xl sm:px-7 lg:px-10">
      <button aria-label="Open navigation" onClick={onMenu} className="grid size-10 shrink-0 place-items-center rounded-xl border border-ink/10 bg-white text-ink/65 lg:hidden"><MenuIcon className="size-5" /></button>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary-600">{detail.eyebrow}</p>
        <div className="mt-1 flex items-baseline gap-3"><h1 className="truncate text-lg font-semibold tracking-[-0.03em] sm:text-xl">{detail.title}</h1><p className="hidden text-xs text-ink/40 md:block">{detail.description}</p></div>
      </div>
      <button className="hidden items-center gap-2 rounded-full border border-ink/10 bg-white px-4 py-2.5 text-xs font-semibold text-ink/65 shadow-sm transition hover:border-primary-600/30 hover:text-primary-700 sm:flex"><span className="size-2 rounded-full bg-secondary-500" />All systems ready</button>
      <button aria-label="Account menu" className="grid size-10 shrink-0 place-items-center rounded-full bg-ink text-xs font-bold text-white">IH</button>
    </header>
  );
}

function ChatView() {
  const [message, setMessage] = useState("");
  const [sentMessages, setSentMessages] = useState<string[]>([]);

  function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = message.trim();
    if (!value) return;
    setSentMessages((current) => [...current, value]);
    setMessage("");
  }

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-4 py-6 sm:px-8 sm:py-8">
      <div className="flex-1 space-y-6 overflow-y-auto pb-6">
        <div className="mx-auto max-w-xl py-5 text-center sm:py-8">
          <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-primary-50 text-primary-600"><SparkIcon className="size-5" /></div>
          <h2 className="mt-4 text-2xl font-semibold tracking-[-0.04em]">What would you like to know?</h2>
          <p className="mt-2 text-sm leading-6 text-ink/45">I’ll search your connected knowledge base and cite the most useful sources.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {["Summarize the latest research", "Compare project requirements", "Find key decisions"].map((prompt) => <button key={prompt} onClick={() => setMessage(prompt)} className="rounded-full border border-ink/10 bg-white px-3.5 py-2 text-xs font-medium text-ink/55 shadow-sm transition hover:border-primary-600/25 hover:text-primary-700">{prompt}</button>)}
          </div>
        </div>

        <div className="ml-auto max-w-[86%] rounded-2xl rounded-br-md bg-primary-600 px-4 py-3 text-sm leading-6 text-white shadow-[0_12px_30px_rgba(92,68,199,0.18)] sm:max-w-[70%]">What are the central findings across my research documents?</div>
        <div className="max-w-[94%] rounded-2xl rounded-bl-md border border-ink/8 bg-white p-5 text-sm leading-6 text-ink/65 shadow-sm sm:max-w-[82%]">
          <div className="mb-3 flex items-center gap-2 font-semibold text-ink"><span className="grid size-7 place-items-center rounded-lg bg-primary-50 text-primary-600"><SparkIcon className="size-3" /></span>Answer from your documents</div>
          Across the indexed research, three themes stand out: retrieval quality improves most when chunks preserve semantic context, hybrid search consistently outperforms keyword-only methods, and source citations materially improve user trust in generated answers.
          <div className="mt-4 flex flex-wrap gap-2"><span className="rounded-lg bg-primary-50 px-2.5 py-1 text-[10px] font-semibold text-primary-700">rag-evaluation.pdf · p. 8</span><span className="rounded-lg bg-primary-50 px-2.5 py-1 text-[10px] font-semibold text-primary-700">research-notes.md</span></div>
        </div>
        {sentMessages.map((item, index) => <div key={`${item}-${index}`} className="ml-auto max-w-[86%] rounded-2xl rounded-br-md bg-primary-600 px-4 py-3 text-sm leading-6 text-white shadow-[0_12px_30px_rgba(92,68,199,0.18)] sm:max-w-[70%]">{item}</div>)}
      </div>

      <form onSubmit={sendMessage} className="rounded-[1.35rem] border border-ink/10 bg-white p-2 shadow-[0_18px_50px_rgba(32,26,46,0.10)]">
        <label htmlFor="message" className="sr-only">Ask your knowledge base</label>
        <div className="flex items-end gap-2">
          <textarea id="message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows={1} placeholder="Ask anything about your knowledge base…" className="min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-sm outline-none placeholder:text-ink/30" />
          <button type="submit" aria-label="Send message" className="grid size-11 shrink-0 place-items-center rounded-2xl bg-primary-600 text-white transition hover:bg-primary-700 disabled:opacity-40" disabled={!message.trim()}><SendIcon className="size-4" /></button>
        </div>
        <div className="flex items-center justify-between px-3 pb-1 pt-1 text-[10px] text-ink/30"><span>Research notes · 12 sources</span><span>Enter to send</span></div>
      </form>
    </div>
  );
}

function KnowledgeView() {
  const [provider, setProvider] = useState<VectorStoreProvider>("chroma_self_hosted");
  const [connection, setConnection] = useState<VectorStoreConnection | null>(null);
  const [connectionResolved, setConnectionResolved] = useState(false);
  const [showConnectionForm, setShowConnectionForm] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);

  useEffect(() => {
    getVectorStoreConnection()
      .then((currentConnection) => {
        setConnection(currentConnection);
        setProvider(currentConnection.provider);
        setShowConnectionForm(false);
      })
      .catch(() => setShowConnectionForm(true))
      .finally(() => setConnectionResolved(true));
  }, []);

  function value(form: FormData, field: string): string {
    return String(form.get(field) ?? "").trim();
  }

  function connectionInput(form: FormData): VectorStoreConnectionInput {
    if (provider === "chroma_self_hosted") {
      return {
        provider,
        endpoint: value(form, "endpoint"),
        collection: value(form, "collection"),
        tenant: value(form, "tenant"),
        database: value(form, "database"),
        ...(value(form, "auth_token") ? { auth_token: value(form, "auth_token") } : {}),
      };
    }
    if (provider === "chroma_cloud") {
      return {
        provider,
        api_key: value(form, "api_key"),
        tenant: value(form, "tenant"),
        database: value(form, "database"),
        collection: value(form, "collection"),
      };
    }
    if (provider === "pinecone_cloud") {
      return {
        provider,
        api_key: value(form, "api_key"),
        index_name: value(form, "index_name"),
        namespace: value(form, "namespace"),
      };
    }
    if (provider === "qdrant_self_hosted") {
      return {
        provider,
        endpoint: value(form, "endpoint"),
        collection: value(form, "collection"),
        ...(value(form, "api_key") ? { api_key: value(form, "api_key") } : {}),
      };
    }
    return {
      provider,
      endpoint: value(form, "endpoint"),
      api_key: value(form, "api_key"),
      collection: value(form, "collection"),
    };
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = connectionInput(new FormData(form));
    setError("");
    setSubmitting(true);
    try {
      const result = await connectVectorStore(input);
      setConnection(result);
      setShowConnectionForm(false);
      form.querySelectorAll<HTMLInputElement>('input[type="password"]').forEach((secretInput) => { secretInput.value = ""; });
    } catch (connectionError) {
      setError(connectionError instanceof Error ? connectionError.message : "Unable to connect to the vector store.");
    } finally {
      setSubmitting(false);
    }
  }

  const fieldClass = "w-full rounded-xl border border-ink/10 bg-canvas px-4 py-3.5 text-sm outline-none placeholder:text-ink/25 focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10";
  const connectedToSelection = connection?.connected && connection.provider === provider;

  function providerFields() {
    if (provider === "chroma_self_hosted") {
      return (
        <>
          <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Server URL</span><input name="endpoint" required type="url" defaultValue="http://chroma:8000" className={fieldClass} /><span className="mt-1.5 block text-[10px] text-ink/35">Must be reachable from the API container.</span></label>
          <div className="grid gap-5 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Tenant</span><input name="tenant" required defaultValue="default_tenant" className={fieldClass} /></label><label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Database</span><input name="database" required defaultValue="default_database" className={fieldClass} /></label></div>
          <div className="grid gap-5 sm:grid-cols-2"><CollectionField className={fieldClass} /><SecretField name="auth_token" label="Auth token" optional className={fieldClass} /></div>
        </>
      );
    }
    if (provider === "chroma_cloud") {
      return (
        <>
          <SecretField name="api_key" label="Chroma API key" className={fieldClass} />
          <div className="grid gap-5 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Tenant ID</span><input name="tenant" required placeholder="tenant-id" className={fieldClass} /></label><label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Database</span><input name="database" required placeholder="database-name" className={fieldClass} /></label></div>
          <CollectionField className={fieldClass} />
        </>
      );
    }
    if (provider === "pinecone_cloud") {
      return (
        <>
          <SecretField name="api_key" label="Pinecone API key" className={fieldClass} />
          <div className="grid gap-5 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Index name</span><input name="index_name" required placeholder="knowledge-index" pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" className={fieldClass} /></label><label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Namespace <span className="font-normal text-ink/30">(optional)</span></span><input name="namespace" placeholder="production" className={fieldClass} /></label></div>
          <p className="rounded-xl bg-primary-50 px-4 py-3 text-[11px] leading-5 text-primary-700">The selected index must use the same dense-vector dimension as your configured Ollama embedding model.</p>
        </>
      );
    }
    if (provider === "qdrant_self_hosted") {
      return (
        <>
          <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Server URL</span><input name="endpoint" required type="url" placeholder="http://host.docker.internal:6333" className={fieldClass} /><span className="mt-1.5 block text-[10px] text-ink/35">The collection is created with cosine distance if it does not exist.</span></label>
          <div className="grid gap-5 sm:grid-cols-2"><CollectionField className={fieldClass} /><SecretField name="api_key" label="API key" optional className={fieldClass} /></div>
        </>
      );
    }
    return (
      <>
        <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Cluster URL</span><input name="endpoint" required type="url" placeholder="https://cluster.region.cloud.qdrant.io:6333" className={fieldClass} /></label>
        <SecretField name="api_key" label="Qdrant API key" className={fieldClass} />
        <CollectionField className={fieldClass} />
      </>
    );
  }

  if (!connectionResolved) {
    return <div className="mx-auto w-full max-w-5xl animate-pulse px-4 py-10 sm:px-8"><div className="h-8 w-64 rounded-lg bg-ink/8" /><div className="mt-6 grid gap-4 sm:grid-cols-3"><div className="h-28 rounded-2xl bg-ink/5" /><div className="h-28 rounded-2xl bg-ink/5" /><div className="h-28 rounded-2xl bg-ink/5" /></div><div className="mt-6 h-64 rounded-[1.5rem] bg-ink/5" /></div>;
  }

  if (connection && !showConnectionForm) {
    if (selectedCollection) {
      return <CollectionDetail collection={selectedCollection} onBack={() => setSelectedCollection(null)} />;
    }
    return <ConnectionDashboard connection={connection} onChangeConnection={() => setShowConnectionForm(true)} onViewCollection={setSelectedCollection} />;
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-7 sm:px-8 sm:py-10">
      <div className="grid gap-6 lg:grid-cols-[0.78fr_1.22fr]">
        <section className="rounded-[1.5rem] bg-ink p-6 text-white sm:p-8">
          <span className="grid size-11 place-items-center rounded-2xl bg-secondary-300 text-ink"><DatabaseIcon className="size-5" /></span>
          <h2 className="mt-7 text-3xl font-semibold tracking-[-0.05em]">Bring your own vector store.</h2>
          <p className="mt-4 text-sm leading-6 text-white/50">Connect an existing database to make its indexed knowledge available to pRAwG. Credentials are sent only to your local API and kept in server memory.</p>
          <div className="mt-9 space-y-4 text-xs text-white/65">
            {["Five supported deployment modes", "Live credential and health checks", "Ingestion and search switch instantly"].map((item) => <div key={item} className="flex items-center gap-3"><span className="grid size-5 place-items-center rounded-full bg-secondary-300 text-[10px] font-bold text-ink">✓</span>{item}</div>)}
          </div>
          {connection && <div className="mt-9 rounded-2xl border border-white/10 bg-white/[0.06] p-4"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-secondary-300">Active connection</p><p className="mt-2 text-sm font-semibold">{connection.label}</p><p className="mt-1 text-xs text-white/40">{connection.collection}</p></div>}
        </section>

        <section className="rounded-[1.5rem] border border-ink/8 bg-white p-5 shadow-sm sm:p-8">
          <div className="flex items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-primary-600">New connection</p><h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">Vector database details</h2></div><span className={`rounded-full px-3 py-1.5 text-[10px] font-bold ${connectedToSelection ? "bg-secondary-200 text-secondary-900" : "bg-ink/5 text-ink/40"}`}>{connectedToSelection ? "CONNECTED" : "NOT CONNECTED"}</span></div>
          <form onSubmit={connect} className="mt-7 space-y-5" autoComplete="off">
            <ProviderSelect value={provider} onChange={(nextProvider) => { setProvider(nextProvider); setError(""); }} />
            {providerFields()}
            {error && <div role="alert" className="rounded-xl border border-[#ef776b]/25 bg-[#ffebe8] px-4 py-3 text-xs font-medium text-[#9a3028]">{error}</div>}
            <label className="flex items-start gap-3 rounded-xl border border-ink/8 bg-primary-50/50 p-4"><input type="checkbox" required defaultChecked className="mt-0.5 size-4 accent-primary-600" /><span><span className="block text-xs font-semibold">Test before activating</span><span className="mt-1 block text-[11px] leading-5 text-ink/40">The active database changes only after credentials and collection access succeed.</span></span></label>
            <button type="submit" disabled={submitting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-5 py-3.5 text-sm font-semibold text-white shadow-[0_10px_25px_rgba(92,68,199,0.18)] transition hover:bg-primary-700 disabled:cursor-wait disabled:opacity-60">{submitting ? "Testing connection…" : connectedToSelection ? "Reconnect" : "Test & connect"}<span aria-hidden="true">→</span></button>
          </form>
        </section>
      </div>
    </div>
  );
}

const MAX_DOCUMENT_BYTES = 25 * 1024 * 1024;
const ALLOWED_DOCUMENT_EXTENSIONS = new Set(["pdf", "docx", "xlsx", "csv", "txt", "md"]);
const METADATA_KEY_PATTERN = /^[A-Za-z][A-Za-z0-9_.-]*$/;
const RESERVED_METADATA_KEYS = new Set(["document_id", "filename", "chunk_index", "source_id", "text"]);
const MAX_CUSTOM_METADATA_BYTES = 1024;

type MetadataRow = { id: number; key: string; value: string };

function DocumentMetadataDialog({ file, uploading, error, onCancel, onUpload }: { file: File; uploading: boolean; error: string; onCancel: () => void; onUpload: (filename: string, metadata: Record<string, string>) => Promise<void> }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const nextRowId = useRef(2);
  const [filename, setFilename] = useState(file.name);
  const [rows, setRows] = useState<MetadataRow[]>([{ id: 1, key: "", value: "" }]);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => {
      if (dialog?.open) dialog.close();
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedFilename = filename.trim();
    const originalExtension = file.name.split(".").pop()?.toLowerCase();
    const nextExtension = trimmedFilename.split(".").pop()?.toLowerCase();
    if (!trimmedFilename || trimmedFilename.includes("/") || trimmedFilename.includes("\\")) {
      setValidationError("Enter a valid file name without folder separators.");
      return;
    }
    if (originalExtension !== nextExtension) {
      setValidationError("Keep the original file extension when renaming this document.");
      return;
    }

    const metadata: Record<string, string> = {};
    const normalizedKeys = new Set<string>();
    for (const row of rows) {
      const key = row.key.trim();
      const value = row.value.trim();
      if (!key && !value) continue;
      if (!key || !value) {
        setValidationError("Every metadata row needs both a key and a value.");
        return;
      }
      if (!METADATA_KEY_PATTERN.test(key) || key.length > 64) {
        setValidationError("Metadata keys must start with a letter and use only letters, numbers, dots, dashes, or underscores.");
        return;
      }
      if (value.length > 500) {
        setValidationError("Metadata values can contain at most 500 characters.");
        return;
      }
      const normalizedKey = key.toLowerCase();
      if (RESERVED_METADATA_KEYS.has(normalizedKey)) {
        setValidationError(`“${key}” is reserved by the document index.`);
        return;
      }
      if (normalizedKeys.has(normalizedKey)) {
        setValidationError("Metadata keys must be unique.");
        return;
      }
      normalizedKeys.add(normalizedKey);
      metadata[key] = value;
    }
    if (new TextEncoder().encode(JSON.stringify(metadata)).length > MAX_CUSTOM_METADATA_BYTES) {
      setValidationError("Custom metadata is too large. Shorten some keys or values.");
      return;
    }

    setValidationError("");
    await onUpload(trimmedFilename, metadata);
  }

  function updateRow(id: number, field: "key" | "value", value: string) {
    setRows((current) => current.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }

  return (
    <dialog ref={dialogRef} aria-labelledby="document-metadata-title" onCancel={(event) => { if (uploading) event.preventDefault(); else onCancel(); }} className="m-auto w-[min(94vw,42rem)] rounded-[1.75rem] border border-white/10 bg-white p-0 text-ink shadow-[0_28px_90px_rgba(23,22,35,0.35)] backdrop:bg-ink/60 backdrop:backdrop-blur-sm">
      <form onSubmit={handleSubmit} className="max-h-[88vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-6 border-b border-ink/8 px-6 py-5 sm:px-7">
          <div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary-600">Prepare upload</p><h2 id="document-metadata-title" className="mt-2 text-2xl font-semibold tracking-[-0.04em]">Edit file details</h2><p className="mt-1 text-xs leading-5 text-ink/45">Rename the file and add metadata that will be attached to every indexed chunk.</p></div>
          <button type="button" disabled={uploading} onClick={onCancel} aria-label="Close metadata dialog" className="grid size-9 shrink-0 place-items-center rounded-full border border-ink/10 text-lg text-ink/45 transition hover:bg-ink/5 hover:text-ink disabled:opacity-40">×</button>
        </div>

        <div className="space-y-6 px-6 py-6 sm:px-7">
          <div className="rounded-2xl border border-primary-600/10 bg-primary-50/60 p-4"><p className="truncate text-sm font-semibold">{file.name}</p><p className="mt-1 text-[10px] text-ink/40">{formatBytes(file.size)} · {documentExtension(file.name).toUpperCase()}</p></div>
          <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">File name</span><input autoFocus value={filename} maxLength={255} onChange={(event) => setFilename(event.target.value)} className="w-full rounded-xl border border-ink/10 bg-canvas px-4 py-3 text-sm outline-none focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10" /><span className="mt-1.5 block text-[10px] text-ink/35">You can rename the file, but its extension must stay the same.</span></label>

          <fieldset>
            <legend className="text-xs font-semibold text-ink/65">Custom metadata</legend>
            <div className="mt-1 flex items-center justify-between gap-4"><p className="text-[10px] text-ink/35">Optional key/value fields, such as author, department, or project.</p><button type="button" disabled={rows.length >= 20 || uploading} onClick={() => setRows((current) => [...current, { id: nextRowId.current++, key: "", value: "" }])} className="shrink-0 rounded-lg border border-primary-600/20 px-3 py-2 text-[10px] font-bold text-primary-700 transition hover:bg-primary-50 disabled:opacity-40">+ Add field</button></div>
            <div className="mt-4 space-y-3">
              {rows.map((row, index) => <div key={row.id} className="grid gap-2 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)_36px]">
                <label><span className="sr-only">Metadata key {index + 1}</span><input value={row.key} maxLength={64} onChange={(event) => updateRow(row.id, "key", event.target.value)} placeholder="Key" className="w-full rounded-xl border border-ink/10 bg-canvas px-3 py-2.5 text-xs outline-none focus:border-primary-600" /></label>
                <label><span className="sr-only">Metadata value {index + 1}</span><input value={row.value} maxLength={500} onChange={(event) => updateRow(row.id, "value", event.target.value)} placeholder="Value" className="w-full rounded-xl border border-ink/10 bg-canvas px-3 py-2.5 text-xs outline-none focus:border-primary-600" /></label>
                <button type="button" disabled={rows.length === 1 || uploading} onClick={() => setRows((current) => current.filter((item) => item.id !== row.id))} aria-label={`Remove metadata field ${index + 1}`} className="grid size-9 place-items-center rounded-lg text-lg text-ink/30 transition hover:bg-[#ffebe8] hover:text-[#9a3028] disabled:opacity-25">−</button>
              </div>)}
            </div>
          </fieldset>

          {(validationError || error) && <div role="alert" className="rounded-xl border border-[#ef776b]/25 bg-[#ffebe8] px-4 py-3 text-xs font-medium text-[#9a3028]">{validationError || error}</div>}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-ink/8 bg-canvas/60 px-6 py-4 sm:flex-row sm:justify-end sm:px-7"><button type="button" disabled={uploading} onClick={onCancel} className="rounded-xl border border-ink/10 bg-white px-5 py-3 text-xs font-semibold text-ink/55 transition hover:text-ink disabled:opacity-40">Cancel</button><button type="submit" disabled={uploading} className="rounded-xl bg-primary-600 px-5 py-3 text-xs font-semibold text-white shadow-[0_10px_24px_rgba(92,68,199,0.2)] transition hover:bg-primary-700 disabled:cursor-wait disabled:opacity-60">{uploading ? "Storing & indexing…" : "Upload document"}</button></div>
      </form>
    </dialog>
  );
}

function ConnectionDashboard({ connection, onChangeConnection, onViewCollection }: { connection: VectorStoreConnection; onChangeConnection: () => void; onViewCollection: (collection: string) => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addDataButtonRef = useRef<HTMLButtonElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [lastUpload, setLastUpload] = useState<IngestedDocument | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [collections, setCollections] = useState<VectorCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState("");
  const [collectionSearch, setCollectionSearch] = useState("");
  const [collectionsVersion, setCollectionsVersion] = useState(0);
  const providerDetails = databaseProviders.find((item) => item.id === connection.provider) ?? databaseProviders[0];
  const deployment = connection.provider.endsWith("_cloud") ? "Managed cloud" : "Self-hosted";
  const normalizedSearch = collectionSearch.trim().toLowerCase();
  const filteredCollections = collections.filter((collection) => collection.name.toLowerCase().includes(normalizedSearch));

  useEffect(() => {
    let cancelled = false;
    getVectorStoreCollections()
      .then((result) => {
        if (!cancelled) setCollections(result.collections);
      })
      .catch((error) => {
        if (!cancelled) setCollectionsError(error instanceof Error ? error.message : "Unable to load collections.");
      })
      .finally(() => {
        if (!cancelled) setCollectionsLoading(false);
      });
    return () => { cancelled = true; };
  }, [connection.provider, connection.collection, collectionsVersion]);

  async function handleDocument(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;

    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_DOCUMENT_EXTENSIONS.has(extension)) {
      setUploadError("Choose a PDF, DOCX, XLSX, CSV, TXT, or Markdown file.");
      return;
    }
    if (file.size <= 0 || file.size > MAX_DOCUMENT_BYTES) {
      setUploadError("The document must be larger than 0 bytes and no more than 25 MB.");
      return;
    }

    setUploadError("");
    setPendingFile(file);
  }

  async function uploadPendingDocument(filename: string, metadata: Record<string, string>) {
    if (!pendingFile) return;
    setUploadError("");
    setUploading(true);
    try {
      setLastUpload(await uploadDocument(pendingFile, { filename, metadata }));
      setCollectionsVersion((version) => version + 1);
      setPendingFile(null);
      requestAnimationFrame(() => addDataButtonRef.current?.focus());
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "We couldn't add this document. Try again.");
    } finally {
      setUploading(false);
    }
  }

  function cancelPendingDocument() {
    if (uploading) return;
    setPendingFile(null);
    setUploadError("");
    requestAnimationFrame(() => addDataButtonRef.current?.focus());
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-8 sm:py-10">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-primary-600"><span className="size-2 rounded-full bg-secondary-500 shadow-[0_0_10px_rgba(141,206,49,0.65)]" />Connected and ready</div>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.05em] sm:text-4xl">Your knowledge base</h2>
          <p className="mt-2 text-sm text-ink/45">Monitor the active database and add documents for retrieval.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onChangeConnection} className="rounded-full border border-ink/10 bg-white px-4 py-2.5 text-xs font-semibold text-ink/55 shadow-sm transition hover:border-primary-600/25 hover:text-primary-700">Change connection</button>
          <input ref={fileInputRef} type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain,text/markdown" onChange={handleDocument} className="sr-only" tabIndex={-1} />
          <button ref={addDataButtonRef} type="button" disabled={uploading} onClick={() => fileInputRef.current?.click()} className="inline-flex items-center gap-2 rounded-full bg-primary-600 px-5 py-2.5 text-xs font-semibold text-white shadow-[0_10px_24px_rgba(92,68,199,0.22)] transition hover:-translate-y-0.5 hover:bg-primary-700 disabled:cursor-wait disabled:opacity-60">
            <span className="text-base leading-none">+</span>{uploading ? "Adding data…" : "Add data"}
          </button>
        </div>
      </div>

      {uploadError && <div role="alert" className="mt-6 rounded-xl border border-[#ef776b]/25 bg-[#ffebe8] px-4 py-3 text-xs font-medium text-[#9a3028]">{uploadError}</div>}
      {lastUpload && <div role="status" className="mt-6 flex items-center gap-3 rounded-xl border border-secondary-500/20 bg-secondary-200/55 px-4 py-3 text-xs text-secondary-900"><span className="grid size-6 place-items-center rounded-full bg-secondary-500 font-bold text-white">✓</span><span><strong>{lastUpload.filename}</strong> was indexed into {lastUpload.chunks} searchable chunks{lastUpload.ocr_used ? " using OCR" : ""}.</span></div>}

      <div className="mt-7 grid gap-4 sm:grid-cols-3">
        <article className="rounded-2xl border border-ink/8 bg-white p-5 shadow-sm"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-ink/30">Connection</p><div className="mt-4 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-secondary-200 text-secondary-900"><span className="size-2.5 rounded-full bg-secondary-500" /></span><div><p className="text-lg font-semibold tracking-[-0.03em]">Active</p><p className="text-[11px] text-ink/40">Health check passed</p></div></div></article>
        <article className="rounded-2xl border border-ink/8 bg-white p-5 shadow-sm"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-ink/30">Database provider</p><div className="mt-4 flex items-center gap-3"><span className={`grid size-10 place-items-center rounded-xl text-[10px] font-bold ${providerDetails.color}`}>{providerDetails.mark}</span><div><p className="text-lg font-semibold tracking-[-0.03em]">{providerDetails.name}</p><p className="text-[11px] text-ink/40">{deployment}</p></div></div></article>
        <article className="rounded-2xl border border-ink/8 bg-white p-5 shadow-sm"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-ink/30">Collection / index</p><p className="mt-5 truncate text-lg font-semibold tracking-[-0.03em]">{connection.collection}</p><p className="mt-1 text-[11px] text-ink/40">Current retrieval target</p></article>
      </div>

      <section className="mt-6 overflow-hidden rounded-[1.5rem] border border-ink/8 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-ink/8 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold tracking-[-0.02em]">Collections</h3>
              {!collectionsLoading && !collectionsError && <span className="rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-bold text-primary-700">{collections.length}</span>}
            </div>
            <p className="mt-1 text-xs text-ink/40">{connection.provider === "pinecone_cloud" ? "Namespaces available in the connected Pinecone index" : "Collections available in the connected database"}</p>
          </div>
          <div className="relative w-full sm:w-72">
            <label htmlFor="collection-search" className="sr-only">Search collections</label>
            <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink/30" />
            <input
              id="collection-search"
              type="search"
              value={collectionSearch}
              onChange={(event) => setCollectionSearch(event.target.value)}
              placeholder="Search collections…"
              className="w-full rounded-xl border border-ink/10 bg-canvas py-2.5 pl-10 pr-4 text-xs outline-none placeholder:text-ink/30 focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10"
            />
          </div>
        </div>

        {collectionsLoading ? (
          <div aria-label="Loading collections" className="divide-y divide-ink/8 px-5 sm:px-6">
            {[0, 1, 2].map((item) => <div key={item} className="flex animate-pulse items-center gap-3 py-4"><span className="size-9 rounded-xl bg-ink/5" /><span className="h-3 w-40 rounded bg-ink/5" /><span className="ml-auto h-3 w-16 rounded bg-ink/5" /></div>)}
          </div>
        ) : collectionsError ? (
          <div role="alert" className="m-5 flex flex-col gap-3 rounded-xl border border-[#ef776b]/25 bg-[#ffebe8] px-4 py-3 text-xs text-[#9a3028] sm:m-6 sm:flex-row sm:items-center sm:justify-between">
            <span>{collectionsError}</span>
            <button type="button" onClick={() => { setCollectionsLoading(true); setCollectionsError(""); setCollectionsVersion((version) => version + 1); }} className="self-start font-bold underline underline-offset-2 sm:self-auto">Try again</button>
          </div>
        ) : filteredCollections.length > 0 ? (
          <ul className="divide-y divide-ink/8 px-5 sm:px-6">
            {filteredCollections.map((collection) => (
              <li key={`${collection.kind}-${collection.name}`} className="flex items-center gap-3 py-4">
                <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${collection.active ? "bg-primary-50 text-primary-700" : "bg-ink/5 text-ink/40"}`}><DatabaseIcon className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><p className="truncate text-sm font-semibold">{collection.name}</p>{collection.active && <span className="rounded-full bg-secondary-200 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-secondary-900">Active</span>}</div>
                  <p className="mt-0.5 text-[10px] capitalize text-ink/35">{collection.kind}</p>
                </div>
                <div className="text-right"><p className="text-sm font-semibold">{collection.records === null ? "—" : collection.records.toLocaleString()}</p><p className="mt-0.5 text-[10px] text-ink/35">records</p></div>
                <button type="button" onClick={() => onViewCollection(collection.name)} className="rounded-lg border border-ink/10 bg-white px-3 py-2 text-[10px] font-bold text-primary-700 transition hover:border-primary-600/30 hover:bg-primary-50">View</button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="px-6 py-10 text-center">
            <span className="mx-auto grid size-10 place-items-center rounded-xl bg-primary-50 text-primary-600"><SearchIcon className="size-4" /></span>
            <p className="mt-3 text-sm font-semibold">{normalizedSearch ? "No matching collections" : "No collections found"}</p>
            <p className="mt-1 text-xs text-ink/40">{normalizedSearch ? `Nothing matches “${collectionSearch.trim()}”.` : "This database does not contain any collections yet."}</p>
          </div>
        )}
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
        <section className="overflow-hidden rounded-[1.5rem] border border-ink/8 bg-white shadow-sm">
          <div className="border-b border-ink/8 px-6 py-5"><h3 className="font-semibold tracking-[-0.02em]">Database profile</h3><p className="mt-1 text-xs text-ink/40">Runtime configuration used by ingestion and retrieval</p></div>
          <dl className="divide-y divide-ink/8 px-6">
            {[["Provider", connection.label], ["Deployment", deployment], ["Resource", connection.collection], ["Embedding pipeline", "Ollama · configured model"], ["Credential status", "Verified in API memory"]].map(([label, value]) => <div key={label} className="flex items-center justify-between gap-6 py-4 text-xs"><dt className="text-ink/40">{label}</dt><dd className="text-right font-semibold">{value}</dd></div>)}
          </dl>
        </section>
        <section className="rounded-[1.5rem] bg-ink p-6 text-white shadow-sm">
          <span className="grid size-10 place-items-center rounded-xl bg-secondary-300 text-ink"><CloudIcon className="size-5" /></span>
          <h3 className="mt-6 text-xl font-semibold tracking-[-0.03em]">Ready for documents</h3>
          <p className="mt-3 text-xs leading-6 text-white/45">Add PDF, DOCX, XLSX, CSV, TXT, or Markdown files. Each document is extracted, chunked, embedded through Ollama, and written to this database.</p>
          <button type="button" disabled={uploading} onClick={() => fileInputRef.current?.click()} className="mt-7 w-full rounded-xl bg-white px-4 py-3 text-xs font-semibold text-ink transition hover:bg-secondary-300 disabled:opacity-60">{uploading ? "Indexing document…" : "Choose a document"}</button>
          <p className="mt-3 text-center text-[10px] text-white/30">Maximum 25 MB · one file at a time</p>
        </section>
      </div>
      {pendingFile && <DocumentMetadataDialog file={pendingFile} uploading={uploading} error={uploadError} onCancel={cancelPendingDocument} onUpload={uploadPendingDocument} />}
    </div>
  );
}

function CollectionDetail({ collection, onBack }: { collection: string; onBack: () => void }) {
  const [chunks, setChunks] = useState<VectorChunk[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<CollectionSearchMode>("similarity");
  const [results, setResults] = useState<VectorChunk[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const displayedChunks = results ?? chunks;

  useEffect(() => {
    let cancelled = false;
    getCollectionChunks(collection)
      .then((page) => {
        if (cancelled) return;
        setChunks(page.chunks);
        setTotal(page.total);
        setNextCursor(page.next_cursor);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "Unable to load collection chunks.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [collection]);

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError("");
    try {
      const page = await getCollectionChunks(collection, nextCursor);
      setChunks((current) => [...current, ...page.chunks]);
      setTotal(page.total);
      setNextCursor(page.next_cursor);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load more chunks.");
    } finally {
      setLoadingMore(false);
    }
  }

  async function runSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const searchQuery = query.trim();
    if (!searchQuery) {
      setResults(null);
      return;
    }
    setSearching(true);
    setError("");
    try {
      const response = await searchCollectionChunks(collection, searchQuery, mode);
      setResults(response.chunks);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Unable to search this collection.");
    } finally {
      setSearching(false);
    }
  }

  async function removeChunk(chunk: VectorChunk) {
    if (!window.confirm("Delete this chunk permanently from the collection?")) return;
    setDeletingId(chunk.id);
    setError("");
    try {
      await deleteCollectionChunk(collection, chunk.id);
      setChunks((current) => current.filter((item) => item.id !== chunk.id));
      setResults((current) => current ? current.filter((item) => item.id !== chunk.id) : null);
      setTotal((current) => current === null ? null : Math.max(0, current - 1));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete this chunk.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-8 sm:py-10">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-2 text-xs font-semibold text-ink/45 transition hover:text-primary-700"><span aria-hidden="true">←</span>Back to collections</button>
      <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary-600">Collection explorer</p><h2 className="mt-2 truncate text-3xl font-semibold tracking-[-0.05em]">{collection}</h2><p className="mt-2 text-sm text-ink/45">{total === null ? "Browse indexed chunks and metadata" : `${total.toLocaleString()} indexed chunks`}</p></div>
      </div>

      <section className="mt-6 rounded-[1.5rem] border border-ink/8 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <div>
            <span className="mb-2 block text-[10px] font-bold uppercase tracking-[0.13em] text-ink/35">Search mode</span>
            <div className="inline-flex rounded-xl bg-ink/5 p-1" role="group" aria-label="Collection search mode">
              {(["similarity", "text"] as const).map((searchMode) => <button key={searchMode} type="button" aria-pressed={mode === searchMode} onClick={() => { setMode(searchMode); setResults(null); }} className={`rounded-lg px-4 py-2 text-xs font-semibold transition ${mode === searchMode ? "bg-white text-primary-700 shadow-sm" : "text-ink/40 hover:text-ink"}`}>{searchMode === "similarity" ? "Similarity" : "String"}</button>)}
            </div>
          </div>
          <form onSubmit={runSearch} className="flex min-w-0 flex-1 gap-2">
            <label htmlFor="chunk-search" className="sr-only">Search collection chunks</label>
            <div className="relative min-w-0 flex-1"><SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink/30" /><input id="chunk-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={mode === "similarity" ? "Search by meaning…" : "Search exact text and metadata…"} className="w-full rounded-xl border border-ink/10 bg-canvas py-3 pl-10 pr-4 text-xs outline-none focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10" /></div>
            <button type="submit" disabled={searching || !query.trim()} className="rounded-xl bg-primary-600 px-5 py-3 text-xs font-semibold text-white transition hover:bg-primary-700 disabled:opacity-50">{searching ? "Searching…" : "Search"}</button>
            {results !== null && <button type="button" onClick={() => { setQuery(""); setResults(null); }} className="rounded-xl border border-ink/10 px-4 py-3 text-xs font-semibold text-ink/45 hover:text-ink">Clear</button>}
          </form>
        </div>
        <p className="mt-3 text-[10px] text-ink/35">{mode === "similarity" ? "Semantic search uses your configured Ollama embedding model across the selected collection." : "String search scans chunk text, IDs, and metadata across the complete collection."}</p>
      </section>

      {error && <div role="alert" className="mt-5 rounded-xl border border-[#ef776b]/25 bg-[#ffebe8] px-4 py-3 text-xs font-medium text-[#9a3028]">{error}</div>}

      <section className="mt-6 space-y-4">
        {loading ? [0, 1, 2].map((item) => <div key={item} className="h-48 animate-pulse rounded-[1.5rem] border border-ink/8 bg-white" />) : displayedChunks.map((chunk, index) => (
          <article key={chunk.id} className="rounded-[1.5rem] border border-ink/8 bg-white p-5 shadow-sm sm:p-6">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary-50 text-xs font-bold text-primary-700">{index + 1}</span>
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">Chunk</h3>{chunk.score !== null && <span className="rounded-full bg-secondary-200 px-2.5 py-1 text-[9px] font-bold text-secondary-900">Score {chunk.score.toFixed(3)}</span>}</div><p className="mt-1 break-all font-mono text-[10px] text-ink/35">{chunk.id}</p></div>
              <button type="button" disabled={deletingId === chunk.id} onClick={() => removeChunk(chunk)} className="rounded-lg border border-[#ef776b]/25 px-3 py-2 text-[10px] font-bold text-[#a33a31] transition hover:bg-[#ffebe8] disabled:opacity-50">{deletingId === chunk.id ? "Deleting…" : "Delete"}</button>
            </div>
            <p className="mt-5 whitespace-pre-wrap break-words text-sm leading-7 text-ink/70">{chunk.text || <span className="italic text-ink/30">This chunk has no stored text.</span>}</p>
            <div className="mt-5 border-t border-ink/8 pt-4"><p className="text-[10px] font-bold uppercase tracking-[0.13em] text-ink/30">Metadata</p>{Object.keys(chunk.metadata).length > 0 ? <dl className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(chunk.metadata).map(([key, value]) => <div key={key} className="rounded-xl bg-canvas px-3 py-2.5"><dt className="text-[9px] font-bold uppercase tracking-wide text-ink/30">{key}</dt><dd className="mt-1 break-all text-xs text-ink/65">{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl> : <p className="mt-2 text-xs italic text-ink/30">No metadata stored for this chunk.</p>}</div>
          </article>
        ))}
        {!loading && displayedChunks.length === 0 && <div className="rounded-[1.5rem] border border-ink/8 bg-white px-6 py-14 text-center shadow-sm"><SearchIcon className="mx-auto size-6 text-ink/20" /><p className="mt-3 text-sm font-semibold">{results === null ? "No chunks in this collection" : "No matching chunks"}</p><p className="mt-1 text-xs text-ink/40">{results === null ? "Upload data to begin populating this collection." : "Try a different query or search mode."}</p></div>}
      </section>

      {results === null && nextCursor && <div className="mt-6 text-center"><button type="button" disabled={loadingMore} onClick={loadMore} className="rounded-full border border-ink/10 bg-white px-5 py-3 text-xs font-semibold text-primary-700 shadow-sm transition hover:border-primary-600/30 disabled:opacity-50">{loadingMore ? "Loading…" : "Load more chunks"}</button></div>}
    </div>
  );
}

function CollectionField({ className }: { className: string }) {
  return <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Collection name</span><input name="collection" required defaultValue="research-notes" pattern="[A-Za-z0-9][A-Za-z0-9._-]*" className={className} /></label>;
}

function SecretField({ name, label, optional = false, className }: { name: string; label: string; optional?: boolean; className: string }) {
  return <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">{label} {optional && <span className="font-normal text-ink/30">(optional)</span>}</span><input name={name} required={!optional} type="password" autoComplete="off" placeholder="••••••••••••" className={className} /></label>;
}

function CloudView() {
  const [search, setSearch] = useState("");
  const [documents, setDocuments] = useState<StoredDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const normalizedSearch = search.trim().toLowerCase();
  const filtered = documents.filter((document) => `${document.filename} ${document.collection} ${Object.entries(document.metadata).flat().join(" ")}`.toLowerCase().includes(normalizedSearch));
  const totalChunks = documents.reduce((total, document) => total + document.chunks, 0);
  const totalBytes = documents.reduce((total, document) => total + document.size, 0);

  useEffect(() => {
    let cancelled = false;
    getStoredDocuments()
      .then((storedDocuments) => {
        if (!cancelled) setDocuments(storedDocuments);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "Unable to load stored documents.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-8 sm:py-10">
      <div className="grid gap-4 sm:grid-cols-3">
        {[[documents.length.toLocaleString(), "Stored documents", "Durable originals"], [totalChunks.toLocaleString(), "Indexed chunks", "Ready to search"], [formatBytes(totalBytes), "Storage used", "MinIO object storage"]].map(([value, label, note]) => <div key={label} className="rounded-2xl border border-ink/8 bg-white p-5 shadow-sm"><p className="text-2xl font-semibold tracking-[-0.04em]">{loading ? "—" : value}</p><div className="mt-1 flex items-center justify-between gap-2"><span className="text-xs font-medium text-ink/55">{label}</span><span className="text-[10px] text-primary-600">{note}</span></div></div>)}
      </div>
      {error && <div role="alert" className="mt-6 rounded-xl border border-[#ef776b]/25 bg-[#ffebe8] px-4 py-3 text-xs font-medium text-[#9a3028]">{error}</div>}
      <section className="mt-6 overflow-hidden rounded-[1.5rem] border border-ink/8 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-ink/8 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div><h2 className="font-semibold tracking-[-0.02em]">All documents</h2><p className="mt-1 text-xs text-ink/40">Uploaded and indexed files</p></div>
          <div className="relative"><SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink/30" /><label htmlFor="document-search" className="sr-only">Search documents</label><input id="document-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents" className="w-full rounded-xl border border-ink/10 bg-canvas py-2.5 pl-10 pr-4 text-xs outline-none focus:border-primary-600 sm:w-64" /></div>
        </div>
        <div className="hidden grid-cols-[minmax(0,2fr)_1fr_0.6fr_0.8fr_70px] gap-4 border-b border-ink/8 bg-canvas/60 px-6 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-ink/30 md:grid"><span>Name</span><span>Collection</span><span>Chunks</span><span>Uploaded</span><span /></div>
        <div className="divide-y divide-ink/8">
          {loading && [0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse bg-ink/[0.025]" />)}
          {!loading && filtered.map((document) => <div key={document.document_id} className="grid gap-3 px-5 py-4 transition hover:bg-primary-50/30 md:grid-cols-[minmax(0,2fr)_1fr_0.6fr_0.8fr_70px] md:items-center md:gap-4 md:px-6">
            <div className="flex min-w-0 items-center gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-50 text-[9px] font-bold uppercase tracking-wide text-primary-700">{documentExtension(document.filename)}</span><div className="min-w-0"><p className="truncate text-sm font-semibold">{document.filename}</p><p className="mt-0.5 text-[10px] text-ink/35">{formatBytes(document.size)} · Stored & indexed{Object.keys(document.metadata).length > 0 ? ` · ${Object.keys(document.metadata).length} metadata fields` : ""}</p></div></div>
            <span className="w-fit rounded-full bg-ink/5 px-2.5 py-1 text-[10px] font-medium text-ink/55">{document.collection}</span><span className="hidden text-xs text-ink/45 md:block">{document.chunks}</span><span className="hidden text-xs text-ink/45 md:block">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(document.uploaded_at))}</span><a href={storedDocumentDownloadUrl(document.document_id)} download className="w-fit rounded-lg border border-ink/10 px-3 py-2 text-center text-[10px] font-bold text-primary-700 transition hover:border-primary-600/30 hover:bg-primary-50">Download</a>
          </div>)}
          {!loading && filtered.length === 0 && <div className="px-6 py-14 text-center"><SearchIcon className="mx-auto size-6 text-ink/20" /><p className="mt-3 text-sm font-semibold">{documents.length === 0 ? "No stored documents" : "No documents found"}</p><p className="mt-1 text-xs text-ink/40">{documents.length === 0 ? "Add data from the knowledge base screen to store it here." : "Try a different search term."}</p></div>}
        </div>
      </section>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

function documentExtension(filename: string): string {
  return filename.split(".").pop()?.slice(0, 4) || "FILE";
}

export function Workspace() {
  const [activeView, setActiveView] = useState<View>("chat");
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <main className="flex h-dvh overflow-hidden bg-canvas text-ink">
      <Sidebar activeView={activeView} onChange={setActiveView} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar activeView={activeView} onMenu={() => setMobileOpen(true)} />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {activeView === "chat" && <ChatView />}
          {activeView === "knowledge" && <KnowledgeView />}
          {activeView === "cloud" && <CloudView />}
        </div>
        <nav className="grid grid-cols-3 border-t border-ink/8 bg-white px-2 py-2 lg:hidden" aria-label="Mobile workspace navigation">
          {navigation.map((item) => { const NavIcon = item.icon; const active = item.id === activeView; return <button key={item.id} onClick={() => setActiveView(item.id)} className={`flex flex-col items-center gap-1 rounded-xl py-2 text-[10px] font-semibold ${active ? "bg-primary-50 text-primary-700" : "text-ink/35"}`}><NavIcon className="size-4" />{item.shortLabel}</button>; })}
        </nav>
      </div>
    </main>
  );
}
