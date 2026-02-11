"use client";

import { useState } from "react";
import {
  ArrowLeft, FlaskConical, Loader2, Download, BarChart3,
  AlertTriangle, Lightbulb, TrendingDown, TrendingUp, Minus,
  ChevronDown, ChevronRight,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getAnalysisReport, getV2RunStats, exportRunResults,
  type AnalysisReport, type V2RunStats,
  formatCost, formatTime,
} from "@/lib/lab-api";

// === Stat Card ===

function StatCard({ label, value, sub, color }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-4 py-3">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-xl font-bold ${color || "text-white"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

// === Accuracy Bar ===

function AccuracyBar({ accuracy, label }: { accuracy: number; label: string }) {
  const pct = Math.round(accuracy * 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-400 w-40 truncate" title={label}>{label}</span>
      <div className="flex-1 bg-[#1a1a2e] rounded-full h-2.5">
        <div className={`${color} h-2.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-sm font-medium w-12 text-right ${
        pct >= 70 ? "text-green-400" : pct >= 40 ? "text-yellow-400" : "text-red-400"
      }`}>{pct}%</span>
    </div>
  );
}

// === SVG Domain Chart ===

function DomainChart({ domains }: { domains: AnalysisReport["domain_analysis"] }) {
  if (!domains.length) return null;

  const sorted = [...domains].sort((a, b) => b.accuracy - a.accuracy);
  const barW = Math.max(20, Math.min(48, Math.floor(600 / sorted.length) - 4));
  const chartW = sorted.length * (barW + 4) + 40;
  const chartH = 200;
  const maxH = chartH - 40;

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 overflow-x-auto">
      <svg width={Math.max(chartW, 200)} height={chartH} className="mx-auto">
        {/* Y-axis labels */}
        {[0, 25, 50, 75, 100].map((v) => {
          const y = chartH - 24 - (v / 100) * maxH;
          return (
            <g key={v}>
              <text x={28} y={y + 4} textAnchor="end" className="fill-gray-600 text-[10px]">{v}%</text>
              <line x1={32} y1={y} x2={chartW} y2={y} stroke="#1e1e2e" strokeWidth={1} />
            </g>
          );
        })}
        {/* Bars */}
        {sorted.map((d, i) => {
          const pct = d.accuracy * 100;
          const h = (pct / 100) * maxH;
          const x = 40 + i * (barW + 4);
          const y = chartH - 24 - h;
          const fill = pct >= 70 ? "#22c55e" : pct >= 40 ? "#eab308" : "#ef4444";
          const label = d.domain.replace(/_/g, " ");
          return (
            <g key={d.domain}>
              <rect x={x} y={y} width={barW} height={h} rx={3} fill={fill} opacity={0.85} />
              <text
                x={x + barW / 2} y={y - 4}
                textAnchor="middle" className="fill-gray-400 text-[10px] font-medium"
              >
                {pct.toFixed(0)}%
              </text>
              <text
                x={x + barW / 2} y={chartH - 6}
                textAnchor="middle" className="fill-gray-500 text-[9px]"
                transform={`rotate(-35, ${x + barW / 2}, ${chartH - 6})`}
              >
                {label.length > 10 ? label.slice(0, 9) + "…" : label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// === SVG Team Chart ===

function TeamChart({ teams }: { teams: AnalysisReport["team_analysis"] }) {
  if (teams.length < 2) return null;

  const sorted = [...teams].sort((a, b) => a.team_index - b.team_index);
  const barW = Math.max(32, Math.min(60, Math.floor(500 / sorted.length) - 8));
  const chartW = sorted.length * (barW + 8) + 60;
  const chartH = 160;
  const maxH = chartH - 36;

  // Trend line points
  const points = sorted.map((t, i) => {
    const x = 52 + i * (barW + 8) + barW / 2;
    const y = chartH - 24 - (t.accuracy * 100 / 100) * maxH;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 overflow-x-auto">
      <svg width={Math.max(chartW, 200)} height={chartH} className="mx-auto">
        {/* Grid */}
        {[0, 50, 100].map((v) => {
          const y = chartH - 24 - (v / 100) * maxH;
          return (
            <g key={v}>
              <text x={38} y={y + 4} textAnchor="end" className="fill-gray-600 text-[10px]">{v}%</text>
              <line x1={42} y1={y} x2={chartW} y2={y} stroke="#1e1e2e" strokeWidth={1} />
            </g>
          );
        })}
        {/* Bars */}
        {sorted.map((t, i) => {
          const pct = t.accuracy * 100;
          const h = (pct / 100) * maxH;
          const x = 52 + i * (barW + 8);
          const y = chartH - 24 - h;
          const fill = pct >= 70 ? "#22c55e" : pct >= 40 ? "#eab308" : "#ef4444";
          return (
            <g key={t.team_index}>
              <rect x={x} y={y} width={barW} height={h} rx={3} fill={fill} opacity={0.7} />
              <text x={x + barW / 2} y={y - 4} textAnchor="middle" className="fill-gray-400 text-[10px] font-medium">
                {pct.toFixed(0)}%
              </text>
              <text x={x + barW / 2} y={chartH - 6} textAnchor="middle" className="fill-gray-500 text-[10px]">
                T{t.team_index + 1}
              </text>
            </g>
          );
        })}
        {/* Trend line */}
        <polyline points={points} fill="none" stroke="#a78bfa" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" opacity={0.8} />
        {sorted.map((t, i) => {
          const x = 52 + i * (barW + 8) + barW / 2;
          const y = chartH - 24 - (t.accuracy * 100 / 100) * maxH;
          return <circle key={i} cx={x} cy={y} r={3} fill="#a78bfa" />;
        })}
      </svg>
    </div>
  );
}

// === Domain Analysis Section ===

function DomainSection({ domains }: { domains: AnalysisReport["domain_analysis"] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!domains.length) return null;

  return (
    <section>
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Domain Analysis
      </h2>
      {/* Chart */}
      <DomainChart domains={domains} />
      {/* Detail rows */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 space-y-3 mt-3">
        {domains.map((d) => (
          <div key={d.domain}>
            <div
              className="cursor-pointer hover:bg-[#1a1a2e] rounded p-1 -m-1"
              onClick={() => setExpanded(expanded === d.domain ? null : d.domain)}
            >
              <AccuracyBar accuracy={d.accuracy} label={d.domain} />
              <div className="flex items-center gap-4 ml-[172px] mt-1 text-xs text-gray-500">
                <span>{d.total} questions</span>
                <span className="text-green-400">{d.correct} correct</span>
                <span className="text-red-400">{d.wrong} wrong</span>
                {d.common_errors.length > 0 && (
                  <span className="flex items-center gap-1">
                    {expanded === d.domain ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    {d.common_errors.length} errors
                  </span>
                )}
              </div>
            </div>
            {expanded === d.domain && d.common_errors.length > 0 && (
              <div className="ml-[172px] mt-2 space-y-1">
                {d.common_errors.map((err, i) => (
                  <div key={i} className="text-xs text-gray-400 bg-[#1a1a2e] rounded px-3 py-2 border-l-2 border-red-500/30">
                    {err}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// === Team Analysis Section ===

function TeamSection({ teams }: { teams: AnalysisReport["team_analysis"] }) {
  if (!teams.length) return null;

  const TrendIcon = ({ trend }: { trend: string }) => {
    if (trend === "improving") return <TrendingUp className="w-3.5 h-3.5 text-green-400" />;
    if (trend === "declining") return <TrendingDown className="w-3.5 h-3.5 text-red-400" />;
    return <Minus className="w-3.5 h-3.5 text-gray-500" />;
  };

  return (
    <section>
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
        Team Rotations
      </h2>
      {/* Chart */}
      <TeamChart teams={teams} />
      {/* Table */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden mt-3">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1e1e2e] text-gray-500 text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-2.5 font-medium">Team</th>
              <th className="text-right px-4 py-2.5 font-medium">Questions</th>
              <th className="text-right px-4 py-2.5 font-medium">Correct</th>
              <th className="text-right px-4 py-2.5 font-medium">Accuracy</th>
              <th className="text-center px-4 py-2.5 font-medium">Trend</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((t) => (
              <tr key={t.team_index} className="border-b border-[#1e1e2e] last:border-0">
                <td className="px-4 py-2.5 text-sm text-gray-300">Team {t.team_index + 1}</td>
                <td className="px-4 py-2.5 text-sm text-gray-400 text-right">{t.total}</td>
                <td className="px-4 py-2.5 text-sm text-green-400 text-right">{t.correct}</td>
                <td className={`px-4 py-2.5 text-sm text-right font-medium ${
                  t.accuracy >= 0.7 ? "text-green-400" : t.accuracy >= 0.4 ? "text-yellow-400" : "text-red-400"
                }`}>{(t.accuracy * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 text-center"><TrendIcon trend={t.performance_trend} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// === Failure Patterns Section ===

function FailurePatternsSection({ patterns }: { patterns: AnalysisReport["failure_patterns"] }) {
  if (!patterns.length) return null;

  return (
    <section>
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-yellow-400" />
        Failure Patterns
      </h2>
      <div className="space-y-3">
        {patterns.map((fp, i) => (
          <div key={i} className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                  {fp.pattern_type}
                </span>
                <span className="text-xs text-gray-500 ml-2">{fp.frequency} occurrence{fp.frequency !== 1 ? "s" : ""}</span>
              </div>
            </div>
            <p className="text-sm text-gray-300 mb-2">{fp.description}</p>
            {fp.suggested_fix && (
              <div className="text-xs text-gray-400 bg-[#1a1a2e] rounded px-3 py-2 border-l-2 border-blue-500/30 flex items-start gap-2">
                <Lightbulb className="w-3.5 h-3.5 text-blue-400 mt-0.5 flex-shrink-0" />
                {fp.suggested_fix}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// === Recommendations Section ===

function RecommendationsSection({ recs }: { recs: string[] }) {
  if (!recs.length) return null;

  return (
    <section>
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Lightbulb className="w-4 h-4 text-blue-400" />
        Recommendations
      </h2>
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 space-y-2">
        {recs.map((rec, i) => (
          <div key={i} className="flex items-start gap-3 text-sm">
            <span className="text-blue-400 font-mono text-xs mt-0.5">{i + 1}.</span>
            <span className="text-gray-300">{rec}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// === Main Page ===

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ["lab-report", id],
    queryFn: () => getAnalysisReport(id),
    enabled: !!id,
  });

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["lab-v2-stats", id],
    queryFn: () => getV2RunStats(id),
    enabled: !!id,
  });

  const isLoading = reportLoading || statsLoading;

  const handleExport = async (format: "json" | "csv") => {
    try {
      const blob = await exportRunResults(id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `run_${id}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
    }
  };

  const summary = report?.summary;
  const accColor = summary
    ? summary.accuracy >= 0.7 ? "text-green-400" : summary.accuracy >= 0.4 ? "text-yellow-400" : "text-red-400"
    : "text-white";

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FlaskConical className="w-8 h-8 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">Results &amp; Analysis</h1>
            <p className="text-gray-500 text-sm">Run {id}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExport("json")}
              className="px-3 py-1.5 text-sm border border-[#2a2a3e] rounded-lg hover:bg-[#1a1a2e] text-gray-300 flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              JSON
            </button>
            <button
              onClick={() => handleExport("csv")}
              className="px-3 py-1.5 text-sm border border-[#2a2a3e] rounded-lg hover:bg-[#1a1a2e] text-gray-300 flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        )}

        {/* Content */}
        {!isLoading && summary && (
          <div className="space-y-8">
            {/* Summary Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              <StatCard
                label="Accuracy"
                value={`${(summary.accuracy * 100).toFixed(1)}%`}
                color={accColor}
              />
              <StatCard label="Questions" value={String(summary.total_questions)} />
              <StatCard
                label="Correct"
                value={String(summary.correct)}
                color="text-green-400"
              />
              <StatCard
                label="Wrong"
                value={String(summary.wrong)}
                color={summary.wrong > 0 ? "text-red-400" : "text-gray-400"}
              />
              <StatCard
                label="Cost"
                value={formatCost(summary.total_cost)}
                sub={`${formatCost(stats?.avg_cost_per_question ?? 0)}/q`}
              />
              <StatCard
                label="Time"
                value={formatTime(summary.total_time_seconds)}
                sub={`${summary.avg_time_per_question.toFixed(1)}s/q`}
              />
            </div>

            {/* Token Stats (from V2RunStats) */}
            {stats && (
              <div className="grid grid-cols-3 gap-3">
                <StatCard
                  label="Tokens In"
                  value={stats.total_tokens_in.toLocaleString()}
                  sub={`${Math.round(stats.avg_tokens_per_question).toLocaleString()} avg/q`}
                />
                <StatCard
                  label="Tokens Out"
                  value={stats.total_tokens_out.toLocaleString()}
                />
                <StatCard
                  label="Errors"
                  value={String(stats.error_count)}
                  color={stats.error_count > 0 ? "text-yellow-400" : "text-gray-400"}
                  sub={stats.partial_count > 0 ? `${stats.partial_count} partial` : undefined}
                />
              </div>
            )}

            {/* Domain Analysis */}
            <DomainSection domains={report!.domain_analysis} />

            {/* Team Analysis */}
            <TeamSection teams={report!.team_analysis} />

            {/* Failure Patterns */}
            <FailurePatternsSection patterns={report!.failure_patterns} />

            {/* Recommendations */}
            <RecommendationsSection recs={report!.recommendations} />
          </div>
        )}

        {/* No data */}
        {!isLoading && !summary && (
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-16 text-center">
            <BarChart3 className="w-16 h-16 mx-auto text-gray-600 mb-4" />
            <h2 className="text-xl font-medium text-gray-300 mb-2">No results yet</h2>
            <p className="text-gray-500">This run has no completed questions to analyze.</p>
          </div>
        )}
      </div>
    </main>
  );
}
