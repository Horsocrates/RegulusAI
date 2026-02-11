"use client";

import { Fragment, useState } from "react";
import {
  BarChart3, ArrowLeft, Loader2, CheckCircle, XCircle,
  AlertTriangle, ChevronDown, ChevronRight, Sparkles, RefreshCw,
  Users, FolderOpen,
} from "lucide-react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAllResults, getResultsStats, getResultsTree, analyzeResult,
  getResultAnalysis, getAnalysisStats, formatCost, formatTime,
  type QuestionResultResponse, type ParticipantNode, type DomainNode,
} from "@/lib/lab-api";

// ── Constants ────────────────────────────────────────────────────────

const PARTICIPANT_COLORS: Record<string, string> = {
  p1: "border-blue-500/40 bg-blue-500/5",
  p2: "border-emerald-500/40 bg-emerald-500/5",
  p3: "border-orange-500/40 bg-orange-500/5",
  p3v2: "border-purple-500/40 bg-purple-500/5",
};

const PARTICIPANT_ACCENT: Record<string, string> = {
  p1: "text-blue-400",
  p2: "text-emerald-400",
  p3: "text-orange-400",
  p3v2: "text-purple-400",
};

const CATEGORY_COLORS: Record<string, string> = {
  reasoning_error: "bg-red-500/20 text-red-400",
  knowledge_gap: "bg-orange-500/20 text-orange-400",
  misinterpretation: "bg-yellow-500/20 text-yellow-400",
  calculation_error: "bg-pink-500/20 text-pink-400",
  incomplete_analysis: "bg-blue-500/20 text-blue-400",
  hallucination: "bg-purple-500/20 text-purple-400",
  format_error: "bg-cyan-500/20 text-cyan-400",
  other: "bg-gray-500/20 text-gray-400",
};

// ── Small components ─────────────────────────────────────────────────

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return <span className="text-gray-600 text-xs">Pending</span>;
  const cfg: Record<string, { icon: React.ElementType; color: string }> = {
    correct: { icon: CheckCircle, color: "text-green-400" },
    wrong: { icon: XCircle, color: "text-red-400" },
    partial: { icon: AlertTriangle, color: "text-yellow-400" },
    error: { icon: XCircle, color: "text-red-600" },
  };
  const c = cfg[verdict] || cfg.error;
  const Icon = c.icon;
  return (
    <span className={`flex items-center gap-1 text-xs font-medium ${c.color}`}>
      <Icon className="w-3.5 h-3.5" />
      {verdict}
    </span>
  );
}

function AccuracyBar({ correct, total, className = "" }: { correct: number; total: number; className?: string }) {
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
        <div
          className="h-full bg-green-500/60 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 w-24 text-right shrink-0">
        {correct}/{total} ({pct}%)
      </span>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-4 py-3">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</p>
    </div>
  );
}

// ── Analysis panel (in expanded question) ────────────────────────────

function AnalysisPanel({ result }: { result: QuestionResultResponse }) {
  const queryClient = useQueryClient();

  const { data: analysis, isLoading: loadingAnalysis } = useQuery({
    queryKey: ["result-analysis", result.id],
    queryFn: () => getResultAnalysis(result.id),
    enabled: result.has_analysis === true,
    retry: false,
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeResult(result.id),
    onSuccess: () => {
      const poll = setInterval(async () => {
        try {
          const a = await getResultAnalysis(result.id);
          if (a.status === "completed" || a.status === "error") {
            clearInterval(poll);
            queryClient.invalidateQueries({ queryKey: ["result-analysis", result.id] });
            queryClient.invalidateQueries({ queryKey: ["lab-all-results"] });
            queryClient.invalidateQueries({ queryKey: ["analysis-stats"] });
          }
        } catch { /* not ready */ }
      }, 2000);
    },
  });

  if (!result.has_analysis && !analyzeMutation.isPending && !analyzeMutation.isSuccess) {
    return (
      <div className="mt-3 pt-3 border-t border-[#1e1e2e]">
        <button
          onClick={(e) => { e.stopPropagation(); analyzeMutation.mutate(); }}
          className="flex items-center gap-2 px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 rounded-lg text-xs transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" />
          Analyze with AI
        </button>
      </div>
    );
  }

  if (analyzeMutation.isPending || (analyzeMutation.isSuccess && (!analysis || analysis.status === "running" || analysis.status === "pending"))) {
    return (
      <div className="mt-3 pt-3 border-t border-[#1e1e2e]">
        <div className="flex items-center gap-2 text-xs text-purple-400">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Analyzing...
        </div>
      </div>
    );
  }

  if (loadingAnalysis) {
    return (
      <div className="mt-3 pt-3 border-t border-[#1e1e2e]">
        <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
      </div>
    );
  }

  if (!analysis) return null;

  if (analysis.status === "error") {
    return (
      <div className="mt-3 pt-3 border-t border-[#1e1e2e]">
        <div className="flex items-center gap-2">
          <p className="text-xs text-red-400">Analysis failed: {analysis.error_message}</p>
          <button
            onClick={(e) => { e.stopPropagation(); analyzeMutation.mutate(); }}
            className="flex items-center gap-1 px-2 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded text-xs"
          >
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3 pt-3 border-t border-[#1e1e2e] space-y-2">
      <div className="flex items-center gap-2">
        <Sparkles className="w-3.5 h-3.5 text-purple-400" />
        <span className="text-xs font-medium text-purple-400">AI Analysis</span>
        {analysis.failure_category && (
          <span className={`text-xs px-2 py-0.5 rounded ${CATEGORY_COLORS[analysis.failure_category] || CATEGORY_COLORS.other}`}>
            {analysis.failure_category.replace(/_/g, " ")}
          </span>
        )}
      </div>
      {analysis.root_cause && (
        <p className="text-xs text-gray-300"><span className="text-gray-500">Root cause:</span> {analysis.root_cause}</p>
      )}
      {analysis.summary && <p className="text-xs text-gray-400">{analysis.summary}</p>}
      {analysis.recommendations && analysis.recommendations.length > 0 && (
        <ul className="text-xs text-gray-400 list-disc list-inside space-y-0.5">
          {analysis.recommendations.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}

// ── Level 3: Questions list (loaded lazily when domain is expanded) ──

function DomainQuestions({
  participantRunIds,
  domain,
}: {
  participantRunIds: string[];
  domain: string;
}) {
  const [expandedQId, setExpandedQId] = useState<string | null>(null);

  // Fetch all results for this participant+domain combination
  // We load all matching run_ids and filter by domain
  const { data, isLoading } = useQuery({
    queryKey: ["domain-questions", participantRunIds, domain],
    queryFn: async () => {
      // Fetch from each run, combine
      const all: QuestionResultResponse[] = [];
      for (const runId of participantRunIds) {
        const res = await listAllResults({ run_id: runId, domain, limit: 200 });
        all.push(...res.results);
      }
      return all;
    },
  });

  if (isLoading) {
    return (
      <div className="py-3 pl-16 flex items-center gap-2 text-gray-500 text-xs">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading questions...
      </div>
    );
  }

  const questions = data ?? [];
  if (questions.length === 0) {
    return <p className="py-2 pl-16 text-xs text-gray-600">No questions found</p>;
  }

  return (
    <div className="ml-12 mr-4 mb-2 border-l border-[#1e1e2e]">
      {questions.map((q) => (
        <Fragment key={q.id}>
          <div
            onClick={() => setExpandedQId(expandedQId === q.id ? null : q.id)}
            className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#12121a] cursor-pointer transition-colors border-b border-[#1e1e2e]/30"
          >
            <span className="text-gray-600 shrink-0">
              {expandedQId === q.id
                ? <ChevronDown className="w-3 h-3" />
                : <ChevronRight className="w-3 h-3" />}
            </span>
            <VerdictBadge verdict={q.judgment_verdict} />
            <span className="text-xs text-gray-300 flex-1 truncate" title={q.input_text}>
              {q.input_text}
            </span>
            {q.has_analysis && (
              <span title="AI analysis available"><Sparkles className="w-3 h-3 text-purple-400 shrink-0" /></span>
            )}
            {q.total_time_ms > 0 && (
              <span className="text-xs text-gray-600 shrink-0">{formatTime(q.total_time_ms / 1000)}</span>
            )}
          </div>

          {/* Expanded question detail */}
          {expandedQId === q.id && (
            <div className="bg-[#0d0d15] px-6 py-4 border-b border-[#1e1e2e]/30 space-y-3">
              <div>
                <p className="text-xs text-gray-500 mb-1">Question</p>
                <p className="text-sm text-gray-200 whitespace-pre-wrap">{q.input_text}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Model Answer</p>
                <p className="text-sm text-gray-300 whitespace-pre-wrap bg-[#12121a] rounded px-3 py-2 border border-[#1e1e2e] max-h-60 overflow-y-auto">
                  {q.final_answer || "(no answer)"}
                </p>
              </div>
              <div className="flex items-start gap-4">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Verdict</p>
                  <VerdictBadge verdict={q.judgment_verdict} />
                </div>
                {q.judgment_explanation && (
                  <div className="flex-1">
                    <p className="text-xs text-gray-500 mb-1">Explanation</p>
                    <p className="text-xs text-gray-400">{q.judgment_explanation}</p>
                  </div>
                )}
              </div>
              <AnalysisPanel result={q} />
            </div>
          )}
        </Fragment>
      ))}
    </div>
  );
}

// ── Level 2: Domain accordion row ────────────────────────────────────

function DomainRow({
  domain,
  participantRunIds,
  accent,
}: {
  domain: DomainNode;
  participantRunIds: string[];
  accent: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 px-4 py-2.5 ml-6 hover:bg-[#12121a] cursor-pointer transition-colors border-b border-[#1e1e2e]/30"
      >
        <span className="text-gray-600 shrink-0">
          {open
            ? <ChevronDown className="w-3.5 h-3.5" />
            : <ChevronRight className="w-3.5 h-3.5" />}
        </span>
        <FolderOpen className={`w-3.5 h-3.5 ${accent} shrink-0`} />
        <span className="text-sm text-gray-300 font-medium w-48 truncate">
          {domain.domain}
        </span>
        <AccuracyBar correct={domain.correct} total={domain.total} className="flex-1" />
      </div>

      {open && (
        <DomainQuestions
          participantRunIds={participantRunIds}
          domain={domain.domain}
        />
      )}
    </>
  );
}

// ── Level 1: Participant card ────────────────────────────────────────

function ParticipantCard({ node }: { node: ParticipantNode }) {
  const [open, setOpen] = useState(false);
  const borderColor = PARTICIPANT_COLORS[node.participant] || "border-gray-500/40 bg-gray-500/5";
  const accent = PARTICIPANT_ACCENT[node.participant] || "text-gray-400";

  return (
    <div className={`border rounded-lg overflow-hidden ${borderColor}`}>
      {/* Header */}
      <div
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-gray-500 shrink-0">
          {open
            ? <ChevronDown className="w-4 h-4" />
            : <ChevronRight className="w-4 h-4" />}
        </span>
        <Users className={`w-5 h-5 ${accent} shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h2 className={`text-sm font-semibold ${accent}`}>{node.name}</h2>
            <span className="text-xs text-gray-600">{node.total} questions</span>
          </div>
          <AccuracyBar correct={node.correct} total={node.total} className="mt-1.5" />
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-4">
          <div className="text-center">
            <p className="text-lg font-bold text-green-400">{node.correct}</p>
            <p className="text-[10px] text-gray-600 uppercase">correct</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-red-400">{node.wrong}</p>
            <p className="text-[10px] text-gray-600 uppercase">wrong</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-gray-300">{Math.round(node.accuracy * 100)}%</p>
            <p className="text-[10px] text-gray-600 uppercase">accuracy</p>
          </div>
        </div>
      </div>

      {/* Domains */}
      {open && (
        <div className="border-t border-[#1e1e2e]">
          {node.domains.map((d) => (
            <DomainRow
              key={d.domain}
              domain={d}
              participantRunIds={node.run_ids}
              accent={accent}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────

export default function AllResultsPage() {
  const { data: stats } = useQuery({
    queryKey: ["results-stats"],
    queryFn: () => getResultsStats(),
  });

  const { data: tree, isLoading } = useQuery({
    queryKey: ["results-tree"],
    queryFn: () => getResultsTree(),
  });

  const { data: analysisStats } = useQuery({
    queryKey: ["analysis-stats"],
    queryFn: () => getAnalysisStats(),
  });

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <BarChart3 className="w-8 h-8 text-blue-400" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">All Results</h1>
            <p className="text-sm text-gray-500">
              {stats ? `${stats.total.toLocaleString()} results across ${stats.run_ids.length} runs` : "Loading..."}
            </p>
          </div>
        </div>

        {/* Summary Cards */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
            <StatCard label="Total" value={stats.total} color="text-gray-300" />
            <StatCard label="Correct" value={stats.correct} color="text-green-400" />
            <StatCard label="Wrong" value={stats.wrong} color="text-red-400" />
            <StatCard label="Partial" value={stats.partial} color="text-yellow-400" />
            <StatCard label="Error" value={stats.error} color="text-red-600" />
            <StatCard label="Pending" value={stats.pending} color="text-gray-500" />
          </div>
        )}

        {/* Analysis stats bar */}
        {analysisStats && analysisStats.completed > 0 && (
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-4 py-3 mb-6">
            <div className="flex items-center gap-3 flex-wrap">
              <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
              <span className="text-xs text-gray-400">{analysisStats.completed} analyses:</span>
              {Object.entries(analysisStats.by_category).map(([cat, count]) => (
                <span key={cat} className={`text-xs px-2 py-0.5 rounded ${CATEGORY_COLORS[cat] || CATEGORY_COLORS.other}`}>
                  {cat.replace(/_/g, " ")} ({count})
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Tree */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
          </div>
        ) : !tree || tree.length === 0 ? (
          <div className="text-center py-20">
            <BarChart3 className="w-12 h-12 text-gray-700 mx-auto mb-4" />
            <p className="text-gray-500">No results found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tree.map((node) => (
              <ParticipantCard key={node.participant} node={node} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
