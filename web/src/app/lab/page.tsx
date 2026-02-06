"use client";

import { useState } from "react";
import {
  FlaskConical, Plus, Trash2, ArrowLeft, Loader2, CheckCircle,
  Clock, PauseCircle, XCircle, ExternalLink, RotateCcw,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getLabRuns, deleteLabRun, getRunStats,
  type LabRun, type RunStatus, STATUS_CONFIG, formatCost, formatTime,
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

function ActiveRunCard({ run }: { run: LabRun }) {
  const router = useRouter();

  const { data: stats } = useQuery({
    queryKey: ["lab-run-stats", run.id],
    queryFn: () => getRunStats(run.id),
    refetchInterval: 5000,
    enabled: run.status === "running",
  });

  const completed = stats?.completed ?? run.completed_questions;
  const total = run.total_questions;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const passed = stats?.passed ?? run.valid_count;
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
        <span className="text-sm text-gray-400">{run.concurrency} agents</span>
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

function RunHistoryTable({ runs, onDelete }: { runs: LabRun[]; onDelete: (id: number) => void }) {
  const router = useRouter();
  const [deletingId, setDeletingId] = useState<number | null>(null);

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
            const failCount = run.completed_questions - run.valid_count;
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
                <td className="px-4 py-3 text-gray-400 text-sm capitalize">{run.dataset}</td>
                <td className="px-4 py-3 text-right text-gray-300 text-sm">{run.total_questions}</td>
                <td className="px-4 py-3 text-right text-green-400 text-sm">{run.valid_count}</td>
                <td className="px-4 py-3 text-right text-red-400 text-sm">{Math.max(0, failCount)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={run.status as RunStatus} />
                </td>
                <td className="px-4 py-3 text-right">
                  {["completed", "failed", "stopped"].includes(run.status) && (
                    <button
                      onClick={(e) => handleDelete(e, run.id, run.name)}
                      disabled={deletingId === run.id}
                      className="p-1 text-gray-600 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors"
                    >
                      {deletingId === run.id
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : <Trash2 className="w-4 h-4" />
                      }
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
            href="/lab/new"
            className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Test
          </Link>
        </div>

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
                <ActiveRunCard key={run.id} run={run} />
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
            <RunHistoryTable runs={sortedRuns} onDelete={handleDelete} />
          </section>
        )}
      </div>
    </main>
  );
}
