"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Save, Loader2, Settings, Plus, Trash2, X,
  ToggleLeft, ToggleRight, Upload, Download, BookOpen, ChevronDown,
} from "lucide-react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getTeam, updateTeam,
  listInstructions, getInstruction, saveInstruction,
  listParadigms, listInstructionSets, getTeamParadigmConfig, updateTeamParadigmConfig,
  type TeamResponse, type AgentConfig, type InstructionFile,
  type ParadigmInfo, type InstructionSetResponse, type TeamParadigmConfig,
} from "@/lib/lab-api";

const MODEL_GROUPS = [
  {
    provider: "Anthropic",
    models: [
      { id: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
      { id: "claude-opus-4-20250514", label: "Claude Opus 4" },
      { id: "claude-opus-4-20250514-thinking", label: "Claude Opus 4 (Thinking)" },
    ],
  },
  {
    provider: "OpenAI",
    models: [
      { id: "gpt-4o", label: "GPT-4o" },
      { id: "gpt-4o-mini", label: "GPT-4o Mini" },
    ],
  },
  {
    provider: "DeepSeek",
    models: [
      { id: "deepseek-chat", label: "DeepSeek V3" },
      { id: "deepseek-reasoner", label: "DeepSeek R1" },
    ],
  },
  {
    provider: "Moonshot",
    models: [
      { id: "kimi-k2", label: "Kimi K2" },
    ],
  },
];

const DOMAIN_KEYS = ["d1", "d2", "d3", "d4", "d5", "d6"];

function roleForKey(key: string): string {
  return key === "team_lead" ? "team_lead" : key;
}

function AgentConfigEditor({
  label,
  agentKey,
  config,
  onChange,
  onRemove,
}: {
  label: string;
  agentKey: string;
  config: AgentConfig;
  onChange: (c: AgentConfig) => void;
  onRemove?: () => void;
}) {
  const role = roleForKey(agentKey);
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saving, setSaving] = useState(false);
  const [showLoadDropdown, setShowLoadDropdown] = useState(false);
  const [files, setFiles] = useState<InstructionFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadedFrom, setLoadedFrom] = useState<string | null>(null);

  const handleSave = async () => {
    if (!saveName.trim()) return;
    setSaving(true);
    try {
      await saveInstruction(role, saveName.trim(), config.instructions);
      setShowSaveForm(false);
      setSaveName("");
      setLoadedFrom(saveName.trim());
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleOpenLoad = async () => {
    if (showLoadDropdown) {
      setShowLoadDropdown(false);
      return;
    }
    setLoadingFiles(true);
    setShowLoadDropdown(true);
    try {
      const list = await listInstructions(role);
      setFiles(list);
    } catch {
      setFiles([]);
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleLoadFile = async (file: InstructionFile) => {
    try {
      const full = await getInstruction(role, file.name);
      onChange({ ...config, instructions: full.content });
      setLoadedFrom(file.name);
      setShowLoadDropdown(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to load");
    }
  };

  return (
    <div className="bg-[#1a1a2e] border border-[#2a2a3e] rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-300">{label}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onChange({ ...config, enabled: !config.enabled })}
            className="text-gray-500 hover:text-white transition-colors"
            title={config.enabled ? "Disable" : "Enable"}
          >
            {config.enabled
              ? <ToggleRight className="w-5 h-5 text-green-400" />
              : <ToggleLeft className="w-5 h-5 text-gray-600" />}
          </button>
          {onRemove && (
            <button
              type="button"
              onClick={onRemove}
              className="text-gray-600 hover:text-red-400 transition-colors"
              title="Remove agent"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Model</label>
          <select
            value={config.model}
            onChange={(e) => onChange({ ...config, model: e.target.value })}
            className="w-full bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500"
          >
            {MODEL_GROUPS.map((group) => (
              <optgroup key={group.provider} label={group.provider}>
                {group.models.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Temperature</label>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={config.temperature}
            onChange={(e) => onChange({ ...config, temperature: parseFloat(e.target.value) || 0 })}
            className="w-full bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Max Tokens</label>
          <input
            type="number"
            min={1}
            max={32768}
            step={256}
            value={config.max_tokens}
            onChange={(e) => onChange({ ...config, max_tokens: parseInt(e.target.value) || 2048 })}
            className="w-full bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500"
          />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-gray-500">Instructions</label>
          <div className="flex items-center gap-2">
            {loadedFrom && (
              <span className="text-xs text-purple-400">Loaded: {loadedFrom}</span>
            )}
            <div className="relative">
              <button
                type="button"
                onClick={handleOpenLoad}
                className="text-xs text-gray-400 hover:text-purple-400 flex items-center gap-1 transition-colors"
                title="Load from file"
              >
                <Download className="w-3 h-3" /> Load
              </button>
              {showLoadDropdown && (
                <div className="absolute right-0 top-6 z-20 bg-[#12121a] border border-[#2a2a3e] rounded-lg shadow-xl min-w-[200px] max-h-[200px] overflow-y-auto">
                  {loadingFiles ? (
                    <div className="p-3 text-xs text-gray-500 flex items-center gap-2">
                      <Loader2 className="w-3 h-3 animate-spin" /> Loading...
                    </div>
                  ) : files.length === 0 ? (
                    <div className="p-3 text-xs text-gray-500">No saved files</div>
                  ) : (
                    files.map((f) => (
                      <button
                        key={f.name}
                        type="button"
                        onClick={() => handleLoadFile(f)}
                        className="w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-[#1a1a2e] transition-colors border-b border-[#1e1e2e] last:border-0"
                      >
                        <div className="font-medium">{f.name}</div>
                        <div className="text-gray-600 text-[10px]">
                          {new Date(f.updated_at).toLocaleDateString()}
                        </div>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => setShowSaveForm(!showSaveForm)}
              className="text-xs text-gray-400 hover:text-purple-400 flex items-center gap-1 transition-colors"
              title="Save as file"
            >
              <Upload className="w-3 h-3" /> Save as...
            </button>
          </div>
        </div>

        {showSaveForm && (
          <div className="flex items-center gap-2 mb-2">
            <input
              type="text"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="filename (e.g. default)"
              className="flex-1 bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
            />
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !saveName.trim()}
              className="px-2 py-1 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white rounded text-xs flex items-center gap-1"
            >
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              Save
            </button>
            <button
              type="button"
              onClick={() => { setShowSaveForm(false); setSaveName(""); }}
              className="text-gray-500 hover:text-gray-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <textarea
          value={config.instructions}
          onChange={(e) => { onChange({ ...config, instructions: e.target.value }); setLoadedFrom(null); }}
          placeholder="System prompt / instructions..."
          rows={2}
          className="w-full bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono resize-y"
        />
      </div>
    </div>
  );
}

export default function TeamEditPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: team, isLoading, error } = useQuery({
    queryKey: ["lab-team", id],
    queryFn: () => getTeam(id),
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [leadConfig, setLeadConfig] = useState<AgentConfig>({
    model: "gpt-4o-mini", temperature: 0.3, max_tokens: 4096, instructions: "", enabled: true,
  });
  const [agents, setAgents] = useState<Record<string, AgentConfig>>({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (team) {
      setName(team.name);
      setDescription(team.description);
      setLeadConfig(team.team_lead_config);
      setAgents(team.agent_configs);
      setDirty(false);
    }
  }, [team]);

  const markDirty = () => setDirty(true);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateTeam(id, {
        name,
        description,
        team_lead_config: leadConfig,
        agents,
      });
      queryClient.invalidateQueries({ queryKey: ["lab-teams"] });
      queryClient.invalidateQueries({ queryKey: ["lab-team", id] });
      setDirty(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const addAgent = () => {
    const existing = Object.keys(agents);
    const next = DOMAIN_KEYS.find((k) => !existing.includes(k));
    if (!next) return;
    setAgents({
      ...agents,
      [next]: { model: "gpt-4o-mini", temperature: 0.2, max_tokens: 2048, instructions: "", enabled: true },
    });
    markDirty();
  };

  const removeAgent = (key: string) => {
    const copy = { ...agents };
    delete copy[key];
    setAgents(copy);
    markDirty();
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </main>
    );
  }

  if (error || !team) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
        <div className="max-w-3xl mx-auto text-center py-20">
          <h1 className="text-xl text-red-400 mb-2">Team not found</h1>
          <Link href="/lab/teams" className="text-purple-400 hover:underline">Back to teams</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab/teams" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <Settings className="w-7 h-7 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">Edit Team</h1>
            <p className="text-sm text-gray-500">Configure agent models and parameters</p>
          </div>
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save
          </button>
        </div>

        {/* Team Metadata */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 mb-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => { setName(e.target.value); markDirty(); }}
                className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => { setDescription(e.target.value); markDirty(); }}
                placeholder="Optional description..."
                className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>
          <div className="mt-3 text-xs text-gray-600">
            ID: {team.id} · Created: {new Date(team.created_at).toLocaleDateString()}
          </div>
        </div>

        {/* Team Lead */}
        <div className="mb-6">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Settings className="w-4 h-4" /> Team Lead (D6)
          </h2>
          <AgentConfigEditor
            label="Team Lead"
            agentKey="team_lead"
            config={leadConfig}
            onChange={(c) => { setLeadConfig(c); markDirty(); }}
          />
        </div>

        {/* Domain Agents */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider flex items-center gap-2">
              Domain Agents ({Object.keys(agents).length})
            </h2>
            {Object.keys(agents).length < DOMAIN_KEYS.length && (
              <button
                onClick={addAgent}
                className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" /> Add Agent
              </button>
            )}
          </div>

          {Object.keys(agents).length === 0 ? (
            <div className="bg-[#12121a] border border-[#1e1e2e] border-dashed rounded-lg p-8 text-center">
              <p className="text-gray-500 text-sm mb-3">No domain agents configured</p>
              <button
                onClick={addAgent}
                className="text-sm text-purple-400 hover:text-purple-300 flex items-center gap-1 mx-auto transition-colors"
              >
                <Plus className="w-4 h-4" /> Add first agent
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(agents).map(([key, cfg]) => (
                <AgentConfigEditor
                  key={key}
                  label={key.toUpperCase()}
                  agentKey={key}
                  config={cfg}
                  onChange={(c) => { setAgents({ ...agents, [key]: c }); markDirty(); }}
                  onRemove={() => removeAgent(key)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Paradigm Assignments */}
        <ParadigmAssignments teamId={id} />

        {/* Unsaved indicator */}
        {dirty && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-yellow-500/20 border border-yellow-500/40 text-yellow-300 px-4 py-2 rounded-full text-sm flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            Unsaved changes
          </div>
        )}
      </div>
    </main>
  );
}

// === Paradigm Assignments Section ===

function ParadigmAssignments({ teamId }: { teamId: string }) {
  const [expanded, setExpanded] = useState(false);

  const { data: paradigms } = useQuery({
    queryKey: ["paradigms"],
    queryFn: listParadigms,
    enabled: expanded,
  });

  const { data: teamConfig, refetch: refetchConfig } = useQuery({
    queryKey: ["team-paradigm-config", teamId],
    queryFn: () => getTeamParadigmConfig(teamId),
    enabled: expanded,
  });

  const handleChange = async (paradigm: string, setId: string) => {
    const current = teamConfig?.paradigm_sets || {};
    let updated: Record<string, string>;
    if (setId === "") {
      // Remove this paradigm
      updated = { ...current };
      delete updated[paradigm];
    } else {
      updated = { ...current, [paradigm]: setId };
    }
    try {
      await updateTeamParadigmConfig(teamId, updated);
      refetchConfig();
    } catch (err) {
      console.error("Failed to update paradigm config:", err);
    }
  };

  return (
    <div className="mb-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-3"
      >
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider flex items-center gap-2">
          <BookOpen className="w-4 h-4" /> Paradigm Assignments
        </h2>
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#1e1e2e] text-gray-500 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-2 font-medium">Paradigm</th>
                <th className="text-left px-4 py-2 font-medium">Instruction Set</th>
                <th className="text-left px-4 py-2 font-medium w-24">Status</th>
              </tr>
            </thead>
            <tbody>
              {(paradigms || []).map((p) => (
                <ParadigmRow
                  key={p.id}
                  paradigm={p}
                  assignedSetId={teamConfig?.paradigm_sets?.[p.id] || ""}
                  onChange={(setId) => handleChange(p.id, setId)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ParadigmRow({
  paradigm,
  assignedSetId,
  onChange,
}: {
  paradigm: ParadigmInfo;
  assignedSetId: string;
  onChange: (setId: string) => void;
}) {
  const { data: sets } = useQuery({
    queryKey: ["paradigm-sets", paradigm.id],
    queryFn: () => listInstructionSets(paradigm.id),
  });

  const isConfigured = assignedSetId !== "";

  return (
    <tr className="border-b border-[#1e1e2e] last:border-0">
      <td className="px-4 py-2.5">
        <div className="text-sm text-white">{paradigm.name}</div>
        <div className="text-[10px] text-gray-600">{paradigm.description}</div>
      </td>
      <td className="px-4 py-2.5">
        <select
          value={assignedSetId}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500"
        >
          <option value="">Use default</option>
          {(sets || []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.is_default ? "\u2605 " : ""}{s.name} ({s.version})
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2.5">
        {isConfigured ? (
          <span className="text-xs font-medium text-green-400 bg-green-400/10 px-2 py-0.5 rounded">Configured</span>
        ) : (
          <span className="text-xs font-medium text-gray-500 bg-gray-500/10 px-2 py-0.5 rounded">Using default</span>
        )}
      </td>
    </tr>
  );
}
