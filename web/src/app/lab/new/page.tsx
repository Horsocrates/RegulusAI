"use client";

import { useState, useEffect } from "react";
import {
  FlaskConical, ArrowLeft, ArrowRight, Check, Loader2,
  Rocket, Database, Target, Cpu, FileCheck,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getDatasets, getLabRuns, createLabRun,
  type Dataset, type LabRun, type CreateRunRequest, formatCost,
} from "@/lib/lab-api";

// === Types ===

interface WizardState {
  step: 1 | 2 | 3 | 4;
  dataset: string | null;
  datasetInfo: Dataset | null;
  totalQuestions: number;
  category: string | null;
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
}

const INITIAL_STATE: WizardState = {
  step: 1,
  dataset: null,
  datasetInfo: null,
  totalQuestions: 50,
  category: null,
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
};

const COST_PER_Q: Record<string, number> = {
  claude: 0.024,
  openai: 0.020,
};

const TIME_PER_Q = 105; // seconds per question (average)

// Fallback datasets when API is unavailable
const FALLBACK_DATASETS: Dataset[] = [
  {
    id: "simpleqa",
    name: "SimpleQA",
    description: "Factual question answering benchmark by OpenAI",
    total_questions: 4326,
    categories: [],
    type: "factual",
  },
  {
    id: "bbeh",
    name: "BBEH (Big-Bench Extra Hard)",
    description: "Complex reasoning benchmark by Google DeepMind",
    total_questions: 460,
    categories: [],
    type: "reasoning",
  },
];

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

function DatasetSelector({ datasets, selected, onSelect }: {
  datasets: Dataset[];
  selected: string | null;
  onSelect: (ds: Dataset) => void;
}) {
  const selectedDs = datasets.find((ds) => ds.id === selected);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white mb-1">Select Dataset</h2>
      <p className="text-gray-500 mb-4">Choose a benchmark for testing:</p>

      <select
        value={selected || ""}
        onChange={(e) => {
          const ds = datasets.find((d) => d.id === e.target.value);
          if (ds) onSelect(ds);
        }}
        className="w-full px-4 py-3 bg-[#12121a] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none appearance-none cursor-pointer"
      >
        <option value="" disabled>Select a dataset...</option>
        {datasets.map((ds) => (
          <option key={ds.id} value={ds.id}>
            {ds.name} — {ds.total_questions.toLocaleString()} questions
          </option>
        ))}
      </select>

      {/* Info card for selected dataset */}
      {selectedDs && (
        <div className="p-4 bg-[#12121a] border border-green-400/30 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <Database className="w-4 h-4 text-green-400" />
            <span className="font-medium text-white">{selectedDs.name}</span>
            <span className="text-xs px-2 py-0.5 bg-[#1a1a2e] rounded text-gray-400">{selectedDs.type}</span>
          </div>
          <p className="text-sm text-gray-400 mb-2">{selectedDs.description}</p>
          <p className="text-sm text-gray-500">{selectedDs.total_questions.toLocaleString()} questions available</p>
        </div>
      )}
    </div>
  );
}

// === Step 2: Scope ===

function ScopeConfig({ state, onChange, maxQuestions, categories, completedRuns }: {
  state: WizardState;
  onChange: (patch: Partial<WizardState>) => void;
  maxQuestions: number;
  categories: string[];
  completedRuns: LabRun[];
}) {
  const PRESETS = [1, 10, 50, 100, 500];
  const [customMode, setCustomMode] = useState(false);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-1">Scope</h2>

      {/* Question count */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Questions</label>
        {state.retryFromRunId !== null ? (
          <div className="px-4 py-3 bg-[#12121a] border border-[#1e1e2e] rounded-lg">
            <span className="text-white font-medium">{state.totalQuestions}</span>
            <span className="text-gray-500 ml-2">failed questions from Run #{state.retryFromRunId}</span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((n) => (
              <button
                key={n}
                onClick={() => { setCustomMode(false); onChange({ totalQuestions: n }); }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  !customMode && state.totalQuestions === n
                    ? "bg-green-500 text-white"
                    : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
                }`}
              >
                {n === 1 ? "1 (test)" : n}
              </button>
            ))}
            <button
              onClick={() => { setCustomMode(false); onChange({ totalQuestions: maxQuestions }); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                !customMode && state.totalQuestions === maxQuestions
                  ? "bg-green-500 text-white"
                  : "bg-[#1a1a2e] text-gray-300 hover:bg-[#252540]"
              }`}
            >
              Full ({maxQuestions.toLocaleString()})
            </button>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={maxQuestions}
                placeholder="Custom"
                value={customMode ? state.totalQuestions : ""}
                onChange={(e) => {
                  setCustomMode(true);
                  onChange({ totalQuestions: Math.min(Number(e.target.value) || 1, maxQuestions) });
                }}
                onFocus={() => setCustomMode(true)}
                className="w-24 px-3 py-2 bg-[#1a1a2e] border border-[#1e1e2e] rounded-lg text-white text-sm focus:border-green-400 focus:outline-none"
              />
            </div>
          </div>
        )}
      </div>

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
      {completedRuns.length > 0 && (
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

function ExecutionConfig({ state, onChange }: {
  state: WizardState;
  onChange: (patch: Partial<WizardState>) => void;
}) {
  const AGENT_PRESETS = [1, 3, 5, 10];

  const numSteps = state.stepMode === "continuous"
    ? 1
    : Math.max(1, Math.ceil(state.totalQuestions / (state.questionsPerAgent * state.concurrency)));

  const timeEstimate = (state.totalQuestions * TIME_PER_Q) / Math.max(1, state.concurrency);
  const formatEta = (secs: number) => {
    if (secs < 60) return `~${Math.round(secs)}s`;
    if (secs < 3600) return `~${Math.round(secs / 60)}min`;
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return `~${h}h ${m}m`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-1">Execution</h2>

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
                    max={state.totalQuestions}
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
          <span className="text-white">{state.totalQuestions}</span>
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

function ReviewPanel({ state, onNameChange, submitting }: {
  state: WizardState;
  onNameChange: (name: string) => void;
  submitting: boolean;
}) {
  const numSteps = state.stepMode === "continuous"
    ? 1
    : Math.max(1, Math.ceil(state.totalQuestions / (state.questionsPerAgent * state.concurrency)));

  const costEstimate = state.totalQuestions * (COST_PER_Q[state.provider] || 0.024);
  const timeEstimate = (state.totalQuestions * TIME_PER_Q) / Math.max(1, state.concurrency);

  const formatEta = (secs: number) => {
    if (secs < 60) return `~${Math.round(secs)}s`;
    if (secs < 3600) return `~${Math.round(secs / 60)} minutes`;
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return `~${h}h ${m}m`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-1">Review & Launch</h2>

      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5 space-y-3">
        <Row label="Dataset" value={state.datasetInfo?.name || state.dataset || ""} />
        <Row label="Questions" value={state.totalQuestions.toLocaleString()} />
        {state.category && <Row label="Category" value={state.category} />}
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

  // Fetch datasets (with fallback)
  const { data: datasetsData, isLoading: loadingDatasets } = useQuery({
    queryKey: ["lab-datasets"],
    queryFn: getDatasets,
  });
  const datasets = datasetsData?.datasets?.length ? datasetsData.datasets : FALLBACK_DATASETS;

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

  // Auto-generate name when entering step 4
  useEffect(() => {
    if (state.step === 4 && !state.name) {
      const ds = state.datasetInfo?.name || state.dataset || "Test";
      const ver = state.modelVersion ? ` ${state.modelVersion}` : "";
      onChange({ name: `${ds} ${state.totalQuestions}q${ver}` });
    }
  }, [state.step]);

  // Navigation
  const canNext = () => {
    switch (state.step) {
      case 1: return state.dataset !== null;
      case 2: return state.totalQuestions > 0;
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
        : Math.max(1, Math.ceil(state.totalQuestions / (state.questionsPerAgent * state.concurrency)));

      const req: CreateRunRequest = {
        name: state.name.trim(),
        dataset: state.dataset!,
        total_questions: state.totalQuestions,
        num_steps: numSteps,
        concurrency: state.concurrency,
        provider: state.provider,
        category: state.category,
        source_run_id: state.retryFromRunId,
        model_version: state.modelVersion,
        mode: state.mode,
        reasoning_model: state.mode === "v2" ? state.reasoningModel : "",
      };

      const run = await createLabRun(req);
      router.push(`/lab/run/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create test");
      setSubmitting(false);
    }
  };

  const maxQuestions = state.datasetInfo?.total_questions ?? 5000;
  const categories = state.datasetInfo?.categories ?? [];

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
                  datasets={datasets}
                  selected={state.dataset}
                  onSelect={(ds) => onChange({ dataset: ds.id, datasetInfo: ds })}
                />
              )
            )}

            {state.step === 2 && (
              <ScopeConfig
                state={state}
                onChange={onChange}
                maxQuestions={maxQuestions}
                categories={categories}
                completedRuns={completedRuns}
              />
            )}

            {state.step === 3 && (
              <ExecutionConfig state={state} onChange={onChange} />
            )}

            {state.step === 4 && (
              <ReviewPanel
                state={state}
                onNameChange={(name) => onChange({ name })}
                submitting={submitting}
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
