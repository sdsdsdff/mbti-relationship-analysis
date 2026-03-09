"use client";

import { useMemo, useState } from "react";

const API_BASE_URL =
  (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function statItems(result) {
  if (!result) {
    return [];
  }

  return [
    {
      label: "Messages",
      value: result.artifacts?.conversation?.messages?.length ?? 0,
    },
    {
      label: "Participants",
      value: result.artifacts?.conversation?.participants?.length ?? 0,
    },
    {
      label: "Signals",
      value: result.artifacts?.signal_set?.signals?.length ?? 0,
    },
    {
      label: "Sections",
      value: result.report?.sections?.length ?? 0,
    },
  ];
}

export default function HomePage() {
  const [file, setFile] = useState(null);
  const [selfNames, setSelfNames] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const stats = useMemo(() => statItems(result), [result]);
  const sections = result?.report?.sections ?? [];
  const conversation = result?.artifacts?.conversation;

  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      setError("Please choose a transcript file first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("transcript", file);
    if (selfNames.trim()) {
      formData.append("self_names", selfNames.trim());
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || "Analysis failed.");
      }

      setResult(payload);
    } catch (submitError) {
      setError(submitError.message || "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Route B MVP</p>
        <h1>MBTI Relationship Analysis</h1>
        <p className="hero-copy">
          Upload a Markdown or TXT transcript, optionally tag your own speaker name,
          and review the existing Python pipeline output in a lightweight web UI.
        </p>
      </section>

      <section className="panel form-panel">
        <h2>Analyze Transcript</h2>
        <form onSubmit={handleSubmit} className="analysis-form">
          <label className="field">
            <span>Transcript file</span>
            <input
              type="file"
              accept=".md,.markdown,.txt,text/markdown,text/plain"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <label className="field">
            <span>Self name(s)</span>
            <input
              type="text"
              placeholder="Me, 我, Alice"
              value={selfNames}
              onChange={(event) => setSelfNames(event.target.value)}
            />
          </label>

          <div className="helper-text">
            The backend accepts comma-separated, newline-separated, or JSON-array
            self-name input.
          </div>

          <button type="submit" disabled={loading} className="submit-button">
            {loading ? "Analyzing..." : "Run Analysis"}
          </button>
        </form>

        {error ? <p className="status error">{error}</p> : null}
        {loading ? <p className="status loading">Pipeline is running...</p> : null}
      </section>

      {result ? (
        <>
          <section className="panel summary-panel">
            <div>
              <p className="eyebrow">Latest Result</p>
              <h2>{result.report?.title || "Analysis Report"}</h2>
              <p>{result.report?.summary}</p>
            </div>

            <div className="stat-grid">
              {stats.map((item) => (
                <article key={item.label} className="stat-card">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>

            <div className="meta-grid">
              <div>
                <strong>Conversation</strong>
                <p>{conversation?.title || result.input?.filename}</p>
              </div>
              <div>
                <strong>Input file</strong>
                <p>{result.input?.filename}</p>
              </div>
              <div>
                <strong>Self names</strong>
                <p>
                  {result.input?.self_names?.length
                    ? result.input.self_names.join(", ")
                    : "Not provided"}
                </p>
              </div>
            </div>

            {result.report?.disclaimer ? (
              <p className="disclaimer">{result.report.disclaimer}</p>
            ) : null}
          </section>

          <section className="results-grid">
            {sections.map((section) => (
              <article key={section.section} className="panel result-section">
                <div className="section-header">
                  <h3>{section.headline}</h3>
                  <span>{section.cards?.length || 0} card(s)</span>
                </div>
                {section.summary ? <p className="section-summary">{section.summary}</p> : null}

                {(section.cards || []).map((card) => (
                  <div key={card.card_id} className="card-block">
                    <div className="card-header">
                      <h4>{card.title}</h4>
                      <span>{card.type}</span>
                    </div>
                    <p>{card.summary}</p>

                    {card.bullets?.length ? (
                      <ul>
                        {card.bullets.map((bullet) => (
                          <li key={bullet}>{bullet}</li>
                        ))}
                      </ul>
                    ) : null}

                    {card.candidates?.length ? (
                      <div className="pill-row">
                        {card.candidates.map((candidate) => (
                          <span key={`${card.card_id}-${candidate.mbti_type}`} className="pill">
                            {candidate.mbti_type} · {Math.round(candidate.score * 100)}%
                          </span>
                        ))}
                      </div>
                    ) : null}

                    <div className="card-footer">
                      <span>
                        Confidence: {card.confidence ? Math.round(card.confidence * 100) : "—"}
                      </span>
                      <span>Evidence: {card.evidence?.length || 0}</span>
                    </div>
                  </div>
                ))}
              </article>
            ))}
          </section>

          <section className="panel">
            <h3>Import Warnings</h3>
            {conversation?.parser_warnings?.length ? (
              <ul>
                {conversation.parser_warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p>No parser warnings for this upload.</p>
            )}
          </section>

          <section className="panel">
            <details>
              <summary>Raw JSON fallback</summary>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </details>
          </section>
        </>
      ) : null}
    </main>
  );
}
