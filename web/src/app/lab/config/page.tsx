"use client";

import { useState, useCallback, useEffect } from "react";
import {
  ArrowLeft, Loader2, Save, ChevronDown,
  Eye, Pencil, Plus, X, FileText, Copy, Settings,
} from "lucide-react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listParadigmConfigs,
  updateParadigmConfig,
  listInstructionSetDirs,
  getInstructionSetDetail,
  createInstructionSetDir,
  updateInstructionFile,
  getResolutionPreview,
  type ParadigmConfigResponse,
  type InstructionSetSummary,
  type InstructionSetDetail,
  type ResolutionPreview,
} from "@/lib/lab-api";
import ModelSettingsPanel from "./ModelSettingsPanel";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODELS = [
  { id: "opus-4.6", name: "Claude Opus 4.6", tier: "premium", tokens: "200K" },
  { id: "sonnet-4.5", name: "Claude Sonnet 4.5", tier: "fast", tokens: "200K" },
  { id: "haiku-4.5", name: "Claude Haiku 4.5", tier: "cheap", tokens: "200K" },
  { id: "gpt-4o", name: "GPT-4o", tier: "fast", tokens: "128K" },
  { id: "o3-mini", name: "o3-mini", tier: "reasoning", tokens: "128K" },
  { id: "deepseek-r1", name: "DeepSeek R1", tier: "reasoning", tokens: "64K" },
] as const;

const ROLES = [
  { id: "team_lead", name: "Team Lead", icon: "\u25C6", desc: "Classifies, routes, verifies", required: true },
  { id: "d1", name: "D1 Recognize", icon: "\u2460", desc: "ERR decomposition" },
  { id: "d2", name: "D2 Clarify", icon: "\u2461", desc: "Definitions & depth" },
  { id: "d3", name: "D3 Framework", icon: "\u2462", desc: "Method selection" },
  { id: "d4", name: "D4 Compare", icon: "\u2463", desc: "Analysis & computation" },
  { id: "d5", name: "D5 Infer", icon: "\u2464", desc: "Conclusions" },
  { id: "d6", name: "D6 Reflect", icon: "\u2465", desc: "Verification & limits" },
] as const;

const SUBPROCESS_ROLES = [
  { id: "re_reader", name: "Re-Reader", icon: "\u25C7", desc: "Question re-interpretation" },
  { id: "adversarial", name: "Adversarial Verifier", icon: "\u2694", desc: "Attacks proposed answer" },
  { id: "dual_solver", name: "Dual-Path Solver", icon: "\u21F6", desc: "Independent computation" },
  { id: "exhaustive", name: "Exhaustive Checker", icon: "\u25A6", desc: "Brute-force enumeration" },
  { id: "executor", name: "Code Executor", icon: "\u25B6", desc: "Run & trace code" },
  { id: "searcher", name: "Fact Searcher", icon: "\u25CE", desc: "Web search & verify" },
  { id: "consistency", name: "Consistency Check", icon: "\u229C", desc: "Cross-statement logic" },
] as const;

type TierKey = "premium" | "fast" | "cheap" | "reasoning";
const TIER_COLORS: Record<TierKey, string> = {
  premium: "bg-amber-400",
  fast: "bg-blue-400",
  cheap: "bg-emerald-400",
  reasoning: "bg-violet-400",
};

// Default file mapping: role → instruction filename
const ROLE_DEFAULT_FILES: Record<string, string> = {
  team_lead: "analyze.md",
  d1: "d1-recognize.md",
  d2: "d2-clarify.md",
  d3: "d3-framework.md",
  d4: "d4-compare.md",
  d5: "d5-infer.md",
  d6: "d6-reflect.md",
};

// ---------------------------------------------------------------------------
// Local paradigm state
// ---------------------------------------------------------------------------

interface LocalParadigm {
  id: string;
  name: string;
  label: string;
  color: string;
  description: string;
  signals: string[];
  activeRoles: string[];
  activeSubprocesses: string[];
  roleModels: Record<string, string>;
  roleInstructions: Record<string, string>;
  instructionSetId: string;
}

function apiToLocal(cfg: ParadigmConfigResponse): LocalParadigm {
  return {
    id: cfg.id,
    name: cfg.name,
    label: cfg.label,
    color: cfg.color,
    description: cfg.description,
    signals: cfg.signals,
    activeRoles: cfg.active_roles,
    activeSubprocesses: cfg.active_subprocesses,
    roleModels: cfg.role_models,
    roleInstructions: cfg.role_instructions,
    instructionSetId: cfg.instruction_set_id,
  };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ModelSelector({
  value,
  onChange,
  compact,
}: {
  value: string;
  onChange: (v: string) => void;
  compact?: boolean;
}) {
  const selected = MODELS.find((m) => m.id === value);
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-1.5 bg-white/[0.04] border border-white/10 rounded-md text-[#e2e8f0] cursor-pointer hover:border-white/25 transition-colors ${
          compact ? "px-2 py-1 text-[11px]" : "px-3 py-1.5 text-[13px]"
        }`}
      >
        {selected && (
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${TIER_COLORS[selected.tier as TierKey]}`} />
        )}
        <span className="flex-1 text-left truncate">{selected ? selected.name : "Select model"}</span>
        <ChevronDown className="w-3 h-3 opacity-40" />
      </button>
      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#1a1f2e] border border-white/[0.12] rounded-lg p-1 z-50 shadow-[0_12px_40px_rgba(0,0,0,0.5)]">
          {MODELS.map((m) => (
            <button
              key={m.id}
              onClick={() => { onChange(m.id); setOpen(false); }}
              className={`flex items-center gap-2 w-full px-2.5 py-2 rounded text-[#e2e8f0] text-xs text-left transition-colors ${
                value === m.id ? "bg-white/[0.06]" : "hover:bg-white/[0.04]"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${TIER_COLORS[m.tier as TierKey]}`} />
              <span className="flex-1">{m.name}</span>
              <span className="opacity-30 text-[10px]">{m.tokens}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function InstructionFileSelector({
  roleId,
  value,
  availableFiles,
  onChange,
}: {
  roleId: string;
  value: string;
  availableFiles: string[];
  onChange: (filename: string) => void;
}) {
  const defaultFile = ROLE_DEFAULT_FILES[roleId] || "";
  const displayValue = value || defaultFile;

  return (
    <div>
      <div className="text-[10px] text-gray-600 mb-0.5">Instruction file</div>
      <div className="relative">
        <select
          value={displayValue}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-white/[0.04] border border-white/10 rounded-md text-[#e2e8f0] px-2 py-1.5 text-[11px] cursor-pointer hover:border-white/25 transition-colors appearance-none pr-7 font-mono"
        >
          {availableFiles.map((f) => (
            <option key={f} value={f}>
              {f}{f === defaultFile ? " (default)" : ""}
            </option>
          ))}
          {availableFiles.length === 0 && (
            <option value="">No files available</option>
          )}
        </select>
        <ChevronDown className="w-3 h-3 absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
      </div>
    </div>
  );
}

function RoleCard({
  role,
  paradigm,
  availableFiles,
  onModelChange,
  onInstructionChange,
  onOpenSettings,
  isSubprocess,
}: {
  role: (typeof ROLES)[number] | (typeof SUBPROCESS_ROLES)[number];
  paradigm: LocalParadigm;
  availableFiles: string[];
  onModelChange: (roleId: string, modelId: string) => void;
  onInstructionChange: (roleId: string, filename: string) => void;
  onOpenSettings?: (roleId: string, modelId: string) => void;
  isSubprocess?: boolean;
}) {
  const modelId = paradigm.roleModels[role.id] || "";
  const selectedFile = paradigm.roleInstructions[role.id] || "";
  const isActive = isSubprocess
    ? paradigm.activeSubprocesses.includes(role.id)
    : paradigm.activeRoles.includes(role.id);

  return (
    <div
      className={`rounded-lg p-3 transition-all ${
        isActive
          ? "bg-white/[0.03] border border-white/[0.08]"
          : "bg-white/[0.01] border border-white/[0.04] opacity-40"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className="text-base w-7 h-7 flex items-center justify-center rounded-md"
          style={{
            background: isActive ? `${paradigm.color}18` : "transparent",
            color: isActive ? paradigm.color : "#475569",
          }}
        >
          {role.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold text-[#e2e8f0]">{role.name}</div>
          <div className="text-[10px] text-gray-500">{role.desc}</div>
        </div>
        {isActive && isSubprocess && (
          <span
            className="text-[9px] font-semibold tracking-wide px-1.5 py-0.5 rounded"
            style={{ background: `${paradigm.color}20`, color: paradigm.color }}
          >
            SUBPROCESS
          </span>
        )}
      </div>
      {isActive && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-1.5">
            <ModelSelector value={modelId} onChange={(v) => onModelChange(role.id, v)} compact />
            {modelId && onOpenSettings && (
              <button
                onClick={() => onOpenSettings(role.id, modelId)}
                className="flex items-center gap-1.5 w-full px-2 py-1 rounded bg-white/[0.03] border border-white/[0.08] text-gray-500 hover:text-gray-300 hover:bg-white/[0.06] hover:border-white/[0.15] transition-colors text-[10px]"
              >
                <Settings className="w-3 h-3" />
                <span>Thinking &amp; Token Settings</span>
              </button>
            )}
          </div>
          {availableFiles.length > 0 && (
            <InstructionFileSelector
              roleId={role.id}
              value={selectedFile}
              availableFiles={availableFiles}
              onChange={(v) => onInstructionChange(role.id, v)}
            />
          )}
          {role.id === "team_lead" && (
            <div className="text-[10px] text-amber-400/70 bg-amber-500/[0.06] rounded px-2 py-1.5 border border-amber-500/10">
              {"\u25C6"} After paradigm classification {"\u2192"} loads selected instruction files for each domain agent
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function WorkflowDiagram({ paradigm }: { paradigm: LocalParadigm }) {
  const domains = paradigm.activeRoles.filter((r) => r !== "team_lead");
  const subprocesses = paradigm.activeSubprocesses;

  const subprocessPositions: Record<string, { after: string; label: string }> = {
    re_reader: { after: "d1", label: "Re-Reader" },
    adversarial: { after: "d5", label: "Adversary" },
    dual_solver: { after: "d5", label: "Dual-Path" },
    exhaustive: { after: "d4", label: "Exhaustive" },
    executor: { after: "d1", label: "Execute" },
    searcher: { after: "d2", label: "Search" },
    consistency: { after: "d5", label: "Consistency" },
  };

  return (
    <div className="bg-black/20 rounded-lg p-4 border border-white/[0.05]">
      <div className="text-[10px] text-gray-500 font-semibold tracking-widest mb-2.5">PIPELINE FLOW</div>
      <div className="flex items-center gap-0.5 flex-wrap">
        <span
          className="text-[11px] px-2.5 py-1 rounded font-semibold"
          style={{ background: `${paradigm.color}20`, color: paradigm.color }}
        >
          {"\u25C6"} Lead
        </span>
        {domains.map((d) => {
          const role = ROLES.find((r) => r.id === d);
          const subsHere = subprocesses.filter((s) => subprocessPositions[s]?.after === d);
          return (
            <div key={d} className="flex items-center gap-0.5">
              <span className="text-gray-700 text-xs">{"\u2192"}</span>
              <span className="text-[11px] px-2 py-1 bg-white/[0.05] text-gray-400 rounded">
                {role?.icon} {d.toUpperCase()}
              </span>
              {subsHere.map((s) => (
                <span
                  key={s}
                  className="text-[9px] px-1.5 py-0.5 rounded ml-0.5"
                  style={{
                    background: `${paradigm.color}15`,
                    color: paradigm.color,
                    border: `1px dashed ${paradigm.color}40`,
                  }}
                >
                  {"\u2197"} {subprocessPositions[s].label}
                </span>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GlobalModelSetter({ onApplyAll }: { onApplyAll: (modelId: string) => void }) {
  const [model, setModel] = useState("");

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-white/[0.02] rounded-md border border-white/[0.06]">
      <span className="text-[11px] text-gray-500 whitespace-nowrap">Apply to all roles:</span>
      <div className="w-44">
        <ModelSelector value={model} onChange={setModel} compact />
      </div>
      <button
        onClick={() => model && onApplyAll(model)}
        disabled={!model}
        className="px-3 py-1 bg-white/[0.08] border border-white/10 rounded text-[11px] text-[#e2e8f0] disabled:opacity-30 disabled:cursor-default hover:bg-white/[0.12] transition-colors"
      >
        Apply
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Instruction Set Selector (dropdown + View/Edit/Create)
// ---------------------------------------------------------------------------

function InstructionSetSelector({
  value,
  onChange,
  sets,
  paradigmColor,
  onView,
  onCreate,
}: {
  value: string;
  onChange: (id: string) => void;
  sets: InstructionSetSummary[];
  paradigmColor: string;
  onView: (id: string) => void;
  onCreate: () => void;
}) {
  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-3.5 mb-4">
      <div className="text-[10px] text-gray-500 font-semibold tracking-widest mb-2">
        INSTRUCTION SET — Markdown prompts loaded by each agent
      </div>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500 appearance-none pr-8"
          >
            {sets.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.file_count} files)
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
        </div>
        <button
          onClick={() => onView(value)}
          className="px-2.5 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] text-gray-400 rounded text-xs flex items-center gap-1 transition-colors"
          title="View instruction files"
        >
          <Eye className="w-3.5 h-3.5" />
          View
        </button>
        <button
          onClick={onCreate}
          className="px-2.5 py-2 rounded text-xs flex items-center gap-1 transition-colors"
          style={{ background: `${paradigmColor}20`, color: paradigmColor, border: `1px solid ${paradigmColor}30` }}
          title="Create new instruction set"
        >
          <Plus className="w-3.5 h-3.5" />
          New
        </button>
      </div>
      {value !== "default" && (
        <div className="mt-1.5 text-[10px] text-gray-600">
          Missing files fall back to <span className="text-gray-400">default/</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Instruction Resolution Preview
// ---------------------------------------------------------------------------

const LEVEL_LABELS: Record<string, { label: string; color: string }> = {
  specialist: { label: "L1 SPECIALIST", color: "#ef4444" },
  paradigm_skill: { label: "L2 PARADIGM+SKILL", color: "#f97316" },
  paradigm_domain: { label: "L3 PARADIGM", color: "#f59e0b" },
  skill: { label: "L4 SKILL", color: "#3b82f6" },
  default_skill: { label: "L5 DEFAULT+SKILL", color: "#8b5cf6" },
  default: { label: "L6 DEFAULT", color: "#64748b" },
  none: { label: "NONE", color: "#374151" },
};

const SKILL_OPTIONS = [
  { id: "", label: "No skill type" },
  { id: "decomposition", label: "Decomposition" },
  { id: "verification", label: "Verification" },
  { id: "recall", label: "Recall" },
  { id: "computation", label: "Computation" },
  { id: "conceptual", label: "Conceptual" },
];

function InstructionResolutionPreview({
  instructionSetId,
  paradigmId,
  paradigmColor,
}: {
  instructionSetId: string;
  paradigmId: string;
  paradigmColor: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [skillType, setSkillType] = useState("");

  const { data: preview } = useQuery({
    queryKey: ["resolution-preview", instructionSetId, skillType, paradigmId],
    queryFn: () => getResolutionPreview({
      set_id: instructionSetId,
      skill_type: skillType || undefined,
      paradigm_id: paradigmId || undefined,
    }),
    enabled: expanded,
  });

  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg mb-4 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500 font-semibold tracking-widest">
            INSTRUCTION RESOLUTION PREVIEW
          </span>
          {!expanded && preview && (
            <span className="text-[10px] text-gray-600">
              ({Object.values(preview.roles).filter(r => r.has_content).length}/{Object.keys(preview.roles).length} resolved)
            </span>
          )}
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-gray-600 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="px-3.5 pb-3.5 space-y-3">
          {/* Skill type selector */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500">Simulate skill type:</span>
            <select
              value={skillType}
              onChange={(e) => setSkillType(e.target.value)}
              className="px-2 py-0.5 bg-black/30 border border-white/[0.08] rounded text-gray-300 text-[11px] outline-none focus:border-white/20"
            >
              {SKILL_OPTIONS.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Resolution table */}
          {preview ? (
            <div className="space-y-1">
              {Object.entries(preview.roles).map(([role, info]) => {
                const lvl = LEVEL_LABELS[info.resolved_level] || LEVEL_LABELS.none;
                return (
                  <div key={role} className="flex items-center gap-2 py-1 px-2 rounded hover:bg-white/[0.02]">
                    <span className="text-[11px] text-gray-400 w-20 font-mono">{role}</span>
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                      style={{ background: `${lvl.color}20`, color: lvl.color }}
                    >
                      {lvl.label}
                    </span>
                    <span className="text-[10px] text-gray-600 font-mono flex-1 truncate">
                      {info.trace.find(t => t.hit)?.path || "—"}
                    </span>
                    <span className="text-[10px] text-gray-600">
                      {info.has_content ? `${(info.content_length / 1024).toFixed(1)}KB` : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex items-center gap-2 py-2 text-gray-600">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span className="text-[11px]">Loading resolution preview...</span>
            </div>
          )}

          {/* Legend */}
          <div className="flex flex-wrap gap-2 pt-1 border-t border-white/[0.04]">
            {Object.entries(LEVEL_LABELS).filter(([k]) => k !== "none").map(([key, { label, color }]) => (
              <span
                key={key}
                className="text-[8px] px-1.5 py-0.5 rounded"
                style={{ background: `${color}15`, color: `${color}99` }}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View/Edit Modal — shows instruction set files
// ---------------------------------------------------------------------------

function InstructionSetModal({
  setId,
  onClose,
  onSaved,
}: {
  setId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ["instruction-set-detail", setId],
    queryFn: () => getInstructionSetDetail(setId),
  });

  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);

  const startEdit = (filename: string, content: string) => {
    setEditingFile(filename);
    setEditContent(content);
  };

  const handleSave = async () => {
    if (!editingFile) return;
    setSaving(true);
    try {
      await updateInstructionFile(setId, editingFile, editContent);
      onSaved();
      setEditingFile(null);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const files = detail?.files || {};
  const ownFiles = new Set(detail?.own_files || []);
  const sortedFiles = Object.keys(files).sort();

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-8">
      <div className="bg-[#12121a] border border-[#2a2a3e] rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1e1e2e]">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white">
              Instruction Set: {detail?.name || setId}
            </h2>
            <span className="text-xs text-gray-500">({sortedFiles.length} files)</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
            </div>
          ) : editingFile ? (
            /* Edit mode */
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Pencil className="w-4 h-4 text-purple-400" />
                  <span className="text-sm font-medium text-white">{editingFile}</span>
                  {!ownFiles.has(editingFile) && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">
                      INHERITED — editing will create override
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setEditingFile(null)}
                    className="px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white rounded text-xs font-medium flex items-center gap-1"
                  >
                    {saving && <Loader2 className="w-3 h-3 animate-spin" />}
                    Save File
                  </button>
                </div>
              </div>
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full h-[50vh] bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-purple-500 resize-none"
                autoFocus
              />
            </div>
          ) : (
            /* File list view */
            <div className="space-y-2">
              {sortedFiles.map((fname) => {
                const content = files[fname];
                const isOwn = ownFiles.has(fname);
                const lines = content.split("\n").length;
                const preview = content.slice(0, 200).replace(/\n/g, " ");

                return (
                  <div
                    key={fname}
                    className="bg-[#1a1a2e] border border-[#2a2a3e] rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <FileText className="w-3.5 h-3.5 text-gray-500" />
                        <span className="text-sm font-medium text-white">{fname}</span>
                        <span className="text-[10px] text-gray-600">{lines} lines</span>
                        {!isOwn && setId !== "default" && (
                          <span className="text-[9px] px-1.5 py-0.5 bg-blue-500/15 text-blue-400 rounded">
                            inherited
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => startEdit(fname, content)}
                        className="text-xs text-gray-500 hover:text-purple-400 flex items-center gap-1 transition-colors"
                      >
                        <Pencil className="w-3 h-3" />
                        Edit
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 font-mono truncate">{preview}...</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create Instruction Set Modal
// ---------------------------------------------------------------------------

function CreateSetModal({
  existingSets,
  onClose,
  onCreated,
}: {
  existingSets: InstructionSetSummary[];
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [cloneFrom, setCloneFrom] = useState("default");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const handleCreate = async () => {
    if (!id.trim()) return;
    setCreating(true);
    setError("");
    try {
      await createInstructionSetDir({
        id: id.trim(),
        name: name.trim() || undefined,
        clone_from: cloneFrom || undefined,
      });
      onCreated(id.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#12121a] border border-[#2a2a3e] rounded-xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">New Instruction Set</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">ID (lowercase, underscores only)</label>
            <input
              type="text"
              value={id}
              onChange={(e) => setId(e.target.value.replace(/[^a-z0-9_]/g, ""))}
              placeholder="e.g. compute_strict"
              className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Display Name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Compute + Strict Verification"
              className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Clone from</label>
            <div className="relative">
              <select
                value={cloneFrom}
                onChange={(e) => setCloneFrom(e.target.value)}
                className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500 appearance-none pr-8"
              >
                <option value="">Empty (inherit all from default)</option>
                {existingSets.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.file_count} files)
                  </option>
                ))}
              </select>
              <Copy className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>
        <div className="flex items-center justify-end gap-3 mt-5">
          <button onClick={onClose} className="px-4 py-2 text-gray-400 hover:text-gray-200 text-sm">
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={creating || !id.trim()}
            className="px-4 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-40 text-white rounded-lg text-sm font-medium flex items-center gap-2"
          >
            {creating && <Loader2 className="w-4 h-4 animate-spin" />}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function TeamConfigPage() {
  const queryClient = useQueryClient();

  // Fetch paradigm configs from API
  const { data: apiConfigs, isLoading } = useQuery({
    queryKey: ["paradigm-configs"],
    queryFn: listParadigmConfigs,
  });

  // Fetch instruction sets
  const { data: instructionSets } = useQuery({
    queryKey: ["instruction-sets"],
    queryFn: listInstructionSetDirs,
  });

  // Local state
  const [paradigms, setParadigms] = useState<LocalParadigm[]>([]);
  const [activeParadigm, setActiveParadigm] = useState("");
  const [showSubprocesses, setShowSubprocesses] = useState(true);
  const [newSignal, setNewSignal] = useState("");
  const [dirty, setDirty] = useState(false);

  // Modal state
  const [viewSetId, setViewSetId] = useState<string | null>(null);
  const [showCreateSetModal, setShowCreateSetModal] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState<{ roleId: string; modelId: string } | null>(null);

  // Fetch instruction files for the current paradigm's set
  const currentSetId = paradigms.find((p) => p.id === activeParadigm)?.instructionSetId || "default";
  const { data: instructionDetail } = useQuery({
    queryKey: ["instruction-set-detail", currentSetId],
    queryFn: () => getInstructionSetDetail(currentSetId),
    enabled: !!activeParadigm,
  });
  const availableFiles = instructionDetail ? Object.keys(instructionDetail.files).sort() : [];

  // Sync API data -> local state on first load
  useEffect(() => {
    if (apiConfigs && paradigms.length === 0) {
      const local = apiConfigs.map(apiToLocal);
      setParadigms(local);
      if (local.length > 0 && !activeParadigm) {
        setActiveParadigm(local[0].id);
      }
    }
  }, [apiConfigs, paradigms.length, activeParadigm]);

  const current = paradigms.find((p) => p.id === activeParadigm);

  // Save all paradigms
  const saveAllMutation = useMutation({
    mutationFn: async () => {
      for (const p of paradigms) {
        await updateParadigmConfig(p.id, {
          name: p.name,
          label: p.label,
          color: p.color,
          description: p.description,
          signals: p.signals,
          active_roles: p.activeRoles,
          active_subprocesses: p.activeSubprocesses,
          role_models: p.roleModels,
          role_instructions: p.roleInstructions,
          instruction_set_id: p.instructionSetId,
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paradigm-configs"] });
      setDirty(false);
    },
  });

  // Updaters
  const updateParadigm = useCallback(
    (id: string, updater: (p: LocalParadigm) => Partial<LocalParadigm>) => {
      setParadigms((prev) =>
        prev.map((p) => (p.id === id ? { ...p, ...updater(p) } : p))
      );
      setDirty(true);
    },
    []
  );

  const setRoleModel = (roleId: string, modelId: string) => {
    updateParadigm(activeParadigm, (p) => ({
      roleModels: { ...p.roleModels, [roleId]: modelId },
    }));
  };

  const setRoleInstruction = (roleId: string, text: string) => {
    updateParadigm(activeParadigm, (p) => ({
      roleInstructions: { ...p.roleInstructions, [roleId]: text },
    }));
  };

  const toggleSubprocess = (subId: string) => {
    updateParadigm(activeParadigm, (p) => ({
      activeSubprocesses: p.activeSubprocesses.includes(subId)
        ? p.activeSubprocesses.filter((s) => s !== subId)
        : [...p.activeSubprocesses, subId],
    }));
  };

  const applyAllModels = (modelId: string) => {
    updateParadigm(activeParadigm, (p) => {
      const newModels = { ...p.roleModels };
      p.activeRoles.forEach((r) => (newModels[r] = modelId));
      p.activeSubprocesses.forEach((r) => (newModels[r] = modelId));
      return { roleModels: newModels };
    });
  };

  const addSignal = () => {
    if (!newSignal.trim()) return;
    updateParadigm(activeParadigm, (p) => ({
      signals: [...p.signals, newSignal.trim()],
    }));
    setNewSignal("");
  };

  const removeSignal = (idx: number) => {
    updateParadigm(activeParadigm, (p) => ({
      signals: p.signals.filter((_, i) => i !== idx),
    }));
  };

  const setInstructionSetId = (setId: string) => {
    updateParadigm(activeParadigm, () => ({ instructionSetId: setId }));
  };

  const configuredCount = current
    ? [...current.activeRoles, ...current.activeSubprocesses].filter(
        (r) => current.roleModels[r]
      ).length
    : 0;
  const totalRoles = current
    ? current.activeRoles.length + current.activeSubprocesses.length
    : 0;

  if (isLoading) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0]">
      {/* Header */}
      <div className="px-6 pt-5 pb-0 border-b border-white/[0.06]">
        <div className="flex items-center justify-between mb-4 max-w-5xl mx-auto">
          <div className="flex items-center gap-3">
            <Link href="/lab" className="text-gray-500 hover:text-gray-300">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-lg font-extrabold tracking-tight text-white">
                  Team Configuration
                </span>
                <span className="text-[9px] px-2 py-0.5 bg-amber-500/15 text-amber-400 rounded font-bold tracking-widest">
                  PARADIGMS
                </span>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Configure models and instructions per paradigm. Team Lead classifies {"\u2192"} loads matching preset.
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => saveAllMutation.mutate()}
              disabled={!dirty || saveAllMutation.isPending}
              className="px-4 py-2 rounded-md text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-40"
              style={{
                background: current ? `${current.color}30` : "rgba(59,130,246,0.19)",
                borderColor: current ? `${current.color}50` : "rgba(59,130,246,0.31)",
                color: current?.color || "#3b82f6",
                borderWidth: 1,
              }}
            >
              {saveAllMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              Save Configuration
            </button>
          </div>
        </div>

        {/* Paradigm tabs */}
        <div className="flex gap-0 overflow-x-auto max-w-5xl mx-auto" style={{ scrollbarWidth: "none" }}>
          {paradigms.map((p) => (
            <button
              key={p.id}
              onClick={() => setActiveParadigm(p.id)}
              className={`px-4 py-2.5 text-xs font-medium whitespace-nowrap tracking-wide transition-colors border-b-2 ${
                activeParadigm === p.id
                  ? "font-bold"
                  : "border-transparent text-gray-500 hover:text-gray-400"
              }`}
              style={
                activeParadigm === p.id
                  ? { background: `${p.color}15`, borderBottomColor: p.color, color: p.color }
                  : undefined
              }
            >
              <span
                className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
                  activeParadigm === p.id ? "opacity-100" : "opacity-40"
                }`}
                style={{ background: p.color }}
              />
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {current && (
        <div className="px-6 py-6 max-w-5xl mx-auto">
          {/* Paradigm header */}
          <div className="flex items-start justify-between mb-5">
            <div>
              <div className="flex items-center gap-2.5 mb-1.5">
                <span
                  className="text-[22px] font-extrabold tracking-tight"
                  style={{ color: current.color }}
                >
                  {current.name}
                </span>
                <span className="text-[10px] px-2.5 py-0.5 bg-white/[0.04] rounded-full text-gray-400">
                  {configuredCount}/{totalRoles} configured
                </span>
              </div>
              <div className="text-[13px] text-gray-400 max-w-lg">{current.description}</div>
            </div>
          </div>

          {/* Instruction Set Selector */}
          {instructionSets && (
            <InstructionSetSelector
              value={current.instructionSetId}
              onChange={setInstructionSetId}
              sets={instructionSets}
              paradigmColor={current.color}
              onView={(id) => setViewSetId(id)}
              onCreate={() => setShowCreateSetModal(true)}
            />
          )}

          {/* Instruction Resolution Preview */}
          <InstructionResolutionPreview
            instructionSetId={current.instructionSetId}
            paradigmId={current.id}
            paradigmColor={current.color}
          />

          {/* Classification signals */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-3.5 mb-4">
            <div className="text-[10px] text-gray-500 font-semibold tracking-widest mb-2">
              CLASSIFICATION SIGNALS — Team Lead uses these to detect this paradigm
            </div>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {current.signals.map((s, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-full"
                  style={{
                    background: `${current.color}12`,
                    color: `${current.color}cc`,
                    border: `1px solid ${current.color}25`,
                  }}
                >
                  {s}
                  <span
                    onClick={() => removeSignal(i)}
                    className="cursor-pointer opacity-50 hover:opacity-100 ml-0.5 text-[9px]"
                  >
                    {"\u00D7"}
                  </span>
                </span>
              ))}
            </div>
            <div className="flex gap-1.5">
              <input
                value={newSignal}
                onChange={(e) => setNewSignal(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addSignal()}
                placeholder="Add signal phrase..."
                className="flex-1 px-2.5 py-1 bg-black/30 border border-white/[0.08] rounded text-gray-300 text-[11px] outline-none focus:border-white/20"
              />
              <button
                onClick={addSignal}
                className="px-2.5 py-1 bg-white/[0.06] border border-white/10 rounded text-gray-400 text-[11px] hover:bg-white/[0.1] transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* Workflow diagram */}
          <WorkflowDiagram paradigm={current} />

          {/* Global model setter */}
          <div className="my-4">
            <GlobalModelSetter onApplyAll={applyAllModels} />
          </div>

          {/* Domain agents */}
          <div className="mb-5">
            <div className="text-[10px] text-gray-500 font-semibold tracking-widest mb-2.5">
              DOMAIN AGENTS
            </div>
            <div className="grid grid-cols-2 gap-2">
              {ROLES.map((role) => (
                <RoleCard
                  key={role.id}
                  role={role}
                  paradigm={current}
                  availableFiles={availableFiles}
                  onModelChange={setRoleModel}
                  onInstructionChange={setRoleInstruction}
                  onOpenSettings={(rId, mId) => setSettingsOpen({ roleId: rId, modelId: mId })}
                />
              ))}
            </div>
          </div>

          {/* Subprocess agents */}
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <div className="text-[10px] text-gray-500 font-semibold tracking-widest">
                SUBPROCESS AGENTS
              </div>
              <button
                onClick={() => setShowSubprocesses(!showSubprocesses)}
                className="text-[10px] text-gray-500 hover:text-gray-300"
              >
                {showSubprocesses ? "Collapse" : "Expand"}
              </button>
            </div>
            {showSubprocesses && (
              <div className="grid grid-cols-2 gap-2">
                {SUBPROCESS_ROLES.map((role) => {
                  const isActive = current.activeSubprocesses.includes(role.id);
                  return (
                    <div key={role.id}>
                      <div className="flex items-center gap-1.5 mb-1">
                        <button
                          onClick={() => toggleSubprocess(role.id)}
                          className="w-4 h-4 rounded flex items-center justify-center text-[10px]"
                          style={{
                            border: `1px solid ${isActive ? current.color : "rgba(255,255,255,0.15)"}`,
                            background: isActive ? `${current.color}30` : "transparent",
                            color: current.color,
                          }}
                        >
                          {isActive ? "\u2713" : ""}
                        </button>
                        <span className={`text-[10px] ${isActive ? "text-gray-400" : "text-gray-600"}`}>
                          Toggle {role.name}
                        </span>
                      </div>
                      <RoleCard
                        role={role}
                        paradigm={current}
                        availableFiles={availableFiles}
                        onModelChange={setRoleModel}
                        onInstructionChange={setRoleInstruction}
                        onOpenSettings={(rId, mId) => setSettingsOpen({ roleId: rId, modelId: mId })}
                        isSubprocess
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Cost estimate */}
          <div className="mt-5 p-3.5 bg-white/[0.02] border border-white/[0.06] rounded-lg flex justify-between items-center">
            <div>
              <div className="text-[10px] text-gray-500 font-semibold tracking-widest">
                EST. COST PER QUESTION
              </div>
              <div className="text-[11px] text-gray-600 mt-0.5">
                Based on {current.activeRoles.length} domains + {current.activeSubprocesses.length} subprocesses
              </div>
            </div>
            <div className="text-right">
              <div
                className="text-xl font-bold"
                style={{ color: current.color }}
              >
                ${(1.5 + current.activeSubprocesses.length * 0.15).toFixed(2)}
              </div>
              <div className="text-[10px] text-gray-600">
                {"\u00D7"}200q = ${((1.5 + current.activeSubprocesses.length * 0.15) * 200).toFixed(0)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Unsaved indicator */}
      {dirty && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-yellow-500/20 border border-yellow-500/40 text-yellow-300 px-4 py-2 rounded-full text-sm flex items-center gap-2 z-40">
          <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
          Unsaved changes
        </div>
      )}

      {/* View/Edit Instruction Set Modal */}
      {viewSetId && (
        <InstructionSetModal
          setId={viewSetId}
          onClose={() => setViewSetId(null)}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ["instruction-sets"] });
            queryClient.invalidateQueries({ queryKey: ["instruction-set-detail", viewSetId] });
          }}
        />
      )}

      {/* Create Instruction Set Modal */}
      {showCreateSetModal && instructionSets && (
        <CreateSetModal
          existingSets={instructionSets}
          onClose={() => setShowCreateSetModal(false)}
          onCreated={(id) => {
            queryClient.invalidateQueries({ queryKey: ["instruction-sets"] });
            setShowCreateSetModal(false);
            if (current) {
              setInstructionSetId(id);
            }
          }}
        />
      )}

      {/* Model Settings Panel */}
      {settingsOpen && current && (
        <ModelSettingsPanel
          modelId={settingsOpen.modelId}
          roleId={settingsOpen.roleId}
          paradigmId={current.id}
          paradigmColor={current.color}
          onClose={() => setSettingsOpen(null)}
          onSaved={() => setSettingsOpen(null)}
        />
      )}
    </main>
  );
}
