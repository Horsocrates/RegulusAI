"use client";

import { useState } from "react";
import {
  ArrowLeft, Users, Plus, Trash2, Loader2, Star, Copy,
  ChevronDown, ChevronRight, Settings, Save, X, Pencil,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listTeams,
  createTeam,
  deleteTeam,
  setDefaultTeam,
  cloneTeam,
  type TeamResponse,
  type AgentConfig,
} from "@/lib/lab-api";

// === Team Card ===

function TeamCard({ team, onRefresh }: { team: TeamResponse; onRefresh: () => void }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [cloning, setCloning] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete team "${team.name}"?`)) return;
    setDeleting(true);
    try {
      await deleteTeam(team.id);
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setDeleting(false);
    }
  };

  const handleSetDefault = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await setDefaultTeam(team.id);
      onRefresh();
    } catch (err) {
      console.error(err);
    }
  };

  const handleClone = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setCloning(true);
    try {
      await cloneTeam(team.id, `${team.name} (copy)`);
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setCloning(false);
    }
  };

  const agentCount = Object.keys(team.agent_configs).length;
  const leadModel = team.team_lead_config?.model || "—";

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-[#1a1a2e]/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {expanded ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
            <div>
              <div className="flex items-center gap-2">
                <span className="text-white font-medium">{team.name}</span>
                {team.is_default && (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 flex items-center gap-0.5">
                    <Star className="w-2.5 h-2.5" /> Default
                  </span>
                )}
              </div>
              {team.description && (
                <div className="text-xs text-gray-500 mt-0.5">{team.description}</div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-xs text-gray-500">
              <span className="text-gray-400">{leadModel}</span>
              <span className="mx-1.5">·</span>
              <span>{agentCount} agent{agentCount !== 1 ? "s" : ""}</span>
            </div>
            <div className="flex items-center gap-1">
              {!team.is_default && (
                <button
                  onClick={handleSetDefault}
                  className="p-1.5 text-gray-600 hover:text-yellow-400 rounded transition-colors"
                  title="Set as default"
                >
                  <Star className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); router.push(`/lab/teams/${team.id}`); }}
                className="p-1.5 text-gray-600 hover:text-purple-400 rounded transition-colors"
                title="Edit team"
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleClone}
                disabled={cloning}
                className="p-1.5 text-gray-600 hover:text-blue-400 rounded transition-colors"
                title="Clone team"
              >
                {cloning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="p-1.5 text-gray-600 hover:text-red-400 rounded transition-colors"
                title="Delete team"
              >
                {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-[#1e1e2e] p-4">
          {/* Team Lead Config */}
          <div className="mb-4">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Settings className="w-3 h-3" /> Team Lead
            </h3>
            <div className="grid grid-cols-4 gap-3 text-sm">
              <div>
                <span className="text-gray-500 text-xs">Model</span>
                <div className="text-gray-300">{team.team_lead_config.model}</div>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Temperature</span>
                <div className="text-gray-300">{team.team_lead_config.temperature}</div>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Max Tokens</span>
                <div className="text-gray-300">{team.team_lead_config.max_tokens.toLocaleString()}</div>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Enabled</span>
                <div className={team.team_lead_config.enabled ? "text-green-400" : "text-red-400"}>
                  {team.team_lead_config.enabled ? "Yes" : "No"}
                </div>
              </div>
            </div>
            {team.team_lead_config.instructions && (
              <div className="mt-2">
                <span className="text-gray-500 text-xs">Instructions</span>
                <div className="text-xs text-gray-400 bg-[#1a1a2e] rounded p-2 mt-1 max-h-20 overflow-auto font-mono">
                  {team.team_lead_config.instructions}
                </div>
              </div>
            )}
          </div>

          {/* Domain Agents */}
          {agentCount > 0 && (
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Domain Agents ({agentCount})
              </h3>
              <div className="space-y-2">
                {Object.entries(team.agent_configs).map(([domain, cfg]) => (
                  <div key={domain} className="flex items-center justify-between bg-[#1a1a2e] rounded px-3 py-2">
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-gray-300 font-medium">{domain}</span>
                      <span className="text-xs text-gray-500">{cfg.model}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>t={cfg.temperature}</span>
                      <span>{cfg.max_tokens.toLocaleString()} tok</span>
                      <span className={cfg.enabled ? "text-green-400" : "text-red-400"}>
                        {cfg.enabled ? "on" : "off"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {agentCount === 0 && (
            <div className="text-sm text-gray-500 italic">No domain agents configured.</div>
          )}

          {/* Metadata */}
          <div className="mt-4 flex items-center gap-4 text-xs text-gray-600">
            <span>ID: {team.id.slice(0, 8)}...</span>
            <span>Created: {new Date(team.created_at).toLocaleDateString()}</span>
            <span>Updated: {new Date(team.updated_at).toLocaleDateString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// === Create Team Dialog ===

function CreateTeamForm({ onCreated, onCancel }: { onCreated: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      await createTeam({ name: name.trim(), description: description.trim() });
      onCreated();
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-white">Create Team</h3>
        <button type="button" onClick={onCancel} className="text-gray-500 hover:text-gray-300">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Alpha Team"
            className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
            autoFocus
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Description (optional)</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Team description..."
            className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
          />
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim() || creating}
            className="px-4 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded font-medium flex items-center gap-1.5 transition-colors"
          >
            {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Create
          </button>
        </div>
      </div>
    </form>
  );
}

// === Main Page ===

export default function TeamsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const queryClient = useQueryClient();

  const { data: teams, isLoading } = useQuery({
    queryKey: ["lab-teams"],
    queryFn: listTeams,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["lab-teams"] });
    setShowCreate(false);
  };

  const allTeams = teams ?? [];
  const defaultTeams = allTeams.filter((t) => t.is_default);
  const otherTeams = allTeams.filter((t) => !t.is_default);

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <Users className="w-8 h-8 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">Teams</h1>
            <p className="text-gray-500">Manage agent team configurations</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Team
          </button>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        )}

        {/* Create Form */}
        {showCreate && (
          <div className="mb-6">
            <CreateTeamForm onCreated={refresh} onCancel={() => setShowCreate(false)} />
          </div>
        )}

        {/* Empty State */}
        {!isLoading && allTeams.length === 0 && !showCreate && (
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-16 text-center">
            <Users className="w-16 h-16 mx-auto text-gray-600 mb-4" />
            <h2 className="text-xl font-medium text-gray-300 mb-2">No teams yet</h2>
            <p className="text-gray-500 mb-6">Create your first team to configure agent settings</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium inline-flex items-center gap-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create Team
            </button>
          </div>
        )}

        {/* Teams List */}
        {!isLoading && allTeams.length > 0 && (
          <div className="space-y-3">
            {/* Default teams first */}
            {defaultTeams.map((team) => (
              <TeamCard key={team.id} team={team} onRefresh={refresh} />
            ))}
            {/* Then the rest */}
            {otherTeams.map((team) => (
              <TeamCard key={team.id} team={team} onRefresh={refresh} />
            ))}
          </div>
        )}

        {/* Summary */}
        {!isLoading && allTeams.length > 0 && (
          <div className="mt-6 text-xs text-gray-600 text-center">
            {allTeams.length} team{allTeams.length !== 1 ? "s" : ""}
            {defaultTeams.length > 0 && ` · ${defaultTeams.length} default`}
          </div>
        )}
      </div>
    </main>
  );
}
