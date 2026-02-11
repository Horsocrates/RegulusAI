"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Play, Settings, Loader2, Trash2, Clock, Users,
  FlaskConical, Pencil, Save, X,
} from "lucide-react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getTestConfig, updateTestConfig, deleteTestConfig,
  startTestRun, executeTestRun, getTeam,
  type TestConfigResponse,
} from "@/lib/lab-api";

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between py-2 border-b border-[#1e1e2e] last:border-0">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="text-white text-sm">{children}</span>
    </div>
  );
}

export default function TestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: config, isLoading, error } = useQuery({
    queryKey: ["lab-test-config", id],
    queryFn: () => getTestConfig(id),
  });

  const { data: team } = useQuery({
    queryKey: ["lab-team", config?.team_id],
    queryFn: () => getTeam(config!.team_id),
    enabled: !!config?.team_id,
  });

  const [launching, setLaunching] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);

  const handleRun = async () => {
    setLaunching(true);
    try {
      const run = await startTestRun(id);
      executeTestRun(run.id).catch(console.error);
      router.push(`/lab/run/${run.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to start run");
      setLaunching(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this test configuration? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteTestConfig(id);
      router.push("/lab/tests");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
      setDeleting(false);
    }
  };

  const startEditing = () => {
    if (!config) return;
    setEditName(config.name);
    setEditDesc(config.description);
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateTestConfig(id, { name: editName });
      queryClient.invalidateQueries({ queryKey: ["lab-test-config", id] });
      queryClient.invalidateQueries({ queryKey: ["lab-test-configs"] });
      setEditing(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
      </main>
    );
  }

  if (error || !config) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
        <div className="max-w-3xl mx-auto text-center py-20">
          <h1 className="text-xl text-red-400 mb-2">Test config not found</h1>
          <Link href="/lab/tests" className="text-blue-400 hover:underline">Back to tests</Link>
        </div>
      </main>
    );
  }

  const judgeConfig = config.judge_config as Record<string, unknown> | undefined;

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab/tests" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FlaskConical className="w-7 h-7 text-blue-400" />
          <div className="flex-1">
            {editing ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-1 text-lg text-white font-bold focus:outline-none focus:border-blue-500"
                  autoFocus
                />
                <button
                  onClick={handleSave}
                  disabled={saving || !editName.trim()}
                  className="p-1.5 text-green-400 hover:bg-green-400/10 rounded disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="p-1.5 text-gray-500 hover:text-gray-300 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white">{config.name}</h1>
                <button
                  onClick={startEditing}
                  className="p-1 text-gray-600 hover:text-gray-300 rounded"
                  title="Edit name"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            {config.description && (
              <p className="text-sm text-gray-500 mt-0.5">{config.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRun}
              disabled={launching}
              className="px-4 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
            >
              {launching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-3 py-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors disabled:opacity-50"
              title="Delete config"
            >
              {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Benchmark Settings */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 mb-4">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Settings className="w-3 h-3" /> Benchmark Settings
          </h2>
          <DetailRow label="Benchmark">{config.benchmark}</DetailRow>
          <DetailRow label="Questions">{config.question_count ?? "All"}</DetailRow>
          <DetailRow label="Shuffle">{config.shuffle ? "Yes" : "No"}</DetailRow>
          {config.domains.length > 0 && (
            <DetailRow label="Domains">
              <div className="flex flex-wrap gap-1 justify-end">
                {config.domains.map((d) => (
                  <span key={d} className="text-xs bg-[#1a1a2e] px-2 py-0.5 rounded text-gray-300">
                    {d}
                  </span>
                ))}
              </div>
            </DetailRow>
          )}
        </div>

        {/* Execution Settings */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 mb-4">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <FlaskConical className="w-3 h-3" /> Execution
          </h2>
          <DetailRow label="Questions per team">{config.questions_per_team}</DetailRow>
          <DetailRow label="Steps per question">{config.steps_count}</DetailRow>
        </div>

        {/* Team */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 mb-4">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Users className="w-3 h-3" /> Team
          </h2>
          {team ? (
            <div>
              <DetailRow label="Team">
                <Link
                  href={`/lab/teams/${team.id}`}
                  className="text-purple-400 hover:underline"
                >
                  {team.name}
                </Link>
              </DetailRow>
              <DetailRow label="Lead model">{team.team_lead_config.model}</DetailRow>
              <DetailRow label="Agents">{Object.keys(team.agent_configs).length}</DetailRow>
            </div>
          ) : (
            <DetailRow label="Team ID">
              <span className="font-mono text-xs">{config.team_id}</span>
            </DetailRow>
          )}
        </div>

        {/* Judge */}
        {judgeConfig && (
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 mb-4">
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Judge Config
            </h2>
            {Object.entries(judgeConfig).map(([key, val]) => (
              <DetailRow key={key} label={key}>{String(val)}</DetailRow>
            ))}
          </div>
        )}

        {/* Metadata */}
        <div className="text-xs text-gray-600 text-center mt-6">
          <Clock className="w-3 h-3 inline mr-1" />
          Created {new Date(config.created_at).toLocaleString()}
          <span className="mx-2">·</span>
          <span className="font-mono">{config.id}</span>
        </div>
      </div>
    </main>
  );
}
