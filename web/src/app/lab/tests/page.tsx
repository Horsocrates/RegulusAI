"use client";

import { useState } from "react";
import {
  FlaskConical, Plus, Trash2, ArrowLeft, Loader2, Play,
  Settings, Clock, Copy,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTestConfigs, deleteTestConfig, startTestRun, executeTestRun,
  type TestConfigResponse, formatTime,
} from "@/lib/lab-api";

function ConfigCard({
  config,
  onDelete,
  onRun,
  deleting,
  launching,
}: {
  config: TestConfigResponse;
  onDelete: () => void;
  onRun: () => void;
  deleting: boolean;
  launching: boolean;
}) {
  const created = new Date(config.created_at).toLocaleDateString();

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 hover:border-green-400/30 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <Link href={`/lab/tests/${config.id}`} className="flex-1 min-w-0">
          <h3 className="text-white font-medium truncate hover:text-blue-400 transition-colors">{config.name}</h3>
          {config.description && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">{config.description}</p>
          )}
        </Link>
        <div className="flex items-center gap-1 ml-3">
          <button
            onClick={onRun}
            disabled={launching}
            className="p-2 text-green-400 hover:bg-green-400/10 rounded-lg transition-colors disabled:opacity-50"
            title="Run this test"
          >
            {launching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          </button>
          <button
            onClick={onDelete}
            disabled={deleting}
            className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors disabled:opacity-50"
            title="Delete"
          >
            {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Benchmark</span>
          <span className="text-white">{config.benchmark}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Questions</span>
          <span className="text-white">{config.question_count ?? "All"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Per team</span>
          <span className="text-white">{config.questions_per_team}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Steps</span>
          <span className="text-white">{config.steps_count}</span>
        </div>
        {config.domains.length > 0 && (
          <div className="col-span-2 flex justify-between">
            <span className="text-gray-500">Domains</span>
            <span className="text-white truncate ml-2">{config.domains.join(", ")}</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#1e1e2e]">
        <span className="text-xs text-gray-600">
          <Clock className="w-3 h-3 inline mr-1" />
          {created}
        </span>
        <span className="text-xs text-gray-600 font-mono">{config.id.slice(0, 8)}</span>
      </div>
    </div>
  );
}

export default function TestsListPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [launchingId, setLaunchingId] = useState<string | null>(null);

  const { data: configs, isLoading } = useQuery({
    queryKey: ["lab-test-configs"],
    queryFn: listTestConfigs,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTestConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lab-test-configs"] });
      setDeletingId(null);
    },
    onError: () => setDeletingId(null),
  });

  const handleDelete = (id: string) => {
    if (!confirm("Delete this test configuration?")) return;
    setDeletingId(id);
    deleteMutation.mutate(id);
  };

  const handleRun = async (configId: string) => {
    setLaunchingId(configId);
    try {
      const run = await startTestRun(configId);
      executeTestRun(run.id).catch(console.error);
      router.push(`/lab/run/${run.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to start run");
      setLaunchingId(null);
    }
  };

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <Settings className="w-8 h-8 text-blue-400" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">Test Configurations</h1>
            <p className="text-sm text-gray-500">Manage saved test configs</p>
          </div>
          <Link
            href="/lab/new"
            className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Test
          </Link>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
          </div>
        ) : !configs?.length ? (
          <div className="text-center py-20">
            <FlaskConical className="w-12 h-12 text-gray-700 mx-auto mb-4" />
            <h2 className="text-lg font-medium text-gray-400 mb-2">No test configurations</h2>
            <p className="text-gray-600 mb-6">Create a test configuration to get started.</p>
            <Link
              href="/lab/new"
              className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Test
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {configs.map((c) => (
              <ConfigCard
                key={c.id}
                config={c}
                onDelete={() => handleDelete(c.id)}
                onRun={() => handleRun(c.id)}
                deleting={deletingId === c.id}
                launching={launchingId === c.id}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
