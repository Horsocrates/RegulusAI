"use client";

import { useState, useEffect, useMemo } from "react";
import {
  FlaskConical, ArrowLeft, ArrowRight, Check, Loader2,
  Rocket, Database, Target, Cpu, FileCheck,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getLabRuns, getBenchmarks, getBenchmarkDomains, createTestConfig,
  startTestRun, executeTestRun, listTeams,
  getBenchmarkIndexStatus, indexBenchmark, getBenchmarkDomainStats,
  type LabRun, type BenchmarkSummary, type BenchmarkDomain, type TeamResponse,
  type BenchmarkIndexStatus, type DomainStatsDetail,
  formatCost,
} from "@/lib/lab-api";

// === Types ===

interface DomainSelection {
  domain: string;
  available: number;
  take: number | "all";
}

interface WizardState {
  step: 1 | 2 | 3 | 4;
  dataset: string | null;
  datasetInfo: BenchmarkSummary | null;
  totalQuestions: number;
  category: string | null;
  selectedDomains: string[];
  domainSelections: DomainSelection[];
  shuffle: boolean;
  retryFromRunId: number | null;
  concurrency: number;
  stepMode: "continuous" | "stepped";
  questionsPerAgent: number;
  provider: "claude" | "openai";
  modelVersion: string;
  name: string;
  mode: "v1" | "v2";
  reasoningModel: string;
  teamId: string | null;
  questionFilter: "all" | "new" | "failed";
}

const INITIAL_STATE: WizardState = {
  step: 1,
  dataset: null,
  datasetInfo: null,
  totalQuestions: 50,
  category: null,
  selectedDomains: [],
  domainSelections: [],
  shuffle: true,
  retryFromRunId: null,
  concurrency: 5,
  stepMode: "continuous",
  questionsPerAgent: 10,
  provider: "claude",
  modelVersion: "v1.0a",
  name: "",
  mode: "v1",
  reasoningModel: "deepseek",
  teamId: null,
  questionFilter: "all",
};

const COST_PER_Q: Record<string, number> = {
  claude: 0.024,
  openai: 0.020,
};

const TIME_PER_Q = 105; // seconds per question (average)


// Fallback benchmarks when API is unavailable
const FALLBACK_BENCHMARKS: BenchmarkSummary[] = [
  {
    id: "bbeh",
    name: "BBEH (Big-Bench Extra Hard)",
    description: "Complex reasoning benchmark by Google DeepMind",
    source: "https://github.com/google-deepmind/bbeh",
    total_examples: 460,
    domains_count: 23,
    version: "1.0",
  },
  {
    id: "simpleqa",
    name: "SimpleQA",
    description: "Factual question answering benchmark by OpenAI",
    source: "https://openaipublic.blob.core.windows.net",
    total_examples: 4326,
    domains_count: 20,
    version: "1.0",
  },
];

// === Helpers ===

function computeWillUse(domainSelections: DomainSelection[]): number {
  return domainSelections.reduce((sum, ds) => {
    return sum + (ds.take === "all" ? ds.available : Math.min(ds.take, ds.available));
  }, 0);
}

function computeAvailableInSelection(domainSelections: DomainSelection[]): number {
  return domainSelections.reduce((sum, ds) => sum + ds.available, 0);
}

// === Step Indicator ===

function StepIndicator({ current, steps }: { current: number; steps: { label: string; icon: React.ElementType }[] }) {
  return (
    <div className="space-y-2">
      {steps.map((s, i) => {
        const stepNum = i + 1;
        const isActive = stepNum === current;
        const isPast = stepNum < current;
        const Icon = s.icon;
        return (
          <div key={i} className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
            isActive ? "bg-green-500/10 text-green-400" : isPast ? "text-green-400/70" : "text-gray-600"
          }`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
              isActive ? "border-green-400 bg-green-400/20" :
              isPast ? "border-green-400/50 bg-green-400/10" :
              "border-gray-700"
            }`}>
              {isPast ? <Check className="w-3.5 h-3.5" /> : stepNum}
            </div>
            <span className={`text-sm font-medium ${isActive ? "text-green-400" : ""}`}>{s.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// === Step 1: Dataset Selection ===

function DatasetSelector({ benchmarks, selected, onSelect }: {
  benchmarks: BenchmarkSummary[];
  selected: string | null;
  onSelect: (b: BenchmarkSummary) => void;
}) {
  const selectedBm = benchmarks.find((b) => b.id === selected);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white mb-1">Select Benchmark</h2>
      <p className="text-gray-500 mb-4">Choose a benchmark for testing:</p>

      <select
        value={selected || ""}
        onChange={(e) => {
          const b = benchmarks.find((d) => d.id === e.target.value);
          if (b) onSelect(b);
        }}
        className="w-full px-4 py-3 bg-[#12121a] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none appearance-none cursor-pointer"
      >
        <option value="" disabled>Select a benchmark...</option>
        {benchmarks.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name} — {b.total_examples.toLocaleString()} questions
          </option>
        ))}
      </select>

      {/* Info card for selected benchmark */}
      {selectedBm && (
        <div className="p-4 bg-[#12121a] border border-green-400/30 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <Database className="w-4 h-4 text-green-400" />
            <span className="font-medium text-white">{selectedBm.name}</span>
            <span className="text-xs px-2 py-0.5 bg-[#1a1a2e] rounded text-gray-400">v{selectedBm.version}</span>
          </div>
          <p className="text-sm text-gray-400 mb-2">{selectedBm.description}</p>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{selectedBm.total_examples.toLocaleString()} questions</span>
            <span>{selectedBm.domains_count} domains</span>
          </div>
        </div>
      )}
    </div>
  );
}

// === Step 2: Scope ===

function DomainRow({
  ds,
  onToggle,
  onChangeTake,
}: {
  ds: DomainSelection & { selected: boolean };
  onToggle: () => void;
  onChangeTake: (take: number | "all") => void;
}) {
  const PRESETS = [1, 2, 3, 5, 10, 20];

  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
      ds.selected ? "bg-green-500/5" : "opacity-60"
    }`}>
      <input
        type="checkbox"
        checked={ds.selected}
        onChange={onToggle}
        className="rounded border-gray-600 text-green-500 focus:ring-green-500 focus:ring-offset-0 bg-transparent"
      />
      <span className={`flex-1 text-sm ${ds.selected ? "text-gray-200" : "text-gray-500"}`}>
        {ds.domain.replace(/_/g, " ")}
      </span>
      <span className="text-xs text-gray-500 w-24 text-right">{ds.available} questions</span>
      <div className="w-24">
        {ds.selected ? (
          <select
            value={ds.take === "all" ? "all" : String(ds.take)}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "all") onChangeTake("all");
              else onChangeTake(parseInt(v, 10));
            }}
            className="w-full px-2 py-1 bg-[#1a1a2e] border border-[#2a2a3e] rounded text-xs text-white focus:outline-none focus:border-green-400 cursor-pointer"
          >
            <option value="all">all</option>
            {PRESETS.filter((p) => p < ds.available).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        ) : (
          <span className="text-xs text-gray-600 px-2">---</span>
        )}
      </div>
    </div>
  );
}

function QuestionCountPicker({ value, max, onChange }: {
  value: number;
  max: number;
  onChange: (n: number) => void;
}) {
  const [customText, setCustomText] = useState("");
  const PRESETS = [1, 2, 3, 5, 10, 20];

  const handlePreset = (n: number) => {
    onChange(n);
  };

  const handleCustomOk = () => {
    const raw = customText.trim();
    if (!raw) return;
    const n = parseInt(raw, 10);
    if (isNaN(n) || n < 1) return;
    onChange(Math.min(n, max));
    setCustomText("");
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-green-400 font-medium bg-green-400/10 px-3 py-1 rounded-lg">
          Selected: {value.toLocaleString()} questions
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.filter((n) => n <= max).map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => handlePreset(n)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              value === n
                ? "bg-green-500 text-white"
                : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
            }`}
          >
            {n}
          </button>
        ))}
        <button
          type="button"
          onClick={() => handlePreset(max)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            value === max
              ? "bg-green-500 text-white"
              : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
          }`}
        >
          All ({max.toLocaleString()})
        </button>

        <span className="text-gray-600 mx-1">|</span>

        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          placeholder="Custom"
          value={customText}
          onChange={(e) => setCustomText(e.target.value.replace(/[^0-9]/g, ""))}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleCustomOk(); } }}
          className="w-20 px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:outline-none focus:border-green-400"
        />
        <button
          type="button"
          onClick={handleCustomOk}
          className="px-3 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm font-medium flex items-center gap-1.5 transition-colors"
        >
          <Check className="w-3.5 h-3.5" />
          OK
        </button>
      </div>
    </div>
  );
}

function ScopeConfig({ state, onChange, maxQuestions, categories, completedRuns, domains, indexStatus, domainStats }: {
  state: WizardState;
  onChange: (patch: Partial<WizardState>) => void;
  maxQuestions: number;
  categories: string[];
  completedRuns: LabRun[];
  domains: BenchmarkDomain[];
  indexStatus?: BenchmarkIndexStatus | null;
  domainStats?: DomainStatsDetail[] | null;
}) {
  // Build domain selections from available domains, preserving existing state
  const fallbackPerDomain = domains.length > 0 ? Math.max(1, Math.floor(maxQuestions / domains.length)) : 1;

  // Build a stats lookup for filtered counts
  const statsMap = useMemo(() => {
    const m = new Map<string, DomainStatsDetail>();
    if (domainStats) {
      for (const s of domainStats) m.set(s.domain, s);
    }
    return m;
  }, [domainStats]);

  const domainRows = useMemo(() => {
    return domains.map((d) => {
      const existing = state.domainSelections.find((ds) => ds.domain === d.name);
      const selected = state.selectedDomains.includes(d.name);
      const totalAvailable = d.example_count > 0 ? d.example_count : fallbackPerDomain;

      // Apply filter to available count
      let available = totalAvailable;
      const stats = statsMap.get(d.name);
      if (stats && state.questionFilter === "new") {
        available = stats.new_count;
      } else if (stats && state.questionFilter === "failed") {
        available = stats.failed_count;
      }

      return {
        domain: d.name,
        available,
        take: existing?.take ?? ("all" as number | "all"),
        selected,
      };
    });
  }, [domains, state.selectedDomains, state.domainSelections, fallbackPerDomain, state.questionFilter, statsMap]);

  const selectedRows = domainRows.filter((r) => r.selected);
  const availableInSelection = computeAvailableInSelection(selectedRows);
  const willUse = computeWillUse(selectedRows);

  // Build domain_limits breakdown string
  const breakdownParts = selectedRows.map((r) => {
    const count = r.take === "all" ? r.available : Math.min(r.take as number, r.available);
    return count;
  });
  const breakdownStr = breakdownParts.length > 0 && breakdownParts.length <= 8
    ? ` (${breakdownParts.join(" + ")})`
    : "";

  const domainAvailable = (d: BenchmarkDomain) => {
    const total = d.example_count > 0 ? d.example_count : fallbackPerDomain;
    const stats = statsMap.get(d.name);
    if (stats && state.questionFilter === "new") return stats.new_count;
    if (stats && state.questionFilter === "failed") return stats.failed_count;
    return total;
  };

  const handleToggleDomain = (domainName: string) => {
    const isSelected = state.selectedDomains.includes(domainName);
    const nextSelected = isSelected
      ? state.selectedDomains.filter((x) => x !== domainName)
      : [...state.selectedDomains, domainName];

    // Update domainSelections to add entry for newly selected
    if (!isSelected) {
      const d = domains.find((dd) => dd.name === domainName);
      const exists = state.domainSelections.find((ds) => ds.domain === domainName);
      if (!exists && d) {
        onChange({
          selectedDomains: nextSelected,
          domainSelections: [...state.domainSelections, { domain: domainName, available: domainAvailable(d), take: "all" }],
        });
        return;
      }
    }
    onChange({ selectedDomains: nextSelected });
  };

  const handleChangeTake = (domainName: string, take: number | "all") => {
    const next = state.domainSelections.map((ds) =>
      ds.domain === domainName ? { ...ds, take } : ds
    );
    // If not in domainSelections yet, add it
    if (!next.find((ds) => ds.domain === domainName)) {
      const d = domains.find((dd) => dd.name === domainName);
      if (d) next.push({ domain: domainName, available: domainAvailable(d), take });
    }
    onChange({ domainSelections: next });
  };

  const handleSelectAll = () => {
    const allNames = domains.map((d) => d.name);
    const allSelections = domains.map((d) => {
      const existing = state.domainSelections.find((ds) => ds.domain === d.name);
      return { domain: d.name, available: domainAvailable(d), take: existing?.take ?? ("all" as number | "all") };
    });
    onChange({ selectedDomains: allNames, domainSelections: allSelections });
  };

  const handleClearAll = () => {
    onChange({ selectedDomains: [], domainSelections: [] });
  };

  // Sync totalQuestions with willUse when domains are selected
  const effectiveQuestions = state.selectedDomains.length > 0 ? willUse : state.totalQuestions;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-1">Scope Selection</h2>

      {state.datasetInfo && (
        <p className="text-sm text-gray-500">
          Benchmark: {state.datasetInfo.name} ({state.datasetInfo.total_examples.toLocaleString()} total questions)
        </p>
      )}

      {/* Question filter */}
      {domains.length > 1 && indexStatus?.status === "ready" && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 mr-1">Filter:</span>
          {(["all", "new", "failed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => onChange({ questionFilter: f, domainSelections: [], selectedDomains: [] })}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                state.questionFilter === f
                  ? f === "new" ? "bg-blue-500/20 text-blue-400 border border-blue-400/40"
                    : f === "failed" ? "bg-red-500/20 text-red-400 border border-red-400/40"
                    : "bg-green-500/20 text-green-400 border border-green-400/40"
                  : "bg-[#1a1a2e] text-gray-400 border border-transparent hover:border-[#2a2a3e]"
              }`}
            >
              {f === "all" ? "All" : f === "new" ? "New (untested)" : "Failed only"}
            </button>
          ))}
        </div>
      )}

      {/* Domain selection */}
      {domains.length > 1 && (
        <div>
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1e1e2e] bg-[#0e0e16]">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSelectAll}
                  className="text-xs text-green-400 hover:text-green-300 transition-colors"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={handleClearAll}
                  className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                  Clear All
                </button>
              </div>
              {state.selectedDomains.length > 0 && (
                <span className="text-xs text-green-400 font-medium">
                  Selected: {willUse.toLocaleString()} questions
                </span>
              )}
            </div>

            {/* Domain list */}
            <div className="max-h-[320px] overflow-y-auto divide-y divide-[#1e1e2e]/50">
              {domainRows.map((dr) => (
                <DomainRow
                  key={dr.domain}
                  ds={dr}
                  onToggle={() => handleToggleDomain(dr.domain)}
                  onChangeTake={(take) => handleChangeTake(dr.domain, take)}
                />
              ))}
            </div>
          </div>

          {/* Summary box */}
          {state.selectedDomains.length > 0 && (
            <div className="mt-3 bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 space-y-2">
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Summary</div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Domains selected</span>
                <span className="text-white">{state.selectedDomains.length} of {domains.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Available in selection</span>
                <span className="text-white">{availableInSelection.toLocaleString()} questions</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Will use</span>
                <span className="text-green-400 font-medium">
                  {willUse.toLocaleString()} questions{breakdownStr}
                </span>
              </div>
              <div className="pt-2 border-t border-[#1e1e2e] flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={state.shuffle}
                    onChange={(e) => onChange({ shuffle: e.target.checked })}
                    className="rounded border-gray-600 text-green-500 focus:ring-green-500 focus:ring-offset-0 bg-transparent"
                  />
                  Shuffle questions
                </label>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Question count (only when NO domains selected — fallback to flat count) */}
      {state.selectedDomains.length === 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Questions {domains.length > 1 && <span className="text-gray-600 font-normal">(all domains)</span>}
          </label>
          {state.retryFromRunId !== null ? (
            <div className="px-4 py-3 bg-[#12121a] border border-[#1e1e2e] rounded-lg">
              <span className="text-white font-medium">{state.totalQuestions}</span>
              <span className="text-gray-500 ml-2">failed questions from Run #{state.retryFromRunId}</span>
            </div>
          ) : (
            <QuestionCountPicker
              value={state.totalQuestions}
              max={maxQuestions}
              onChange={(n) => onChange({ totalQuestions: n })}
            />
          )}

          {/* Shuffle toggle when no domains selected */}
          <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer mt-3">
            <input
              type="checkbox"
              checked={state.shuffle}
              onChange={(e) => onChange({ shuffle: e.target.checked })}
              className="rounded border-gray-600 text-green-500 focus:ring-green-500 focus:ring-offset-0 bg-transparent"
            />
            Shuffle questions
          </label>
        </div>
      )}

      {/* Category filter */}
      {categories.length > 1 && (
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Category</label>
          <select
            value={state.category || ""}
            onChange={(e) => onChange({ category: e.target.value || null })}
            className="w-full px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none"
          >
            <option value="">All categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
      )}

      {/* Retry from run */}
      {completedRuns.length > 0 && state.selectedDomains.length === 0 && (
        <div>
          <label className="flex items-center gap-2 text-sm text-gray-400 mb-2">
            <input
              type="checkbox"
              checked={state.retryFromRunId !== null}
              onChange={(e) => {
                if (e.target.checked) {
                  const run = completedRuns[0];
                  const failedCount = run.completed_questions - run.correct_count;
                  onChange({ retryFromRunId: run.id, totalQuestions: Math.max(1, failedCount) });
                } else {
                  onChange({ retryFromRunId: null, totalQuestions: maxQuestions > 50 ? 50 : maxQuestions });
                }
              }}
              className="rounded border-gray-600"
            />
            Only failed from previous run
          </label>
          {state.retryFromRunId !== null && (
            <select
              value={state.retryFromRunId ?? ""}
              onChange={(e) => {
                const runId = Number(e.target.value);
                const run = completedRuns.find((r) => r.id === runId);
                const failedCount = run ? run.completed_questions - run.correct_count : 0;
                onChange({ retryFromRunId: runId || null, totalQuestions: Math.max(1, failedCount) });
              }}
              className="w-full px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none"
            >
              {completedRuns.map((r) => {
                const failedCount = r.completed_questions - r.correct_count;
                return (
                  <option key={r.id} value={r.id}>
                    Run #{r.id}: {r.name} ({failedCount} failed)
                  </option>
                );
              })}
            </select>
          )}
        </div>
      )}
    </div>
  );
}

// === Step 3: Execution ===

function ExecutionConfig({ state, onChange, teams, domains }: {
  state: WizardState;
  onChange: (patch: Partial<WizardState>) => void;
  teams: TeamResponse[];
  domains: BenchmarkDomain[];
}) {
  const AGENT_PRESETS = [1, 3, 5, 10];

  // Compute effective question count from domain selections
  const effectiveQuestions = useMemo(() => {
    if (state.selectedDomains.length > 0) {
      const selectedRows = state.domainSelections.filter(
        (ds) => state.selectedDomains.includes(ds.domain)
      );
      return computeWillUse(selectedRows);
    }
    return state.totalQuestions;
  }, [state.selectedDomains, state.domainSelections, state.totalQuestions]);

  const numSteps = state.stepMode === "continuous"
    ? 1
    : Math.max(1, Math.ceil(effectiveQuestions / (state.questionsPerAgent * state.concurrency)));

  const timeEstimate = (effectiveQuestions * TIME_PER_Q) / Math.max(1, state.concurrency);
  const formatEta = (secs: number) => {
    if (secs < 60) return `~${Math.round(secs)}s`;
    if (secs < 3600) return `~${Math.round(secs / 60)}min`;
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return `~${h}h ${m}m`;
  };

  const selectedTeam = teams.find((t) => t.id === state.teamId);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-1">Execution</h2>

      {/* Team selection */}
      {teams.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Team</label>
          <select
            value={state.teamId || ""}
            onChange={(e) => onChange({ teamId: e.target.value || null })}
            className="w-full px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none"
          >
            <option value="">Default team</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}{t.is_default ? " (default)" : ""} — {t.team_lead_config.model}
              </option>
            ))}
          </select>
          {selectedTeam && (
            <div className="mt-2 text-xs text-gray-500 flex items-center gap-3">
              <span>Lead: {selectedTeam.team_lead_config.model}</span>
              <span>{Object.keys(selectedTeam.agent_configs).length} agents</span>
            </div>
          )}
        </div>
      )}

      {/* Parallel agents */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Parallel agents</label>
        <div className="flex gap-2">
          {AGENT_PRESETS.map((n) => (
            <button
              key={n}
              onClick={() => onChange({ concurrency: n })}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                state.concurrency === n
                  ? "bg-green-500 text-white"
                  : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Step mode */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Step mode</label>
        <div className="space-y-3">
          <label className="flex items-start gap-3 p-3 rounded-lg bg-[#12121a] border border-[#1e1e2e] cursor-pointer hover:border-green-400/30">
            <input
              type="radio"
              checked={state.stepMode === "continuous"}
              onChange={() => onChange({ stepMode: "continuous" })}
              className="mt-0.5"
            />
            <div>
              <div className="text-white text-sm font-medium">Continuous</div>
              <div className="text-gray-500 text-xs">Run all questions in 1 step without pausing</div>
            </div>
          </label>
          <label className="flex items-start gap-3 p-3 rounded-lg bg-[#12121a] border border-[#1e1e2e] cursor-pointer hover:border-green-400/30">
            <input
              type="radio"
              checked={state.stepMode === "stepped"}
              onChange={() => onChange({ stepMode: "stepped" })}
              className="mt-0.5"
            />
            <div className="flex-1">
              <div className="text-white text-sm font-medium">Stepped</div>
              <div className="text-gray-500 text-xs mb-2">Pause after each batch for review</div>
              {state.stepMode === "stepped" && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 text-xs">Questions per agent:</span>
                  <input
                    type="number"
                    min={1}
                    max={effectiveQuestions}
                    value={state.questionsPerAgent}
                    onChange={(e) => onChange({ questionsPerAgent: Math.max(1, Number(e.target.value) || 1) })}
                    className="w-20 px-2 py-1 bg-[#1a1a2e] border border-[#1e1e2e] rounded text-white text-sm focus:border-green-400 focus:outline-none"
                  />
                </div>
              )}
            </div>
          </label>
        </div>
      </div>

      {/* Provider */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Provider</label>
        <div className="flex gap-2">
          <button
            onClick={() => onChange({ provider: "claude" })}
            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              state.provider === "claude"
                ? "bg-green-500 text-white"
                : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
            }`}
          >
            Claude
          </button>
          <button
            onClick={() => onChange({ provider: "openai" })}
            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              state.provider === "openai"
                ? "bg-green-500 text-white"
                : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
            }`}
          >
            OpenAI
          </button>
        </div>
      </div>

      {/* Pipeline Mode */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Pipeline mode</label>
        <div className="flex gap-2">
          <button
            onClick={() => onChange({ mode: "v1" })}
            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              state.mode === "v1"
                ? "bg-green-500 text-white"
                : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
            }`}
          >
            v1 Socratic
          </button>
          <button
            onClick={() => onChange({ mode: "v2" })}
            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              state.mode === "v2"
                ? "bg-purple-500 text-white"
                : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
            }`}
          >
            v2 Audit
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {state.mode === "v1"
            ? "Generate reasoning D1-D6 step by step (6+ LLM calls)"
            : "Reasoning model thinks, then Regulus audits the trace (2 LLM calls)"}
        </p>
      </div>

      {/* Reasoning Model (v2 only) */}
      {state.mode === "v2" && (
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Reasoning model</label>
          <div className="space-y-2">
            {[
              { value: "deepseek", label: "DeepSeek-R1", desc: "Full chain-of-thought trace" },
              { value: "claude-thinking", label: "Claude Extended Thinking", desc: "Summary trace" },
              { value: "openai-reasoning", label: "OpenAI (Stub)", desc: "No trace (answer-only audit)" },
            ].map((m) => (
              <label
                key={m.value}
                className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                  state.reasoningModel === m.value
                    ? "bg-purple-500/10 border border-purple-400/40"
                    : "bg-[#12121a] border border-[#1e1e2e] hover:border-purple-400/20"
                }`}
              >
                <input
                  type="radio"
                  checked={state.reasoningModel === m.value}
                  onChange={() => onChange({ reasoningModel: m.value })}
                  className="mt-0.5"
                />
                <div>
                  <div className="text-white text-sm font-medium">{m.label}</div>
                  <div className="text-gray-500 text-xs">{m.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Model version */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Model version label</label>
        <input
          type="text"
          value={state.modelVersion}
          onChange={(e) => onChange({ modelVersion: e.target.value })}
          placeholder="e.g. v1.0a"
          className="w-full px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none"
        />
      </div>

      {/* Summary */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Questions</span>
          <span className="text-white">{effectiveQuestions.toLocaleString()}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Agents</span>
          <span className="text-white">{state.concurrency} parallel</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Total steps</span>
          <span className="text-green-400 font-medium">{numSteps}</span>
        </div>
        {state.stepMode === "stepped" && (
          <>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Questions per agent</span>
              <span className="text-white">{state.questionsPerAgent}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Questions per step</span>
              <span className="text-white">{state.questionsPerAgent * state.concurrency}</span>
            </div>
          </>
        )}
        <div className="flex justify-between text-sm border-t border-[#1e1e2e] pt-2">
          <span className="text-gray-500">Est. time</span>
          <span className="text-green-400 font-medium">{formatEta(timeEstimate)}</span>
        </div>
      </div>
    </div>
  );
}

// === Step 4: Review ===

function ReviewPanel({ state, onNameChange, submitting, teams, domains }: {
  state: WizardState;
  onNameChange: (name: string) => void;
  submitting: boolean;
  teams: TeamResponse[];
  domains: BenchmarkDomain[];
}) {
  const effectiveQuestions = useMemo(() => {
    if (state.selectedDomains.length > 0) {
      const selectedRows = state.domainSelections.filter(
        (ds) => state.selectedDomains.includes(ds.domain)
      );
      return computeWillUse(selectedRows);
    }
    return state.totalQuestions;
  }, [state.selectedDomains, state.domainSelections, state.totalQuestions]);

  const numSteps = state.stepMode === "continuous"
    ? 1
    : Math.max(1, Math.ceil(effectiveQuestions / (state.questionsPerAgent * state.concurrency)));

  const costEstimate = effectiveQuestions * (COST_PER_Q[state.provider] || 0.024);
  const timeEstimate = (effectiveQuestions * TIME_PER_Q) / Math.max(1, state.concurrency);

  const formatEta = (secs: number) => {
    if (secs < 60) return `~${Math.round(secs)}s`;
    if (secs < 3600) return `~${Math.round(secs / 60)} minutes`;
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return `~${h}h ${m}m`;
  };

  // Build domain detail string
  const domainDetail = useMemo(() => {
    if (state.selectedDomains.length === 0) return null;
    const parts = state.selectedDomains.map((d) => {
      const ds = state.domainSelections.find((s) => s.domain === d);
      if (!ds) return d.replace(/_/g, " ");
      const take = ds.take === "all" ? ds.available : Math.min(ds.take as number, ds.available);
      return `${d.replace(/_/g, " ")} (${take})`;
    });
    return parts.join(", ");
  }, [state.selectedDomains, state.domainSelections]);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-1">Review & Launch</h2>

      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 space-y-3">
        <Row label="Dataset" value={state.datasetInfo?.name || state.dataset || ""} />
        <Row label="Questions" value={effectiveQuestions.toLocaleString()} />
        {state.selectedDomains.length > 0 && (
          <>
            <Row label="Domains" value={`${state.selectedDomains.length} selected`} />
            {domainDetail && (
              <div className="text-xs text-gray-500 pl-2 -mt-1 break-words">{domainDetail}</div>
            )}
          </>
        )}
        {state.shuffle && <Row label="Shuffle" value="Yes" />}
        {state.category && <Row label="Category" value={state.category} />}
        {state.teamId && (
          <Row label="Team" value={teams.find((t) => t.id === state.teamId)?.name || state.teamId.slice(0, 8)} />
        )}
        <Row label="Agents" value={`${state.concurrency} parallel`} />
        <Row label="Steps" value={state.stepMode === "continuous" ? "1 (continuous)" : `${numSteps} (${state.questionsPerAgent * state.concurrency} questions/step = ${state.questionsPerAgent}/agent × ${state.concurrency} agents)`} />
        <Row label="Provider" value={state.provider === "claude" ? "Claude" : "OpenAI"} />
        <Row label="Pipeline" value={state.mode === "v1" ? "v1 Socratic (6+ LLM calls)" : "v2 Audit (2 LLM calls)"} />
        {state.mode === "v2" && <Row label="Reasoning model" value={state.reasoningModel} />}
        {state.modelVersion && <Row label="Version" value={state.modelVersion} />}
        {state.retryFromRunId && <Row label="Retry from" value={`Run #${state.retryFromRunId}`} />}

        <div className="border-t border-[#1e1e2e] pt-3 mt-3 space-y-2">
          <Row label="Estimated cost" value={formatCost(costEstimate)} highlight />
          <Row label="Estimated time" value={formatEta(timeEstimate)} highlight />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Test name</label>
        <input
          type="text"
          value={state.name}
          onChange={(e) => onNameChange(e.target.value)}
          className="w-full px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none"
        />
      </div>

      {submitting && (
        <div className="flex items-center gap-2 text-blue-400 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" />
          Creating test...
        </div>
      )}
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className={highlight ? "text-green-400 font-medium" : "text-white"}>{value}</span>
    </div>
  );
}

// === Main Wizard ===

const STEPS = [
  { label: "Dataset", icon: Database },
  { label: "Scope", icon: Target },
  { label: "Execution", icon: Cpu },
  { label: "Review", icon: FileCheck },
];

export default function CreateTestPage() {
  const router = useRouter();
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onChange = (patch: Partial<WizardState>) => {
    setState((s) => ({ ...s, ...patch }));
  };

  // Fetch benchmarks (with fallback)
  const { data: benchmarksData, isLoading: loadingDatasets } = useQuery({
    queryKey: ["lab-benchmarks"],
    queryFn: getBenchmarks,
  });
  const benchmarks = benchmarksData?.length ? benchmarksData : FALLBACK_BENCHMARKS;

  // Fetch teams for team picker
  const { data: teamsData } = useQuery({
    queryKey: ["lab-teams"],
    queryFn: listTeams,
  });
  const teams = teamsData ?? [];

  // Fetch index status for selected benchmark
  const { data: indexStatusData, refetch: refetchIndex } = useQuery({
    queryKey: ["benchmark-index-status", state.dataset],
    queryFn: () => getBenchmarkIndexStatus(state.dataset!),
    enabled: !!state.dataset,
  });
  const [indexing, setIndexing] = useState(false);

  // Auto-trigger indexing when benchmark selected and not yet indexed
  useEffect(() => {
    if (
      state.dataset &&
      indexStatusData &&
      indexStatusData.status !== "ready" &&
      indexStatusData.status !== "indexing" &&
      !indexing
    ) {
      setIndexing(true);
      indexBenchmark(state.dataset)
        .then(() => { refetchIndex(); setIndexing(false); })
        .catch(() => { setIndexing(false); });
    }
  }, [state.dataset, indexStatusData]);

  // Fetch domains for selected benchmark
  const { data: domainsData } = useQuery({
    queryKey: ["lab-benchmark-domains", state.dataset],
    queryFn: () => getBenchmarkDomains(state.dataset!),
    enabled: !!state.dataset && (indexStatusData?.status === "ready" || !indexStatusData),
  });
  const benchmarkDomains = domainsData ?? [];

  // Fetch domain stats (attempted/correct/new/failed counts)
  const { data: domainStatsData } = useQuery({
    queryKey: ["lab-benchmark-domain-stats", state.dataset],
    queryFn: () => getBenchmarkDomainStats(state.dataset!),
    enabled: !!state.dataset && indexStatusData?.status === "ready",
  });

  // Fetch completed runs for retry picker
  const { data: runsData } = useQuery({
    queryKey: ["lab-runs"],
    queryFn: getLabRuns,
  });
  const completedRuns = (runsData ?? []).filter(
    (r) => ["completed", "paused", "stopped"].includes(r.status) &&
           r.completed_questions > 0 &&
           (!state.dataset || r.dataset === state.dataset)
  );

  // Compute effective questions for name generation
  const effectiveQuestions = useMemo(() => {
    if (state.selectedDomains.length > 0) {
      const selectedRows = state.domainSelections.filter(
        (ds) => state.selectedDomains.includes(ds.domain)
      );
      return computeWillUse(selectedRows);
    }
    return state.totalQuestions;
  }, [state.selectedDomains, state.domainSelections, state.totalQuestions]);

  // Auto-generate name when entering step 4
  useEffect(() => {
    if (state.step === 4 && !state.name) {
      const ds = state.datasetInfo?.name || state.dataset || "Test";
      const ver = state.modelVersion ? ` ${state.modelVersion}` : "";
      onChange({ name: `${ds} ${effectiveQuestions}q${ver}` });
    }
  }, [state.step]);

  // Navigation
  const canNext = () => {
    switch (state.step) {
      case 1: return state.dataset !== null;
      case 2: return state.selectedDomains.length > 0 || state.totalQuestions > 0;
      case 3: return true;
      case 4: return state.name.trim().length > 0 && !submitting;
      default: return false;
    }
  };

  const goNext = () => {
    if (state.step < 4) onChange({ step: (state.step + 1) as 1 | 2 | 3 | 4 });
  };
  const goBack = () => {
    if (state.step > 1) onChange({ step: (state.step - 1) as 1 | 2 | 3 | 4 });
  };

  const handleLaunch = async () => {
    setError(null);
    setSubmitting(true);

    try {
      const numSteps = state.stepMode === "continuous"
        ? 1
        : Math.max(1, Math.ceil(effectiveQuestions / (state.questionsPerAgent * state.concurrency)));

      // Build domain_limits from domainSelections
      const domainLimits: Record<string, number> = {};
      if (state.selectedDomains.length > 0) {
        for (const ds of state.domainSelections) {
          if (state.selectedDomains.includes(ds.domain) && ds.take !== "all") {
            domainLimits[ds.domain] = ds.take as number;
          }
        }
      }

      // Step 1: Create test config
      const config = await createTestConfig({
        name: state.name.trim(),
        benchmark: state.dataset!,
        domains: state.selectedDomains.length > 0 ? state.selectedDomains : undefined,
        domain_limits: Object.keys(domainLimits).length > 0 ? domainLimits : undefined,
        question_count: state.selectedDomains.length > 0 ? undefined : state.totalQuestions,
        shuffle: state.shuffle,
        questions_per_team: state.questionsPerAgent,
        steps_count: numSteps,
        team_id: state.teamId || undefined,
        judge_config: { strict_mode: true },
      });

      // Step 2: Start test run
      const run = await startTestRun(config.id);

      // Step 3: Execute (async, returns immediately)
      executeTestRun(run.id).catch((err) => {
        console.error("Execute failed:", err);
      });

      router.push(`/lab/run/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create test");
      setSubmitting(false);
    }
  };

  const maxQuestions = state.datasetInfo?.total_examples ?? 5000;
  const categories: string[] = [];

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FlaskConical className="w-8 h-8 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">Create New Test</h1>
          </div>
          <span className="text-sm text-gray-500">Step {state.step} of 4</span>
        </div>

        {/* Content */}
        <div className="flex gap-8">
          {/* Side nav */}
          <div className="w-48 flex-shrink-0">
            <StepIndicator current={state.step} steps={STEPS} />
          </div>

          {/* Main panel */}
          <div className="flex-1 min-w-0">
            {state.step === 1 && (
              loadingDatasets ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
                </div>
              ) : (
                <DatasetSelector
                  benchmarks={benchmarks}
                  selected={state.dataset}
                  onSelect={(b) => onChange({ dataset: b.id, datasetInfo: b, selectedDomains: [], domainSelections: [], step: 2 })}
                />
              )
            )}

            {state.step === 2 && (
              <>
                {indexing && (
                  <div className="flex items-center gap-2 text-blue-400 text-sm mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Indexing benchmark questions (first time only)...
                  </div>
                )}
                <ScopeConfig
                  state={state}
                  onChange={onChange}
                  maxQuestions={maxQuestions}
                  categories={categories}
                  completedRuns={completedRuns}
                  domains={benchmarkDomains}
                  indexStatus={indexStatusData}
                  domainStats={domainStatsData}
                />
              </>
            )}

            {state.step === 3 && (
              <ExecutionConfig state={state} onChange={onChange} teams={teams} domains={benchmarkDomains} />
            )}

            {state.step === 4 && (
              <ReviewPanel
                state={state}
                onNameChange={(name) => onChange({ name })}
                submitting={submitting}
                teams={teams}
                domains={benchmarkDomains}
              />
            )}

            {/* Error */}
            {error && (
              <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                {error}
              </div>
            )}

            {/* Navigation buttons */}
            <div className="flex justify-between mt-8 pt-6 border-t border-[#1e1e2e]">
              <div>
                {state.step > 1 && (
                  <button
                    onClick={goBack}
                    className="px-4 py-2 text-gray-400 hover:text-white transition-colors flex items-center gap-2"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back
                  </button>
                )}
                {state.step === 1 && (
                  <Link
                    href="/lab"
                    className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </Link>
                )}
              </div>

              {state.step < 4 ? (
                <button
                  onClick={goNext}
                  disabled={!canNext()}
                  className="px-5 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                  Next
                  <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={handleLaunch}
                  disabled={!canNext()}
                  className="px-5 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                  <Rocket className="w-4 h-4" />
                  Start Test
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
