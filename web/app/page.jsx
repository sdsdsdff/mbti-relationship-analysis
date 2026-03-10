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
    <div className="bg-gray-900 text-white min-h-screen font-sans">
      <main className="max-w-4xl mx-auto p-4 sm:p-6 lg:p-8">
        <header className="text-center my-8">
          <p className="text-blue-400 font-semibold">MBTI Relationship Analysis</p>
          <h1 className="text-4xl sm:text-5xl font-bold mt-2">Upload & Analyze</h1>
          <p className="mt-4 text-lg text-gray-400 max-w-2xl mx-auto">
            Upload a Markdown or TXT transcript, optionally tag your own speaker name,
            and review the existing Python pipeline output in a lightweight web UI.
          </p>
        </header>

        <section className="bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-2xl font-bold mb-4">Analyze Transcript</h2>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="file-upload" className="block text-sm font-medium text-gray-300">
                Transcript file
              </label>
              <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-600 border-dashed rounded-md">
                <div className="space-y-1 text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-500" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
                    <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <div className="flex text-sm text-gray-400">
                    <label htmlFor="file-upload" className="relative cursor-pointer bg-gray-700 rounded-md font-medium text-blue-400 hover:text-blue-300 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-offset-gray-800 focus-within:ring-blue-500">
                      <span>Upload a file</span>
                      <input id="file-upload" name="file-upload" type="file" className="sr-only" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                    </label>
                    <p className="pl-1">{file ? file.name : 'or drag and drop'}</p>
                  </div>
                  <p className="text-xs text-gray-500">
                    Markdown, TXT up to 10MB
                  </p>
                </div>
              </div>
            </div>

            <div>
              <label htmlFor="self-names" className="block text-sm font-medium text-gray-300">
                Self name(s) (optional)
              </label>
              <input
                type="text"
                id="self-names"
                placeholder="Me, 我, Alice"
                value={selfNames}
                onChange={(event) => setSelfNames(event.target.value)}
                className="mt-1 block w-full bg-gray-700 border border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="mt-2 text-sm text-gray-400">
                Comma-separated names to identify your messages.
              </p>
            </div>

            <button type="submit" disabled={loading} className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed">
              {loading ? "Analyzing..." : "Run Analysis"}
            </button>
          </form>

          {error && <p className="mt-4 text-center text-red-400">{error}</p>}
          {loading && <p className="mt-4 text-center text-blue-400">Pipeline is running, please wait...</p>}
        </section>

        {result && (
          <div className="space-y-8 mt-8">
            <section className="bg-gray-800 rounded-lg p-6 shadow-lg">
              <p className="text-blue-400 font-semibold">Latest Result</p>
              <h2 className="text-3xl font-bold mt-2">{result.report?.title || "Analysis Report"}</h2>
              <p className="mt-4 text-gray-300">{result.report?.summary}</p>
              
              <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                {stats.map((item) => (
                  <div key={item.label} className="bg-gray-700 p-4 rounded-lg">
                    <span className="text-sm text-gray-400">{item.label}</span>
                    <strong className="block text-2xl font-bold">{item.value}</strong>
                  </div>
                ))}
              </div>

              <div className="mt-6 border-t border-gray-700 pt-6 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <strong className="block text-gray-400">Conversation</strong>
                  <p>{conversation?.title || result.input?.filename}</p>
                </div>
                <div>
                  <strong className="block text-gray-400">Input file</strong>
                  <p>{result.input?.filename}</p>
                </div>
                <div>
                  <strong className="block text-gray-400">Self names</strong>
                  <p>
                    {result.input?.self_names?.length
                      ? result.input.self_names.join(", ")
                      : "Not provided"}
                  </p>
                </div>
              </div>

              {result.report?.disclaimer && (
                <p className="mt-6 text-xs text-gray-500 italic">{result.report.disclaimer}</p>
              )}
            </section>

            {sections.map((section) => (
              <section key={section.section} className="bg-gray-800 rounded-lg p-6 shadow-lg">
                <header className="flex justify-between items-baseline mb-4 border-b border-gray-700 pb-4">
                  <h3 className="text-2xl font-bold text-blue-300">{section.headline}</h3>
                  <span className="text-sm text-gray-400">{section.cards?.length || 0} card(s)</span>
                </header>
                {section.summary && <p className="mb-6 text-gray-300">{section.summary}</p>}

                <div className="space-y-6">
                  {(section.cards || []).map((card) => (
                    <article key={card.card_id} className="bg-gray-700 p-4 rounded-lg border border-gray-600">
                      <header className="flex justify-between items-start mb-2">
                        <h4 className="text-lg font-semibold">{card.title}</h4>
                        <span className="text-xs font-mono bg-gray-600 text-blue-300 px-2 py-1 rounded">{card.type}</span>
                      </header>
                      <p className="text-gray-300 mb-4">{card.summary}</p>

                      {card.bullets?.length > 0 && (
                        <ul className="list-disc list-inside space-y-1 mb-4 text-gray-400">
                          {card.bullets.map((bullet, i) => (
                            <li key={i}>{bullet}</li>
                          ))}
                        </ul>
                      )}

                      {card.candidates?.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-4">
                          {card.candidates.map((candidate) => (
                            <span key={`${card.card_id}-${candidate.mbti_type}`} className="inline-block bg-blue-800 text-blue-200 text-xs font-semibold px-2.5 py-1 rounded-full">
                              {candidate.mbti_type} · {Math.round(candidate.score * 100)}%
                            </span>
                          ))}
                        </div>
                      )}

                      <footer className="text-xs text-gray-500 flex justify-between items-center border-t border-gray-600 pt-2 mt-4">
                        <span>
                          Confidence: {card.confidence ? `${Math.round(card.confidence * 100)}%` : "—"}
                        </span>
                        <span>Evidence: {card.evidence?.length || 0}</span>
                      </footer>
                    </article>
                  ))}
                </div>
              </section>
            ))}

            <section className="bg-gray-800 rounded-lg p-6 shadow-lg">
              <h3 className="text-xl font-bold mb-4">Import Warnings</h3>
              {conversation?.parser_warnings?.length ? (
                <ul className="list-disc list-inside space-y-1 text-yellow-400">
                  {conversation.parser_warnings.map((warning, i) => (
                    <li key={i}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-gray-400">No parser warnings for this upload.</p>
              )}
            </section>

            <section className="bg-gray-800 rounded-lg p-6 shadow-lg">
              <details>
                <summary className="font-medium cursor-pointer hover:text-blue-400">Raw JSON fallback</summary>
                <div className="mt-4 bg-gray-900 p-4 rounded-md">
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap break-all">{JSON.stringify(result, null, 2)}</pre>
                </div>
              </details>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
