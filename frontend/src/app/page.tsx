const ArrowUpRight = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 fill-none stroke-current stroke-[1.8]">
    <path d="M5 15 15 5M7 5h8v8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const Spark = ({ className = "" }: { className?: string }) => (
  <svg aria-hidden="true" viewBox="0 0 24 24" className={`fill-current ${className}`}>
    <path d="M12 0c.8 7.7 4.3 11.2 12 12-7.7.8-11.2 4.3-12 12C11.2 16.3 7.7 12.8 0 12 7.7 11.2 11.2 7.7 12 0Z" />
  </svg>
);

const FileIcon = ({ type }: { type: string }) => (
  <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-[9px] font-bold tracking-wider text-primary-700">
    {type}
  </div>
);

export default function Home() {
  return (
    <main className="overflow-hidden bg-canvas text-ink">
      <section className="relative min-h-screen border-b border-ink/10">
        <div className="hero-glow absolute inset-0" aria-hidden="true" />
        <nav className="relative z-20 mx-auto flex max-w-7xl items-center justify-between px-5 py-6 sm:px-8 lg:px-12">
          <a href="#top" className="flex items-center gap-2.5" aria-label="pRAwG home">
            <span className="grid size-9 place-items-center rounded-xl bg-primary-600 text-white shadow-[0_8px_24px_rgba(92,68,199,0.25)]">
              <Spark className="size-4" />
            </span>
            <span className="text-xl font-semibold tracking-[-0.04em]">pRAwG</span>
          </a>

          <div className="hidden items-center gap-8 text-sm font-medium text-ink/60 md:flex">
            <a href="#how-it-works" className="transition-colors hover:text-ink">How it works</a>
            <a href="#features" className="transition-colors hover:text-ink">Features</a>
            <a href="#privacy" className="transition-colors hover:text-ink">Privacy</a>
          </div>

          <a
            href="#get-started"
            className="group flex items-center gap-2 rounded-full border border-ink/15 bg-white/60 px-4 py-2.5 text-sm font-semibold backdrop-blur transition hover:border-primary-600 hover:text-primary-700"
          >
            Open app
            <ArrowUpRight />
          </a>
        </nav>

        <div id="top" className="relative z-10 mx-auto grid max-w-7xl items-center gap-14 px-5 pb-20 pt-14 sm:px-8 sm:pt-20 lg:grid-cols-[0.9fr_1.1fr] lg:px-12 lg:pb-28 lg:pt-24">
          <div>
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-primary-600/15 bg-primary-50/80 px-3.5 py-2 text-xs font-semibold text-primary-700">
              Your knowledge, made conversational
            </div>
            <h1 className="max-w-2xl text-[clamp(3.2rem,7vw,6.4rem)] font-semibold leading-[0.91] tracking-[-0.075em]">
              Ask more of what you <span className="text-primary-600">already know.</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-ink/60 sm:text-xl">
              Turn scattered documents into a private, intelligent knowledge base. Add your files, ask naturally, and get answers grounded in your own material.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <a
                href="#get-started"
                className="group inline-flex items-center justify-center gap-2 rounded-full bg-primary-600 px-6 py-3.5 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(92,68,199,0.25)] transition hover:-translate-y-0.5 hover:bg-primary-700"
              >
                Build your knowledge base
                <ArrowUpRight />
              </a>
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center rounded-full border border-ink/15 bg-white/60 px-6 py-3.5 text-sm font-semibold backdrop-blur transition hover:border-ink/30"
              >
                See how it works
              </a>
            </div>
            <div className="mt-10 flex items-center gap-4 text-xs font-medium text-ink/50">
              <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-secondary-600" />PDF, DOCX, TXT & MD</span>
              <span className="h-3 w-px bg-ink/15" />
              <span>No generic answers</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-2xl lg:ml-auto">
            <div className="absolute -left-14 top-14 size-32 rounded-full bg-secondary-400/40 blur-3xl" aria-hidden="true" />
            <div className="app-shell relative rounded-[2rem] border border-white/80 bg-white/75 p-2.5 shadow-[0_40px_100px_rgba(33,25,59,0.16)] backdrop-blur-xl">
              <div className="overflow-hidden rounded-[1.5rem] border border-ink/10 bg-[#f8f7fb]">
                <div className="flex items-center justify-between border-b border-ink/10 bg-white/80 px-5 py-3.5">
                  <div className="flex gap-1.5" aria-hidden="true">
                    <span className="size-2.5 rounded-full bg-[#ff8a80]" />
                    <span className="size-2.5 rounded-full bg-[#ffd166]" />
                    <span className="size-2.5 rounded-full bg-secondary-500" />
                  </div>
                  <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink/35">Knowledge workspace</span>
                  <div className="size-6 rounded-full bg-primary-100" />
                </div>

                <div className="grid min-h-[430px] sm:grid-cols-[155px_1fr]">
                  <aside className="hidden border-r border-ink/10 bg-white/45 p-4 sm:block">
                    <div className="mb-5 flex items-center gap-2 text-xs font-semibold">
                      <span className="grid size-6 place-items-center rounded-lg bg-primary-600 text-white"><Spark className="size-2.5" /></span>
                      pRAwG
                    </div>
                    <p className="mb-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-ink/35">Collections</p>
                    <div className="space-y-1 text-[11px] font-medium text-ink/55">
                      <div className="rounded-lg bg-primary-50 px-2.5 py-2 text-primary-700">Research notes</div>
                      <div className="px-2.5 py-2">Project docs</div>
                      <div className="px-2.5 py-2">Reading list</div>
                    </div>
                  </aside>

                  <div className="flex flex-col p-4 sm:p-6">
                    <div className="mb-5 flex items-center justify-between">
                      <div>
                        <p className="text-xs font-semibold">Research notes</p>
                        <p className="mt-0.5 text-[10px] text-ink/40">12 documents · ready to search</p>
                      </div>
                      <span className="rounded-full bg-secondary-200 px-2.5 py-1 text-[9px] font-bold text-secondary-900">INDEXED</span>
                    </div>

                    <div className="mb-4 flex items-center gap-3 rounded-xl border border-ink/8 bg-white px-3 py-2.5 shadow-sm">
                      <FileIcon type="PDF" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[11px] font-semibold">attention-is-all-you-need.pdf</p>
                        <p className="mt-0.5 text-[9px] text-ink/40">15 pages · 34 chunks</p>
                      </div>
                      <span className="size-2 rounded-full bg-secondary-500" />
                    </div>

                    <div className="ml-auto max-w-[78%] rounded-2xl rounded-br-sm bg-primary-600 px-4 py-3 text-[11px] leading-5 text-white shadow-lg shadow-primary-600/15">
                      What makes the transformer architecture more efficient than recurrent models?
                    </div>

                    <div className="mt-3 max-w-[92%] rounded-2xl rounded-bl-sm border border-ink/8 bg-white px-4 py-3 text-[11px] leading-[1.65] text-ink/70 shadow-sm">
                      <div className="mb-2 flex items-center gap-2 font-semibold text-ink">
                        <Spark className="size-3 text-primary-600" />
                        Answer from your documents
                      </div>
                      Transformers process all sequence positions in parallel, removing the sequential computation required by recurrent networks. This makes training faster while attention connects distant context directly.
                      <div className="mt-3 flex items-center gap-1.5 text-[9px] font-semibold text-primary-700">
                        <span className="rounded bg-primary-50 px-1.5 py-0.5">Source 1</span>
                        <span className="text-ink/30">Page 6</span>
                      </div>
                    </div>

                    <div className="mt-auto flex items-center rounded-xl border border-ink/10 bg-white px-4 py-3 text-[10px] text-ink/35 shadow-sm">
                      Ask a follow-up question...
                      <span className="ml-auto grid size-7 place-items-center rounded-lg bg-primary-600 text-white"><ArrowUpRight /></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="absolute -bottom-5 -left-4 flex items-center gap-2 rounded-full border border-white bg-white/90 px-4 py-2.5 text-[11px] font-semibold shadow-xl backdrop-blur sm:-left-8">
              <span className="grid size-6 place-items-center rounded-full bg-secondary-300"><Spark className="size-2.5 text-secondary-900" /></span>
              Grounded answers, every time
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl px-5 py-24 sm:px-8 lg:px-12 lg:py-32">
        <div className="grid gap-12 lg:grid-cols-[0.72fr_1.28fr] lg:gap-20">
          <div>
            <p className="eyebrow">A calmer way to know more</p>
            <h2 className="mt-5 text-4xl font-semibold leading-tight tracking-[-0.055em] sm:text-5xl">From document pile to clear answer.</h2>
            <p className="mt-5 max-w-md leading-7 text-ink/55">pRAwG handles the retrieval work behind the scenes, so you can stay focused on the question that matters.</p>
          </div>
          <div className="grid gap-px overflow-hidden rounded-[1.75rem] border border-ink/10 bg-ink/10 sm:grid-cols-3">
            {[
              ["01", "Add your sources", "Bring PDFs, documents, notes, and scanned files into a collection built around your work."],
              ["02", "We map the meaning", "Your content is extracted, split into useful context, and indexed for semantic search."],
              ["03", "Ask in plain language", "Get a conversational answer grounded in the most relevant parts of your own sources."],
            ].map(([number, title, body]) => (
              <article key={number} className="group bg-white p-6 transition-colors hover:bg-primary-50/60 sm:p-7">
                <span className="font-mono text-xs font-semibold text-primary-600">{number}</span>
                <div className="my-8 grid size-11 place-items-center rounded-2xl bg-primary-50 text-primary-600 transition group-hover:bg-primary-600 group-hover:text-white">
                  <Spark className="size-4" />
                </div>
                <h3 className="text-lg font-semibold tracking-[-0.025em]">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-ink/50">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="bg-ink px-5 py-24 text-white sm:px-8 lg:px-12 lg:py-32">
        <div className="mx-auto max-w-7xl">
          <div className="mb-14 flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="eyebrow text-secondary-400">Built around your context</p>
              <h2 className="mt-5 max-w-2xl text-4xl font-semibold leading-tight tracking-[-0.055em] sm:text-5xl">Knowledge that stays close to the source.</h2>
            </div>
            <p className="max-w-sm text-sm leading-6 text-white/50">Search precisely, trace each answer, and keep every project organized in its own focused collection.</p>
          </div>

          <div className="grid gap-4 lg:grid-cols-12">
            <article className="relative min-h-[340px] overflow-hidden rounded-[1.75rem] bg-primary-600 p-7 sm:p-9 lg:col-span-7">
              <div className="relative z-10 max-w-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/55">Semantic retrieval</p>
                <h3 className="mt-4 text-3xl font-semibold tracking-[-0.045em]">Find the idea, not just the exact phrase.</h3>
                <p className="mt-4 text-sm leading-6 text-white/65">Meaning-aware search surfaces the passages that actually answer your question—even when the wording is different.</p>
              </div>
              <div className="absolute -bottom-24 -right-14 size-[330px] rounded-full border border-white/15">
                <div className="absolute inset-10 rounded-full border border-white/20" />
                <div className="absolute inset-20 rounded-full border border-white/30" />
                <div className="absolute left-1/2 top-1/2 size-12 -translate-x-1/2 -translate-y-1/2 rounded-full bg-secondary-300 shadow-[0_0_80px_rgba(188,244,103,0.8)]" />
              </div>
            </article>

            <article className="relative min-h-[340px] overflow-hidden rounded-[1.75rem] bg-secondary-300 p-7 text-ink sm:p-9 lg:col-span-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">Source aware</p>
              <h3 className="mt-4 max-w-sm text-3xl font-semibold tracking-[-0.045em]">Answers you can verify.</h3>
              <div className="absolute bottom-8 left-7 right-7 space-y-2 sm:left-9 sm:right-9">
                {["Quarterly research.pdf · p. 12", "Project brief.docx · section 3"].map((source, index) => (
                  <div key={source} className="flex items-center gap-3 rounded-xl bg-ink px-4 py-3 text-xs font-medium text-white shadow-lg" style={{ transform: `translateX(${index * 10}px)` }}>
                    <span className="grid size-6 place-items-center rounded-md bg-white/10 text-[9px]">{index + 1}</span>
                    {source}
                  </div>
                ))}
              </div>
            </article>

            <article className="rounded-[1.75rem] border border-white/10 bg-white/[0.055] p-7 sm:p-9 lg:col-span-5">
              <div className="grid size-11 place-items-center rounded-2xl bg-white/10 text-secondary-300"><Spark className="size-4" /></div>
              <h3 className="mt-8 text-2xl font-semibold tracking-[-0.035em]">Collections with boundaries</h3>
              <p className="mt-3 text-sm leading-6 text-white/50">Separate clients, research areas, and projects so every answer draws from the right context.</p>
            </article>

            <article id="privacy" className="rounded-[1.75rem] border border-white/10 bg-white/[0.055] p-7 sm:p-9 lg:col-span-7">
              <div className="flex flex-col justify-between gap-8 sm:flex-row sm:items-end">
                <div className="max-w-md">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary-300">Container-first by design</p>
                  <h3 className="mt-4 text-2xl font-semibold tracking-[-0.035em]">Your knowledge base, under your control.</h3>
                  <p className="mt-3 text-sm leading-6 text-white/50">Run the stack in your own environment and keep your source material within infrastructure you manage.</p>
                </div>
                <div className="flex shrink-0 items-center gap-2 rounded-full border border-secondary-300/25 bg-secondary-300/10 px-4 py-2.5 text-xs font-semibold text-secondary-300">
                  <span className="size-2 rounded-full bg-secondary-300 shadow-[0_0_12px_rgba(188,244,103,0.8)]" />
                  Private by default
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="get-started" className="relative overflow-hidden px-5 py-24 sm:px-8 lg:px-12 lg:py-32">
        <div className="cta-grid absolute inset-0 opacity-35" aria-hidden="true" />
        <div className="relative mx-auto max-w-5xl text-center">
          <div className="mx-auto mb-8 grid size-14 place-items-center rounded-2xl bg-primary-600 text-white shadow-[0_16px_36px_rgba(92,68,199,0.25)]">
            <Spark className="size-5" />
          </div>
          <p className="eyebrow">Ready when your documents are</p>
          <h2 className="mx-auto mt-5 max-w-4xl text-[clamp(2.8rem,7vw,5.8rem)] font-semibold leading-[0.96] tracking-[-0.07em]">Make your knowledge useful again.</h2>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-ink/55">Start with one collection. Add the sources you trust. Ask the question you have been carrying around.</p>
          <a href="#top" className="mt-9 inline-flex items-center gap-2 rounded-full bg-ink px-7 py-4 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-primary-700">
            Start exploring
            <ArrowUpRight />
          </a>
        </div>
      </section>

      <footer className="border-t border-ink/10 px-5 py-8 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 text-xs text-ink/45 sm:flex-row">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <span className="grid size-7 place-items-center rounded-lg bg-primary-600 text-white"><Spark className="size-3" /></span>
            pRAwG
          </div>
          <p>Personalized retrieval. Answers grounded in you.</p>
          <a href="#top" className="font-semibold text-ink transition hover:text-primary-600">Back to top ↑</a>
        </div>
      </footer>
    </main>
  );
}
