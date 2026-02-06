"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, Loader2, CheckCircle, XCircle, AlertTriangle, Swords, Clock, BarChart3, FlaskConical } from "lucide-react";
import { verifyQuery, battleQuery, dualQuery, VerifyResponse, BattleResponse, DualResponse, Step } from "@/lib/api";

const DOMAIN_NAMES: Record<string, string> = {
  "E_0": "D1 Identification",
  "E_1": "D2 Contextualization",
  "E_2": "D3 Evaluation",
  "E_3": "D4 Conclusion",
  "E_4": "D5 Execution",
  "E_5": "D6 Reflection",
};

const DOMAIN_COLORS: Record<string, string> = {
  "E_0": "bg-blue-500",
  "E_1": "bg-purple-500",
  "E_2": "bg-green-500",
  "E_3": "bg-yellow-500",
  "E_4": "bg-orange-500",
  "E_5": "bg-pink-500",
};

const STATUS_STYLES: Record<string, string> = {
  "PRIMARY_MAX": "ring-2 ring-green-500 bg-green-50",
  "SECONDARY_MAX": "ring-2 ring-blue-400 bg-blue-50",
  "CANDIDATE": "",
  "INVALID": "ring-2 ring-red-500 bg-red-50 opacity-75",
};

const COMPARISON_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  "MATCH": { bg: "bg-green-100", text: "text-green-800", label: "✓ MATCH — Responses aligned" },
  "CORRECTED": { bg: "bg-yellow-100", text: "text-yellow-800", label: "⚠ CORRECTED — Hallucination caught" },
  "BLOCKED": { bg: "bg-red-100", text: "text-red-800", label: "✗ BLOCKED — Invalid reasoning" },
};

function ExpandableText({ text, maxLength = 300 }: { text: string; maxLength?: number }) {
  const [expanded, setExpanded] = useState(false);

  if (text.length <= maxLength) {
    return <p className="text-sm text-gray-600">{text}</p>;
  }

  return (
    <div>
      <p className="text-sm text-gray-600">
        {expanded ? text : text.slice(0, maxLength) + "..."}
      </p>
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-blue-600 hover:underline mt-1"
      >
        {expanded ? "Show less" : "Show more"}
      </button>
    </div>
  );
}

function StepCard({ step }: { step: Step }) {
  const color = DOMAIN_COLORS[step.domain] || "bg-gray-500";
  const name = DOMAIN_NAMES[step.domain] || step.domain;
  const statusStyle = STATUS_STYLES[step.status] || "";

  return (
    <div className={`rounded-lg border p-4 ${statusStyle}`}>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className={`${color} text-white text-xs px-2 py-1 rounded font-medium`}>
          {name}
        </span>
        <span className="text-xs text-gray-500">L{step.level}</span>
        <span className="text-xs text-gray-500">W:{step.weight.toFixed(1)}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded ${step.gate === 1 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
          G:{step.gate}
        </span>
        {step.status === "PRIMARY_MAX" && (
          <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded font-medium">
            ✓ PRIMARY
          </span>
        )}
        {step.status === "INVALID" && (
          <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded font-medium">
            ✗ INVALID
          </span>
        )}
      </div>
      <p className="text-sm text-gray-700 dark:text-gray-300">{step.content}</p>
    </div>
  );
}

function BattleView({ result }: { result: BattleResponse }) {
  const style = COMPARISON_STYLES[result.comparison];

  return (
    <div className="space-y-4">
      {/* Comparison Banner */}
      <div className={`${style.bg} ${style.text} p-4 rounded-lg text-center font-medium text-lg`}>
        {style.label}
      </div>

      {/* Split View */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Raw LLM */}
        <div className="border rounded-lg p-4 bg-gray-50">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-700">🤖 Raw LLM</h3>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" /> {result.raw_time.toFixed(2)}s
            </span>
          </div>
          <ExpandableText text={result.raw_answer} maxLength={300} />
        </div>

        {/* Guarded */}
        <div className={`border rounded-lg p-4 ${result.guarded_valid ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-700">🛡️ Regulus Guarded</h3>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" /> {result.guarded_time.toFixed(2)}s
            </span>
          </div>
          {result.guarded_answer ? (
            <ExpandableText text={result.guarded_answer} maxLength={300} />
          ) : (
            <p className="text-sm text-red-600 italic">Response blocked — failed verification</p>
          )}
          {result.guarded_corrections > 0 && (
            <p className="text-xs text-yellow-700 mt-2">
              ⚠ {result.guarded_corrections} correction(s) applied
            </p>
          )}
          {result.guarded_violations.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {result.guarded_violations.map((v, i) => (
                <span key={i} className="bg-red-200 text-red-800 text-xs px-2 py-0.5 rounded">
                  {v}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DualView({ result }: { result: DualResponse }) {
  return (
    <div className="space-y-4">
      {/* Agreement Banner */}
      <div className={`p-4 rounded-lg text-center font-medium text-lg ${
        result.agreement
          ? "bg-green-100 text-green-800"
          : "bg-yellow-100 text-yellow-800"
      }`}>
        {result.agreement ? "✓ Models Agree" : "⚠ Models Disagree"}
      </div>

      {/* Split View */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Claude */}
        <div className={`border rounded-lg p-4 ${result.claude_valid ? "bg-purple-50 border-purple-200" : "bg-red-50 border-red-200"}`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-purple-700">🟣 Claude</h3>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded ${result.claude_valid ? "bg-green-200 text-green-800" : "bg-red-200 text-red-800"}`}>
                {result.claude_valid ? "Valid" : "Invalid"}
              </span>
              <span className="text-xs text-gray-500">{result.claude_time.toFixed(2)}s</span>
            </div>
          </div>
          {result.claude_answer ? (
            <ExpandableText text={result.claude_answer} maxLength={300} />
          ) : (
            <p className="text-sm text-red-600 italic">No valid response</p>
          )}
        </div>

        {/* OpenAI */}
        <div className={`border rounded-lg p-4 ${result.openai_valid ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-emerald-700">🟢 GPT-4</h3>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded ${result.openai_valid ? "bg-green-200 text-green-800" : "bg-red-200 text-red-800"}`}>
                {result.openai_valid ? "Valid" : "Invalid"}
              </span>
              <span className="text-xs text-gray-500">{result.openai_time.toFixed(2)}s</span>
            </div>
          </div>
          {result.openai_answer ? (
            <ExpandableText text={result.openai_answer} maxLength={300} />
          ) : (
            <p className="text-sm text-red-600 italic">No valid response</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"verify" | "battle" | "dual">("verify");
  const [verifyResult, setVerifyResult] = useState<VerifyResponse | null>(null);
  const [battleResult, setBattleResult] = useState<BattleResponse | null>(null);
  const [dualResult, setDualResult] = useState<DualResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (selectedMode: "verify" | "battle" | "dual") => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setMode(selectedMode);
    setVerifyResult(null);
    setBattleResult(null);
    setDualResult(null);

    try {
      if (selectedMode === "verify") {
        const res = await verifyQuery(query);
        setVerifyResult(res);
      } else if (selectedMode === "battle") {
        const res = await battleQuery(query);
        setBattleResult(res);
      } else {
        const res = await dualQuery(query);
        setDualResult(res);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Shield className="w-10 h-10 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold">Regulus AI</h1>
            <p className="text-gray-500">Structural Guardrail for LLM Reasoning</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/lab"
              className="px-4 py-2 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              <FlaskConical className="w-4 h-4" />
              Lab
            </Link>
            <Link
              href="/benchmark"
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              <BarChart3 className="w-4 h-4" />
              Benchmark
            </Link>
          </div>
        </div>

        {/* Input */}
        <div className="flex gap-2 mb-6">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit(mode)}
            placeholder="Enter a claim to verify..."
            className="flex-1 px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-700 dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
          />
          <button
            onClick={() => handleSubmit("verify")}
            disabled={loading || !query.trim()}
            className="px-5 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading && mode === "verify" ? <Loader2 className="w-5 h-5 animate-spin" /> : <Shield className="w-5 h-5" />}
            Verify
          </button>
          <button
            onClick={() => handleSubmit("battle")}
            disabled={loading || !query.trim()}
            className="px-5 py-3 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading && mode === "battle" ? <Loader2 className="w-5 h-5 animate-spin" /> : <Swords className="w-5 h-5" />}
            Battle
          </button>
          <button
            onClick={() => handleSubmit("dual")}
            disabled={loading || !query.trim()}
            className="px-5 py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading && mode === "dual" ? <Loader2 className="w-5 h-5 animate-spin" /> : <span>🔀</span>}
            Dual
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Battle Result */}
        {battleResult && <BattleView result={battleResult} />}
        {dualResult && <DualView result={dualResult} />}

        {/* Verify Result */}
        {verifyResult && (
          <div className="space-y-6">
            {/* Summary */}
            <div className={`p-6 rounded-lg ${verifyResult.valid ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"} border`}>
              <div className="flex items-center gap-3">
                {verifyResult.valid ? (
                  <CheckCircle className="w-8 h-8 text-green-600" />
                ) : (
                  <XCircle className="w-8 h-8 text-red-600" />
                )}
                <div>
                  <h2 className="text-lg font-semibold">
                    {verifyResult.valid ? "✅ Verified" : "❌ Invalid"}
                  </h2>
                  <p className="text-sm text-gray-600">
                    {verifyResult.steps.length} steps · {verifyResult.corrections} corrections · {verifyResult.time_seconds.toFixed(2)}s
                  </p>
                </div>
              </div>
            </div>

            {/* Violations */}
            {verifyResult.violations.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-5 h-5 text-yellow-600" />
                  <span className="font-medium">Violations Detected</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {verifyResult.violations.map((v, i) => (
                    <span key={i} className="bg-yellow-200 text-yellow-800 text-xs px-2 py-1 rounded">
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Steps */}
            <div>
              <h3 className="font-medium mb-3">Reasoning Steps</h3>
              <div className="space-y-3">
                {verifyResult.steps.map((step, i) => (
                  <StepCard key={i} step={step} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
