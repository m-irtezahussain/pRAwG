"use client";

import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";

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
  { id: "chroma", name: "Chroma", detail: "Open-source embedding database", mark: "CH", color: "bg-primary-50 text-primary-700" },
  { id: "pinecone", name: "Pinecone", detail: "Managed vector database", mark: "PC", color: "bg-secondary-200 text-secondary-900" },
  { id: "weaviate", name: "Weaviate", detail: "AI-native vector database", mark: "WV", color: "bg-[#e6f7f0] text-[#167052]" },
  { id: "qdrant", name: "Qdrant", detail: "High-performance vector search", mark: "QD", color: "bg-[#ffebe8] text-[#b63d35]" },
] as const;

// Keyboard map: Enter/Space/ArrowDown opens; Arrow keys move; Home/End jump;
// Enter/Space selects; Escape closes and returns focus to the trigger.
function ProviderSelect() {
  const [selectedId, setSelectedId] = useState<(typeof databaseProviders)[number]["id"]>("chroma");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const selected = databaseProviders.find((provider) => provider.id === selectedId) ?? databaseProviders[0];

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  function openList() {
    const selectedIndex = databaseProviders.findIndex((provider) => provider.id === selectedId);
    setActiveIndex(selectedIndex);
    setOpen(true);
    requestAnimationFrame(() => optionRefs.current[selectedIndex]?.focus());
  }

  function closeList(returnFocus = true) {
    setOpen(false);
    if (returnFocus) requestAnimationFrame(() => triggerRef.current?.focus());
  }

  function selectProvider(index: number) {
    setSelectedId(databaseProviders[index].id);
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
            const isSelected = provider.id === selectedId;
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
      <input type="hidden" name="provider" value={selectedId} />
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
  const [connected, setConnected] = useState(false);
  function connect(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setConnected(true); }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-7 sm:px-8 sm:py-10">
      <div className="grid gap-6 lg:grid-cols-[0.78fr_1.22fr]">
        <section className="rounded-[1.5rem] bg-ink p-6 text-white sm:p-8">
          <span className="grid size-11 place-items-center rounded-2xl bg-secondary-300 text-ink"><DatabaseIcon className="size-5" /></span>
          <h2 className="mt-7 text-3xl font-semibold tracking-[-0.05em]">Bring your own vector store.</h2>
          <p className="mt-4 text-sm leading-6 text-white/50">Connect an existing database to make its indexed knowledge available to pRAwG. Your credentials stay within your local environment.</p>
          <div className="mt-9 space-y-4 text-xs text-white/65">
            {["Encrypted connection details", "Semantic search health checks", "Collection-level access controls"].map((item) => <div key={item} className="flex items-center gap-3"><span className="grid size-5 place-items-center rounded-full bg-secondary-300 text-[10px] font-bold text-ink">✓</span>{item}</div>)}
          </div>
        </section>

        <section className="rounded-[1.5rem] border border-ink/8 bg-white p-5 shadow-sm sm:p-8">
          <div className="flex items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-primary-600">New connection</p><h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">Vector database details</h2></div><span className={`rounded-full px-3 py-1.5 text-[10px] font-bold ${connected ? "bg-secondary-200 text-secondary-900" : "bg-ink/5 text-ink/40"}`}>{connected ? "CONNECTED" : "NOT CONNECTED"}</span></div>
          <form onSubmit={connect} className="mt-7 space-y-5">
            <ProviderSelect />
            <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Connection URL</span><input required type="url" defaultValue="http://chroma:8000" className="w-full rounded-xl border border-ink/10 bg-canvas px-4 py-3.5 text-sm outline-none placeholder:text-ink/25 focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10" /></label>
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">Collection name</span><input required defaultValue="research-notes" className="w-full rounded-xl border border-ink/10 bg-canvas px-4 py-3.5 text-sm outline-none focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10" /></label>
              <label className="block"><span className="mb-2 block text-xs font-semibold text-ink/65">API key <span className="font-normal text-ink/30">(optional)</span></span><input type="password" placeholder="••••••••••••" className="w-full rounded-xl border border-ink/10 bg-canvas px-4 py-3.5 text-sm outline-none placeholder:text-ink/25 focus:border-primary-600 focus:ring-3 focus:ring-primary-600/10" /></label>
            </div>
            <label className="flex items-start gap-3 rounded-xl border border-ink/8 bg-primary-50/50 p-4"><input type="checkbox" defaultChecked className="mt-0.5 size-4 accent-primary-600" /><span><span className="block text-xs font-semibold">Verify connection before saving</span><span className="mt-1 block text-[11px] leading-5 text-ink/40">Run a read-only health check against the selected collection.</span></span></label>
            <button type="submit" className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-5 py-3.5 text-sm font-semibold text-white shadow-[0_10px_25px_rgba(92,68,199,0.18)] transition hover:bg-primary-700">{connected ? "Connection saved" : "Test & connect"}<span aria-hidden="true">→</span></button>
          </form>
        </section>
      </div>
    </div>
  );
}

const documents = [
  { name: "rag-evaluation-framework.pdf", type: "PDF", collection: "Research notes", size: "4.2 MB", date: "Nov 8, 2026", chunks: 48, color: "bg-[#ffebe8] text-[#bd4538]" },
  { name: "product-requirements.docx", type: "DOCX", collection: "Project docs", size: "1.8 MB", date: "Nov 6, 2026", chunks: 31, color: "bg-[#e7efff] text-[#315eb0]" },
  { name: "architecture-decisions.md", type: "MD", collection: "Project docs", size: "82 KB", date: "Nov 5, 2026", chunks: 12, color: "bg-primary-50 text-primary-700" },
  { name: "retrieval-notes.txt", type: "TXT", collection: "Research notes", size: "28 KB", date: "Oct 29, 2026", chunks: 8, color: "bg-secondary-200 text-secondary-900" },
  { name: "attention-is-all-you-need.pdf", type: "PDF", collection: "Reading list", size: "2.1 MB", date: "Oct 22, 2026", chunks: 34, color: "bg-[#ffebe8] text-[#bd4538]" },
];

function CloudView() {
  const [search, setSearch] = useState("");
  const filtered = documents.filter((document) => document.name.toLowerCase().includes(search.toLowerCase()));
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-8 sm:py-10">
      <div className="grid gap-4 sm:grid-cols-3">
        {[["12", "Total documents", "+3 this month"], ["186", "Indexed chunks", "Ready to search"], ["1.8 GB", "Storage used", "36% of allowance"]].map(([value, label, note]) => <div key={label} className="rounded-2xl border border-ink/8 bg-white p-5 shadow-sm"><p className="text-2xl font-semibold tracking-[-0.04em]">{value}</p><div className="mt-1 flex items-center justify-between gap-2"><span className="text-xs font-medium text-ink/55">{label}</span><span className="text-[10px] text-primary-600">{note}</span></div></div>)}
      </div>
      <section className="mt-6 overflow-hidden rounded-[1.5rem] border border-ink/8 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-ink/8 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div><h2 className="font-semibold tracking-[-0.02em]">All documents</h2><p className="mt-1 text-xs text-ink/40">Uploaded and indexed files</p></div>
          <div className="relative"><SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink/30" /><label htmlFor="document-search" className="sr-only">Search documents</label><input id="document-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents" className="w-full rounded-xl border border-ink/10 bg-canvas py-2.5 pl-10 pr-4 text-xs outline-none focus:border-primary-600 sm:w-64" /></div>
        </div>
        <div className="hidden grid-cols-[minmax(0,2fr)_1fr_0.6fr_0.8fr_40px] gap-4 border-b border-ink/8 bg-canvas/60 px-6 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-ink/30 md:grid"><span>Name</span><span>Collection</span><span>Chunks</span><span>Uploaded</span><span /></div>
        <div className="divide-y divide-ink/8">
          {filtered.map((document) => <div key={document.name} className="grid gap-3 px-5 py-4 transition hover:bg-primary-50/30 md:grid-cols-[minmax(0,2fr)_1fr_0.6fr_0.8fr_40px] md:items-center md:gap-4 md:px-6">
            <div className="flex min-w-0 items-center gap-3"><span className={`grid size-10 shrink-0 place-items-center rounded-xl text-[9px] font-bold tracking-wide ${document.color}`}>{document.type}</span><div className="min-w-0"><p className="truncate text-sm font-semibold">{document.name}</p><p className="mt-0.5 text-[10px] text-ink/35">{document.size} · Indexed</p></div></div>
            <span className="w-fit rounded-full bg-ink/5 px-2.5 py-1 text-[10px] font-medium text-ink/55">{document.collection}</span><span className="hidden text-xs text-ink/45 md:block">{document.chunks}</span><span className="hidden text-xs text-ink/45 md:block">{document.date}</span><button aria-label={`More options for ${document.name}`} className="hidden size-8 place-items-center rounded-lg text-ink/35 hover:bg-ink/5 hover:text-ink md:grid">•••</button>
          </div>)}
          {filtered.length === 0 && <div className="px-6 py-14 text-center"><SearchIcon className="mx-auto size-6 text-ink/20" /><p className="mt-3 text-sm font-semibold">No documents found</p><p className="mt-1 text-xs text-ink/40">Try a different search term.</p></div>}
        </div>
      </section>
    </div>
  );
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
