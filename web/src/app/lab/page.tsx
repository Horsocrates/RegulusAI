"use client";

import { useState } from "react";
import {
  FlaskConical, Plus, Trash2, ArrowLeft, Loader2, CheckCircle,
  Clock, PauseCircle, XCircle, ExternalLink, RotateCcw, StopCircle,
  Users, BarChart3, Database, Settings, FileText, BookOpen, Sliders,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getLabRuns, deleteLabRun, stopLabRun, getRunStats, getDashboard,
  type LabRun, type RunStatus, type DashboardStats, STATUS_CONFIG, formatCost, formatTime,
} from "@/lib/lab-api";

// === Status Badge ===

const STATUS_ICONS: Record<RunStatus, React.ElementType> = {
  created: Clock,
  running: Loader2,
  paused: PauseCircle,
  completed: CheckCircle,
  failed: XCircle,
  stopped: XCircle,
};

function StatusBadge({ status }: { status: RunStatus }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.created;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${config.dotClass}`} />
      <span className={`text-sm font-medium ${config.textClass}`}>{config.label}</span>
    </span>
  );
}

// === Active Run Card ===

function ActiveRunCard({ run, onStop }: { run: LabRun; onStop: (id: number) => void }) {
  const router = useRouter();
  const [stopping, setStopping] = useState(false);

  const handleStop = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Cancel run "${run.name}"?`)) return;
    setStopping(true);
    try {
      await stopLabRun(run.id);
      onStop(run.id);
    } catch (err) {
      console.error(err);
    } finally {
      setStopping(false);
    }
  };

  const { data: stats } = useQuery({
    queryKey: ["lab-run-stats", run.id],
    queryFn: () => getRunStats(run.id),
    refetchInterval: 5000,
    enabled: run.status === "running",
  });

  const completed = stats?.completed ?? run.completed_questions;
  const total = run.total_questions;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const passed = stats?.passed ?? run.correct_count;
  const failed = stats?.failed ?? (completed - passed);

  return (
    <div
      onClick={() => router.push(`/lab/run/${run.id}`)}
      className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 hover:border-blue-500/50 transition-colors cursor-pointer"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status as RunStatus} />
          <span className="text-white font-medium">Run #{run.id}: {run.name}</span>
        </div>
        <div className="flex items-center gap-3">
          {run.mode === "v2" && (
            <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400">v2</span>
          )}
          <span className="text-sm text-gray-400">{run.concurrency} agents</span>
          <button
            onClick={handleStop}
            disabled={stopping}
            className="px-2.5 py-1 text-xs font-medium text-red-400 border border-red-400/30 rounded hover:bg-red-400/10 transition-colors flex items-center gap-1"
          >
            {stopping
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <StopCircle className="w-3 h-3" />
            }
            Cancel
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-2">
        <div className="w-full bg-[#1a1a2e] rounded-full h-2.5">
          <div
            className="bg-blue-500 h-2.5 rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-4 text-gray-400">
          <span>{completed}/{total} questions</span>
          <span className="text-green-400">{passed} pass</span>
          <span className="text-red-400">{Math.max(0, failed)} fail</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">{pct}%</span>
          <ExternalLink className="w-4 h-4 text-gray-500" />
        </div>
      </div>
    </div>
  );
}

// === Run History Table ===

function RunHistoryTable({ runs, onDelete, onStop }: { runs: LabRun[]; onDelete: (id: number) => void; onStop: (id: number) => void }) {
  const router = useRouter();
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [stoppingId, setStoppingId] = useState<number | null>(null);

  const handleStop = async (e: React.MouseEvent, id: number, name: string) => {
    e.stopPropagation();
    if (!confirm(`Cancel run "${name}"?`)) return;
    setStoppingId(id);
    try {
      await stopLabRun(id);
      onStop(id);
    } catch (err) {
      console.error(err);
    } finally {
      setStoppingId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: number, name: string) => {
    e.stopPropagation();
    if (!confirm(`Delete run "${name}"?`)) return;
    setDeletingId(id);
    try {
      await deleteLabRun(id);
      onDelete(id);
    } catch (err) {
      console.error(err);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1e1e2e] text-gray-500 text-xs uppercase tracking-wider">
            <th className="text-left px-4 py-3 font-medium">#</th>
            <th className="text-left px-4 py-3 font-medium">Name</th>
            <th className="text-left px-4 py-3 font-medium">Dataset</th>
            <th className="text-right px-4 py-3 font-medium">Qs</th>
            <th className="text-right px-4 py-3 font-medium">Pass</th>
            <th className="text-right px-4 py-3 font-medium">Fail</th>
            <th className="text-left px-4 py-3 font-medium">Status</th>
            <th className="text-right px-4 py-3 font-medium w-10"></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const failCount = run.completed_questions - run.correct_count;
            return (
              <tr
                key={run.id}
                onClick={() => router.push(`/lab/run/${run.id}`)}
                className="border-b border-[#1e1e2e] hover:bg-[#1a1a2e] cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 text-gray-500 text-sm">{run.id}</td>
                <td className="px-4 py-3">
                  <div className="text-white text-sm font-medium">{run.name}</div>
                  {run.source_run_id && (
                    <div className="text-xs text-gray-500 flex items-center gap-1">
                      <RotateCcw className="w-3 h-3" />
                      Retry of #{run.source_run_id}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-400 text-sm capitalize">
                  {run.dataset}
                  {run.mode === "v2" && (
                    <span className="ml-1.5 text-[10px] font-medium px-1 py-0.5 rounded bg-purple-500/20 text-purple-400">v2</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right text-gray-300 text-sm">{run.total_questions}</td>
                <td className="px-4 py-3 text-right text-green-400 text-sm">{run.correct_count}</td>
                <td className="px-4 py-3 text-right text-red-400 text-sm">{Math.max(0, failCount)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={run.status as RunStatus} />
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {["running", "paused"].includes(run.status) && (
                      <button
                        onClick={(e) => handleStop(e, run.id, run.name)}
                        disabled={stoppingId === run.id}
                        className="p-1 text-gray-600 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors"
                        title="Cancel run"
                      >
                        {stoppingId === run.id
                          ? <Loader2 className="w-4 h-4 animate-spin" />
                          : <StopCircle className="w-4 h-4" />
                        }
                      </button>
                    )}
                    {["completed", "failed", "stopped"].includes(run.status) && (
                      <>
                        <Link
                          href={`/lab/results/${run.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="p-1 text-gray-600 hover:text-blue-400 hover:bg-blue-400/10 rounded transition-colors"
                          title="View results"
                        >
                          <BarChart3 className="w-4 h-4" />
                        </Link>
                        <button
                          onClick={(e) => handleDelete(e, run.id, run.name)}
                          disabled={deletingId === run.id}
                          className="p-1 text-gray-600 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors"
                          title="Delete run"
                        >
                          {deletingId === run.id
                            ? <Loader2 className="w-4 h-4 animate-spin" />
                            : <Trash2 className="w-4 h-4" />
                          }
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// === Dashboard Stats Bar ===

function DashboardStatsBar({ stats }: { stats: DashboardStats | undefined }) {
  if (!stats || stats.total_runs === 0) return null;

  const items = [
    { label: "Runs", value: String(stats.total_runs), sub: `${stats.completed_runs} done` },
    { label: "Questions", value: String(stats.total_questions_answered) },
    {
      label: "Accuracy",
      value: `${(stats.overall_accuracy * 100).toFixed(1)}%`,
      color: stats.overall_accuracy >= 0.7 ? "text-green-400" : stats.overall_accuracy >= 0.4 ? "text-yellow-400" : "text-red-400",
    },
    { label: "Cost", value: formatCost(stats.total_cost) },
    { label: "Time", value: formatTime(stats.total_time_seconds) },
  ];

  return (
    <div className="grid grid-cols-5 gap-3 mb-8">
      {items.map((item) => (
        <div key={item.label} className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-4 py-3">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{item.label}</div>
          <div className={`text-lg font-semibold ${item.color || "text-white"}`}>{item.value}</div>
          {item.sub && <div className="text-xs text-gray-500">{item.sub}</div>}
        </div>
      ))}
    </div>
  );
}

// === Main Dashboard ===

export default function LabPage() {
  const queryClient = useQueryClient();
  const { data: runs, isLoading } = useQuery({
    queryKey: ["lab-runs"],
    queryFn: getLabRuns,
    refetchInterval: 10000,
  });

  const { data: dashboardStats } = useQuery({
    queryKey: ["lab-dashboard"],
    queryFn: getDashboard,
    refetchInterval: 30000,
  });

  const allRuns = runs ?? [];
  const activeRuns = allRuns.filter((r) => r.status === "running" || r.status === "paused");
  const sortedRuns = [...allRuns].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const handleDelete = (id: number) => {
    queryClient.setQueryData<LabRun[]>(["lab-runs"], (old) =>
      old ? old.filter((r) => r.id !== id) : []
    );
  };

  const handleStop = (id: number) => {
    queryClient.setQueryData<LabRun[]>(["lab-runs"], (old) =>
      old ? old.map((r) => r.id === id ? { ...r, status: "stopped" as RunStatus } : r) : []
    );
  };

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FlaskConical className="w-10 h-10 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">Lab</h1>
            <p className="text-gray-500">Benchmark Testing</p>
          </div>
          <Link
            href="/lab/benchmarks"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <Database className="w-4 h-4" />
            Benchmarks
          </Link>
          <Link
            href="/lab/tests"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <Settings className="w-4 h-4" />
            Tests
          </Link>
          <Link
            href="/lab/results"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <BarChart3 className="w-4 h-4" />
            Results
          </Link>
          <Link
            href="/lab/teams"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <Users className="w-4 h-4" />
            Teams
          </Link>
          <Link
            href="/lab/paradigms"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <BookOpen className="w-4 h-4" />
            Paradigms
          </Link>
          <Link
            href="/lab/config"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <Sliders className="w-4 h-4" />
            Config
          </Link>
          <Link
            href="/lab/reports"
            className="px-3 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-300 rounded-lg font-medium flex items-center gap-2 transition-colors text-sm"
          >
            <FileText className="w-4 h-4" />
            Reports
          </Link>
          <Link
            href="/lab/new"
            className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Test
          </Link>
        </div>

        {/* Dashboard Stats */}
        <DashboardStatsBar stats={dashboardStats} />

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        )}

        {/* Empty State */}
        {!isLoading && allRuns.length === 0 && (
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-16 text-center">
            <FlaskConical className="w-16 h-16 mx-auto text-gray-600 mb-4" />
            <h2 className="text-xl font-medium text-gray-300 mb-2">No runs yet</h2>
            <p className="text-gray-500 mb-6">Create your first Lab test to get started</p>
            <Link
              href="/lab/new"
              className="px-6 py-3 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium inline-flex items-center gap-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Test
            </Link>
          </div>
        )}

        {/* Active Runs */}
        {activeRuns.length > 0 && (
          <section className="mb-8">
            <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              Active Runs
            </h2>
            <div className="space-y-3">
              {activeRuns.map((run) => (
                <ActiveRunCard key={run.id} run={run} onStop={handleStop} />
              ))}
            </div>
          </section>
        )}

        {/* All Runs Table */}
        {sortedRuns.length > 0 && (
          <section>
            <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              All Runs
            </h2>
            <RunHistoryTable runs={sortedRuns} onDelete={handleDelete} onStop={handleStop} />
          </section>
        )}
      </div>
    </main>
  );
}
