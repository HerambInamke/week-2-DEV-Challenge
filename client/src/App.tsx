import { lazy, Suspense, useState } from "react"

const MultiverseScene = lazy(() => import("./MultiverseScene"))

type IconProps = {
  name: string

  size?: number
}

function Icon({ name, size = 18 }: IconProps) {
  const paths: Record<string, React.ReactNode> = {
    arrow: (
      <>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </>
    ),

    branch: (
      <>
        <circle cx="6" cy="5" r="2" />
        <circle cx="6" cy="19" r="2" />
        <circle cx="18" cy="5" r="2" />
        <path d="M6 7v10M6 13h5a7 7 0 0 0 7-6" />
      </>
    ),

    cube: (
      <>
        <path d="m12 3 9 5v8l-9 5-9-5V8l9-5ZM3 8l9 5 9-5M12 13v8" />
      </>
    ),

    code: (
      <>
        <path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 20" />
      </>
    ),

    check: <path d="m5 12 4 4L19 6" />,

    close: <path d="m6 6 12 12M6 18 18 6" />,

    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6M12 7v.1" />
      </>
    ),

    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),

    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),

    bolt: <path d="m13 2-9 12h7l-1 8 10-13h-7l0-7Z" />,
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.branch}
    </svg>
  )
}

const scenarios = [
  { label: "Data cleanup", text: "Delete old user records", category: "data" },

  {
    label: "Access control",

    text: "Give the team access to customer data",

    category: "access",
  },

  {
    label: "System operations",

    text: "Restart services that are not responding",

    category: "system",
  },
]

type AnalysisBranch = {
  id: string
  title: string
  assumption: string
  explanation: string
  operation: string
  where: Record<string, unknown>
  update_set?: Record<string, unknown> | null
  affected_ids: string[]
  affected_count: number
}

type AnalyzeResponse = {
  status: "ok" | "unsupported" | "incomplete"
  reason?: string
  source?: string
  fallback_reason?: string | null
  model_info?: {
    model?: string
    mode?: string
  }
  domain?: string
  world?: {
    entity: string
    today?: string
    record_count: number
  }
  branches?: AnalysisBranch[]
  comparison?: {
    diverges: boolean
    distinct_sets: number
    only_in: Record<string, string[]>
    common_ids: string[]
  }
  ambiguous_terms?: Array<{
    term: string
    description?: string
  }>
  suggested_rewrite?: string
  warnings?: string[]
}

type BranchView = {
  id: string
  title: string
  interpretation: string
  outcome: string
  detail: string
  risk: string
  metric: string
  metricLabel: string
  code: string
  affectedCount: number
}

export default function App() {
  const [instruction, setInstruction] = useState(scenarios[0].text)
  const [phase, setPhase] =
    useState<"edit" | "loading" | "explore" | "compare">("edit")
  const [selected, setSelected] = useState<number | null>(null)
  const [detailTab, setDetailTab] = useState<"overview" | "trace" | "impact">(
    "overview",
  )
  const [error, setError] = useState("")
  const [modal, setModal] = useState<"about" | "history" | null>(null)
  const [history, setHistory] = useState<string[]>([])
  const [copied, setCopied] = useState(false)
  const [hovered, setHovered] = useState<number | null>(null)
  const [analyzedInstruction, setAnalyzedInstruction] = useState("")
  const [sceneReady, setSceneReady] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResponse | null>(
    null,
  )

  const realities: BranchView[] = (analysisResult?.branches ?? []).map(
    (branch) => {
      const entity = analysisResult?.world?.entity ?? "synthetic records"
      const operationText: Record<string, string> = {
        delete: "deleted",
        archive: "archived",
        update: "updated",
        flag: "flagged",
      }
      const count = branch.affected_count
      return {
        id: branch.id,
        title: branch.title,
        interpretation: branch.assumption || branch.explanation,
        outcome: `${count.toLocaleString()} ${entity} ${operationText[branch.operation] ?? "matched"}`,
        detail: `${count.toLocaleString()} of ${analysisResult?.world?.record_count ?? 0} synthetic ${entity} records matched this interpretation. ${branch.explanation}`,
        risk: "Simulated outcome",
        metric: count.toLocaleString(),
        metricLabel: `synthetic ${entity} records matched`,
        code: JSON.stringify(
          {
            operation: branch.operation,
            where: branch.where,
            update_set: branch.update_set ?? undefined,
          },
          null,
          2,
        ),
        affectedCount: count,
      }
    },
  )

  const previewRealities: BranchView[] = [
    {
      id: "A",
      title: "A world of intention",
      interpretation: "A possible reading of the instruction.",
      outcome: "Awaiting analysis",
      detail: "No simulation has run yet.",
      risk: "",
      metric: "0",
      metricLabel: "synthetic records matched",
      code: "{}",
      affectedCount: 0,
    },
    {
      id: "B",
      title: "A different reading",
      interpretation: "Another plausible reading.",
      outcome: "Awaiting analysis",
      detail: "No simulation has run yet.",
      risk: "",
      metric: "0",
      metricLabel: "synthetic records matched",
      code: "{}",
      affectedCount: 0,
    },
    {
      id: "C",
      title: "An unintended consequence",
      interpretation: "A third possible reading.",
      outcome: "Awaiting analysis",
      detail: "No simulation has run yet.",
      risk: "",
      metric: "0",
      metricLabel: "synthetic records matched",
      code: "{}",
      affectedCount: 0,
    },
  ]

  const visualRealities = realities.length
    ? realities.slice(0, 3)
    : previewRealities
  const displayRealities = realities.length ? realities : previewRealities
  const impactValues = realities.map((reality) => reality.affectedCount)

  const maxImpact = Math.max(...impactValues, 1)

  const ready = phase === "explore" || phase === "compare"
  const corrected = analysisResult?.suggested_rewrite?.trim() ?? ""

  function reset() {
    setPhase("edit")

    setSelected(null)

    setError("")

    setAnalysisResult(null)
  }

  async function explore() {
    if (instruction.trim().length < 10) {
      setError("Add a little more context — at least 10 characters.")

      return
    }

    setError("")

    setSelected(null)

    setPhase("loading")

    setAnalyzedInstruction(instruction)
    setAnalysisResult(null)

    try {
      const apiBase =
        import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? ""
      const response = await fetch(`${apiBase}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: instruction.trim(),
          scenario: "auto",
        }),
      })
      const result = (await response.json()) as AnalyzeResponse & {
        detail?: string
      }
      if (!response.ok) {
        throw new Error(result.detail || "The analysis request failed.")
      }
      if (result.status !== "ok") {
        setAnalysisResult(result)
        setPhase("edit")
        setError(
          result.reason || "The backend could not analyze this instruction.",
        )
        return
      }
      setAnalysisResult(result)
      setAnalyzedInstruction(instruction.trim())
      setPhase("compare")
      setHistory((items) => [instruction.trim(), ...items].slice(0, 8))
    } catch (requestError) {
      setPhase("edit")
      setError(
        requestError instanceof TypeError
          ? "Could not reach the analysis API. Start the backend with: uvicorn ai.api:app --reload --port 8000"
          : requestError instanceof Error
            ? requestError.message
            : "The analysis request failed.",
      )
    }
  }

  return (
    <div className={`app phase-${phase}`}>
      <main>
        <section className="intro">
          <div>
            <div className="eyebrow">
              <span className="status-dot" /> THE AMBIGUITY EXPLORER{" "}
              <span className="eyebrow-line" /> EXPERIMENT 001
            </div>
            <h1>
              One instruction.
              <br />
              <span>Infinite ways</span>
              <br />
              to go wrong.
            </h1>
            <p>
              Language isn’t a straight line. Explore the space
              <br />
              between what you said and what your AI understood.
            </p>
          </div>
          <div className="intro-note">
            <Icon name="shield" size={16} />
            <span>
              A safe space for dangerous possibilities.
              <br />
              <strong>No real systems. No real consequences.</strong>
            </span>
          </div>
          <div className="intro-actions">
            <button onClick={() => setModal("history")}>
              <Icon name="clock" size={15} /> Run history{" "}
              <span>{history.length.toString().padStart(2, "0")}</span>
            </button>
            <button onClick={() => setModal("about")}>
              How it works <Icon name="info" size={15} />
            </button>
          </div>
        </section>
        <section
          className={`exploration-stage ${
            phase === "loading" ? "is-loading" : ""
          }`}
        >
          <div className="workspace-body">
            <div className="editor-side">
              <div className="section-label">
                <span className="step">01</span> THE INSTRUCTION{" "}
                <span className="plain-label">INPUT</span>
              </div>
              <h2>Start with a few words.</h2>
              <p className="helper">
                We’ll test plausible readings against the same synthetic world.
              </p>
              <div className={`editor ${error ? "invalid" : ""}`}>
                <div className="editor-head">
                  <span>
                    <Icon name="code" size={14} /> instruction.txt
                  </span>
                  <span>PLAIN TEXT</span>
                </div>
                <div className="textarea-wrap">
                  <span className="line-number">1</span>
                  <textarea
                    aria-label="Instruction to explore"
                    value={instruction}
                    onChange={(e) => {
                      setInstruction(e.target.value)

                      reset()
                    }}
                    disabled={phase === "loading"}
                    spellCheck={false}
                  />
                </div>
                <div className="editor-foot">
                  <span>
                    <span className="small-dot" /> Natural language
                  </span>
                  <span>{instruction.length} characters</span>
                </div>
              </div>
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <div className="examples">
                <span>TRY AN EXAMPLE</span>
                <div>
                  {scenarios.map((s) => (
                    <button
                      key={s.category}
                      className={instruction === s.text ? "active" : ""}
                      onClick={() => {
                        setInstruction(s.text)

                        reset()
                      }}
                    >
                      {s.label}
                      <Icon name="arrow" size={12} />
                    </button>
                  ))}
                </div>
              </div>
              <button
                className="explore-button"
                disabled={phase === "loading"}
                onClick={explore}
              >
                <Icon
                  name={phase === "loading" ? "branch" : "bolt"}
                  size={17}
                />
                {phase === "loading"
                  ? "Opening parallel realities…"
                  : "Explore Realities"}
                <span>
                  {phase === "loading" ? (
                    <span className="spinner" />
                  ) : (
                    <Icon name="arrow" size={18} />
                  )}
                </span>
              </button>
              <div className="button-note">
                <Icon name="shield" size={12} /> Synthetic simulation only ·
                Instructions may be sent to the configured model provider
              </div>
            </div>
            <div
              className={`visual-side ${sceneReady ? "has-webgl" : ""} ${
                phase !== "edit" ? "awakened" : ""
              } ${selected !== null && selected < 3 ? `focused focus-${selected}` : ""} ${
                hovered !== null ? `hover-${hovered}` : ""
              }`}
            >
              <div className="visual-top">
                <span>
                  <span className="status-dot" /> THE POSSIBILITY SPACE
                </span>
                <span className="mono">3 WORLDS / 1 ORIGIN</span>
              </div>
              <Suspense fallback={null}>
                <MultiverseScene
                  selected={selected !== null && selected < 3 ? selected : null}
                  hovered={hovered}
                  loading={phase === "loading"}
                  onReady={setSceneReady}
                />
              </Suspense>
              <div className="scene-camera">
                <div className="scene-floor" />
                <div className="scene-haze" />
                <svg
                  className="light-paths"
                  viewBox="0 0 800 680"
                  fill="none"
                  aria-hidden="true"
                >
                  <defs>
                    <filter id="pathGlow">
                      <feGaussianBlur stdDeviation="5" />
                    </filter>
                  </defs>
                  {[
                    "M400 565 C390 390 110 450 155 295",

                    "M400 565 C410 390 435 310 435 200",

                    "M400 565 C510 530 710 490 675 340",
                  ].map((d, i) => (
                    <g key={d} className={`light-path light-path-${i}`}>
                      <path d={d} filter="url(#pathGlow)" strokeWidth="7" />
                      <path d={d} strokeWidth="1.5" />
                    </g>
                  ))}
                </svg>
                <div className="particles" aria-hidden="true">
                  {Array.from({ length: 30 }, (_, i) => (
                    <i
                      key={i}
                      style={{
                        left: `${(i * 37 + 9) % 100}%`,

                        top: `${(i * 23 + 7) % 87}%`,

                        animationDelay: `${i * -0.7}s`,
                      }}
                    />
                  ))}
                </div>
                {visualRealities.map((r, i) => (
                  <button
                    key={i}
                    aria-label={`Explore Reality 0${i + 1}: ${r.title}`}
                    aria-pressed={selected === i}
                    disabled={phase === "loading"}
                    className={`world world-${i}`}
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() => setHovered(null)}
                    onFocus={() => setHovered(i)}
                    onBlur={() => setHovered(null)}
                    onClick={() => {
                      if (ready) setSelected(selected === i ? null : i)
                      else explore()
                    }}
                  >
                    <span className="portal-shadow" />
                    <span className="portal-assembly">
                      <span className="portal-aura" />
                      <span className="portal-back" />
                      <span className="portal-ring ring-back" />
                      <span className="portal-interior">
                        <span className="dimension-grid" />
                        <span className="inner-star" />
                        <span className="glass-shard shard-one" />
                        <span className="glass-shard shard-two" />
                        <span className="glass-shard shard-three" />
                      </span>
                      <span className="portal-ring ring-front" />
                      <span className="portal-highlight" />
                    </span>
                    <span className="world-label">
                      <span className="world-index">
                        <b className="reality-number">0{i + 1}</b> <span />{" "}
                        {["INTENDED", "ALTERNATIVE", "DANGEROUS"][i]}
                      </span>
                      <strong>
                        {ready
                          ? r.title
                          : [
                              "A world of intention",

                              "A different reading",

                              "An unintended consequence",
                            ][i]}
                      </strong>
                      <span className="world-preview">
                        {ready ? r.outcome : "Follow this interpretation"}{" "}
                        <Icon name="arrow" size={13} />
                      </span>
                    </span>
                  </button>
                ))}
                <div className="origin-object">
                  <span>
                    <Icon name="branch" size={20} />
                  </span>
                  <div>
                    <small>THE POINT OF DIVERGENCE</small>
                    <p>
                      {phase === "edit" ? instruction : analyzedInstruction}
                    </p>
                  </div>
                </div>
              </div>
              <div className="visual-bottom" aria-live="polite">
                <span>
                  <i />{" "}
                  {phase === "loading"
                    ? "BRANCHING REALITIES…"
                    : selected !== null
                      ? `INSIDE REALITY 0${selected + 1}`
                      : "HOVER TO DISCOVER · CLICK TO ENTER"}
                </span>
                <span>∞ POSSIBILITIES</span>
              </div>
              {selected !== null && (
                <button
                  className="return-worlds"
                  onClick={() => {
                    setSelected(null)

                    setPhase("compare")
                  }}
                >
                  ← Return to all realities
                </button>
              )}
              {selected !== null && ready && (
                <div className={`immersive-preview reality-${selected}`}>
                  <span className="mini-eyebrow">
                    REALITY 0{selected + 1} / SIMULATED OUTCOME
                  </span>
                  <h3>{realities[selected].outcome}</h3>
                  <p>{realities[selected].detail}</p>
                  <span className="risk risk-neutral">
                    Synthetic simulation
                  </span>
                </div>
              )}
            </div>
          </div>
        </section>
        <section
          className={`realities-section ${
            phase === "explore" || phase === "compare" ? "revealed" : ""
          }`}
        >
          {ready && analysisResult && (
            <p className="simulation-notice">
              <Icon name="shield" size={14} /> Synthetic scenario ·{" "}
              {analysisResult.source === "fixture_fallback"
                ? "fixture-backed result; see fallback details below"
                : "interpreted by the configured model and simulated on synthetic records"}
              {analysisResult.fallback_reason
                ? ` · Fallback: ${analysisResult.fallback_reason}`
                : ""}
            </p>
          )}
          <div className="results-heading">
            <div className="section-label">
              <span className="step">02</span> PARALLEL REALITIES{" "}
              <span className="reality-count">
                {analysisResult?.branches?.length ?? 3} BRANCHES
              </span>
            </div>
            <span className="results-hint">
              {phase === "edit"
                ? "Your possibilities will unfold here"
                : phase === "loading"
                  ? "Tracing possible consequences…"
                  : "Same words. Different worlds."}
            </span>
            {(phase === "explore" || phase === "compare") && (
              <button
                className="compare-button"
                onClick={() => {
                  setPhase(phase === "compare" ? "explore" : "compare")

                  setSelected(null)
                }}
              >
                {phase === "compare" ? "Explore branches" : "Compare outcomes"}
                <Icon name="arrow" size={14} />
              </button>
            )}
          </div>
          <div className="reality-grid">
            {displayRealities.map((r, i) => (
              <button
                key={`${r.id}-${i}`}
                disabled={phase === "edit" || phase === "loading"}
                onClick={() => {
                  setSelected(selected === i ? null : i)

                  setDetailTab("overview")
                }}
                className={`reality-card reality-${i} ${
                  selected === i ? "selected" : ""
                }`}
                style={{ animationDelay: `${i * 150}ms` }}
              >
                <div className="card-top">
                  <span>
                    <span className="branch-dot" /> REALITY 0{i + 1}
                  </span>
                  <Icon name="branch" size={16} />
                </div>
                {phase === "edit" || phase === "loading" ? (
                  <>
                    <h3>
                      {
                        [
                          "The intended interpretation",

                          "The alternative reading",

                          "The dangerous assumption",
                        ][i]
                      }
                    </h3>
                    <p>
                      {
                        [
                          "A cautious, recoverable path through your instruction.",

                          "A plausible interpretation with unexpected trade-offs.",

                          "A literal reading. An irreversible ripple effect.",
                        ][i]
                      }
                    </p>
                    <div className="card-bottom">
                      <span className="pending-dot" /> Awaiting instruction{" "}
                      <Icon name="arrow" size={14} />
                    </div>
                  </>
                ) : (
                  <>
                    <h3>{r.title}</h3>
                    <p>{r.interpretation}</p>
                    <div className="card-bottom">
                      <span className="risk risk-neutral">{r.risk}</span>
                      <span>
                        {selected === i ? "Close branch" : "Enter reality"}
                        <Icon name="arrow" size={14} />
                      </span>
                    </div>
                  </>
                )}
              </button>
            ))}
          </div>
          {selected !== null &&
            (phase === "explore" || phase === "compare") && (
              <div className={`branch-detail reality-${selected}`}>
                <div className="branch-detail-heading">
                  <div>
                    <span className="mini-eyebrow">
                      REALITY 0{selected + 1} / BRANCH DETAILS
                    </span>
                    <h2>{realities[selected].title}</h2>
                    <p className="branch-detail-subtitle">
                      {realities[selected].outcome}
                    </p>
                  </div>
                  <button
                    className="detail-close"
                    onClick={() => setSelected(null)}
                  >
                    Close details <Icon name="close" size={15} />
                  </button>
                </div>
                <div
                  className="detail-tabs"
                  role="tablist"
                  aria-label="Branch detail pages"
                >
                  {(["overview", "trace", "impact"] as const).map((tab) => (
                    <button
                      key={tab}
                      role="tab"
                      aria-selected={detailTab === tab}
                      className={detailTab === tab ? "active" : ""}
                      onClick={() => setDetailTab(tab)}
                    >
                      {tab === "overview"
                        ? "Overview"
                        : tab === "trace"
                          ? "Action path"
                          : "Safety & impact"}
                    </button>
                  ))}
                </div>
                <div className="detail-page" key={detailTab}>
                  {detailTab === "overview" && (
                    <>
                      <div className="detail-copy">
                        <span className="detail-label">INTERPRETATION</span>
                        <p>{realities[selected].interpretation}</p>
                        <span className="detail-label">
                          WHAT HAPPENS IN THIS SCENARIO
                        </span>
                        <p>{realities[selected].detail}</p>
                      </div>
                      <div className="detail-summary">
                        <span className="risk risk-neutral">
                          {realities[selected].risk}
                        </span>
                        <strong className="impact-number">
                          {realities[selected].metric}
                        </strong>
                        <span>{realities[selected].metricLabel}</span>
                      </div>
                    </>
                  )}
                  {detailTab === "trace" && (
                    <>
                      <div className="trace-steps">
                        <div>
                          <span>01</span>
                          <p>
                            <strong>Read the instruction</strong>
                            <small>{analyzedInstruction}</small>
                          </p>
                        </div>
                        <div>
                          <span>02</span>
                          <p>
                            <strong>Apply this interpretation</strong>
                            <small>{realities[selected].interpretation}</small>
                          </p>
                        </div>
                        <div>
                          <span>03</span>
                          <p>
                            <strong>Simulate the resulting action</strong>
                            <small>{realities[selected].outcome}</small>
                          </p>
                        </div>
                      </div>
                      <pre>
                        <code>{realities[selected].code}</code>
                      </pre>
                    </>
                  )}
                  {detailTab === "impact" && (
                    <>
                      <div className="impact-detail">
                        <span className="risk risk-neutral">
                          {realities[selected].risk}
                        </span>
                        <strong className="impact-number">
                          {realities[selected].metric}
                        </strong>
                        <p>{realities[selected].metricLabel}</p>
                        <div className="impact-meter">
                          <span
                            style={{
                              width: `${(impactValues[selected] / maxImpact) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                      <div className="detail-copy">
                        <span className="detail-label">SAFETY REVIEW</span>
                        <p>{realities[selected].detail}</p>
                        <p className="simulation-note-small">
                          Deterministic simulation on synthetic records. No
                          action is executed against a live system.
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          {phase === "compare" && (
            <div className="comparison">
              <div className="comparison-title">
                <Icon name="branch" />
                <div>
                  <h2>
                    {analysisResult?.comparison?.diverges
                      ? "The simulated paths diverge"
                      : "The simulated paths match"}
                  </h2>
                  <p>
                    {analysisResult?.comparison?.diverges
                      ? `${analysisResult.comparison.distinct_sets} distinct simulated outcome patterns across the interpretations.`
                      : "The interpretations led to the same synthetic final state."}
                  </p>
                </div>
                <span
                  className={`risk ${
                    analysisResult?.comparison?.diverges ? "risk-2" : "risk-0"
                  }`}
                >
                  {analysisResult?.comparison?.diverges
                    ? "DIVERGENT OUTCOMES"
                    : "MATCHING OUTCOMES"}
                </span>
              </div>
              <div className="comparison-grid">
                {realities.map((r, i) => (
                  <div
                    className={`comparison-world reality-${i}`}
                    key={r.title}
                  >
                    <span className="mini-eyebrow">REALITY 0{i + 1}</span>
                    <h3>{r.outcome}</h3>
                    <div className="impact-meter">
                      <span
                        style={{
                          width: `${(impactValues[i] / maxImpact) * 100}%`,
                        }}
                      />
                    </div>
                    <strong className="impact-number">{r.metric}</strong>
                    <p>{r.metricLabel}</p>
                    <span className="risk risk-neutral">{r.risk}</span>
                  </div>
                ))}
              </div>
              <div className="corrected">
                <div className="corrected-heading">
                  <span>
                    <Icon name="shield" size={17} /> Suggested clarification
                  </span>
                  <button
                    onClick={async () => {
                      try {
                        if (!corrected) return
                        await navigator.clipboard.writeText(corrected)

                        setCopied(true)

                        setTimeout(() => setCopied(false), 2000)
                      } catch {
                        setError(
                          "Clipboard unavailable. Select the corrected instruction to copy it.",
                        )
                      }
                    }}
                  >
                    <Icon name={copied ? "check" : "code"} size={14} />
                    {copied ? "Copied" : "Copy instruction"}
                  </button>
                </div>
                <p>
                  {corrected || "No clarification was returned for this run."}
                </p>
                {corrected && (
                  <button
                    className="use-instruction"
                    onClick={() => {
                      setInstruction(corrected)
                      reset()
                      window.scrollTo({ top: 0, behavior: "smooth" })
                    }}
                  >
                    Use in editor <Icon name="arrow" size={14} />
                  </button>
                )}
              </div>
            </div>
          )}
        </section>
        <footer>
          <span>
            <Icon name="branch" size={14} /> Break the interpretation. Not
            production.
          </span>
          <span>
            SYNTHETIC SIMULATION <i /> NO LIVE ACTIONS EXECUTED
          </span>
          <span className="footer-version">SCM / 001</span>
        </footer>
      </main>
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(null)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={modal === "about" ? "How it works" : "Run history"}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              aria-label="Close dialog"
              onClick={() => setModal(null)}
            >
              <Icon name="close" />
            </button>
            <span className="mini-eyebrow">SEMANTIC CHAOS MONKEY</span>
            <h2>
              {modal === "about"
                ? "Explore what you didn’t say."
                : "Your previous explorations"}
            </h2>
            {modal === "about" ? (
              <>
                <p>
                  The backend generates supported interpretations, validates
                  each declarative plan, and simulates the resulting actions on
                  synthetic records. Unsupported instructions are reported
                  instead of being mapped to a canned scenario.
                </p>
                <ol>
                  <li>Write an instruction with room for interpretation.</li>
                  <li>
                    Enter each reality to inspect its simulated consequences.
                  </li>
                  <li>
                    Compare outcomes and take away a more precise instruction.
                  </li>
                </ol>
                <p className="modal-disclaimer">
                  The backend analyzes instructions and runs validated plans
                  against synthetic data only. No real commands are executed.
                  Depending on backend configuration, instruction text may be
                  sent to a model provider.
                </p>
              </>
            ) : history.length ? (
              <div className="history-list">
                {history.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInstruction(h)

                      reset()

                      setModal(null)
                    }}
                  >
                    <span>
                      <small>
                        RUN {String(history.length - i).padStart(2, "0")}
                      </small>
                      {h}
                    </span>
                    <Icon name="arrow" />
                  </button>
                ))}
              </div>
            ) : (
              <p>
                No explorations yet. Your runs will appear here during this
                session.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
