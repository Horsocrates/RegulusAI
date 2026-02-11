"use client";

import { useState, useMemo, useEffect } from "react";
import { X, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getModelLimits,
  resolveModelSettings,
  upsertModelSettings,
  deleteModelSettings,
  listModelSettings,
  type ModelLimitsInfo,
  type ResolvedSettings,
  type ModelSettingsData,
} from "@/lib/lab-api";

// ---------------------------------------------------------------------------
// Types & constants
// ---------------------------------------------------------------------------

interface Props {
  modelId: string;
  roleId: string;
  paradigmId: string;
  paradigmColor: string;
  onClose: () => void;
  onSaved: () => void;
}

interface LocalSettings {
  context_window: number;
  max_tokens: number;
  thinking_enabled: boolean;
  thinking_budget: number;
  interleaved_thinking: boolean;
  temperature: number;
}

const PRESETS: Record<string, { label: string; thinking_budget: number; max_tokens: number }> = {
  minimal:   { label: "Minimal",    thinking_budget: 1024,   max_tokens: 8192 },
  balanced:  { label: "Balanced",   thinking_budget: 10000,  max_tokens: 16000 },
  deep:      { label: "Deep",       thinking_budget: 32000,  max_tokens: 32000 },
  max_think: { label: "Max Think",  thinking_budget: 120000, max_tokens: 16000 },
  max_out:   { label: "Max Output", thinking_budget: 10000,  max_tokens: 64000 },
};

function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}K`;
  return n.toString();
}

// ---------------------------------------------------------------------------
// SliderWithPresets
// ---------------------------------------------------------------------------

function SliderWithPresets({
  label, value, onChange, min, max, step, presets, unit, color,
}: {
  label: string; value: number; onChange: (v: number) => void;
  min: number; max: number; step: number;
  presets?: number[]; unit?: string; color: string;
}) {
  const pct = max > min ? ((value - min) / (max - min)) * 100 : 0;
  return (
    <div className="mb-3.5">
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-[11px] text-gray-400 font-semibold">{label}</span>
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={value}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v)) onChange(Math.min(max, Math.max(min, v)));
            }}
            className="w-[70px] px-1.5 py-0.5 text-right bg-black/40 border border-white/10 rounded text-xs font-mono outline-none"
            style={{ color }}
          />
          <span className="text-[10px] text-gray-600">{unit ?? "tokens"}</span>
        </div>
      </div>
      <div className="relative h-5 mb-1.5">
        <div className="absolute top-2 left-0 right-0 h-1 bg-white/[0.06] rounded" />
        <div className="absolute top-2 left-0 h-1 rounded" style={{ width: `${pct}%`, background: `${color}80` }} />
        <input
          type="range" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute top-0 left-0 w-full h-5 opacity-0 cursor-pointer"
        />
        <div
          className="absolute top-1 w-3 h-3 rounded-full border-2 border-[#0f1219] pointer-events-none"
          style={{ left: `calc(${pct}% - 6px)`, background: color }}
        />
      </div>
      {presets && (
        <div className="flex gap-1">
          {presets.map((p) => (
            <button
              key={p}
              onClick={() => onChange(p)}
              className="px-2 py-0.5 text-[10px] rounded font-mono cursor-pointer transition-colors"
              style={{
                background: value === p ? `${color}20` : "rgba(255,255,255,0.03)",
                border: `1px solid ${value === p ? `${color}40` : "rgba(255,255,255,0.06)"}`,
                color: value === p ? color : "#64748b",
              }}
            >{fmt(p)}</button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toggle
// ---------------------------------------------------------------------------

function Toggle({
  label, value, onChange, desc, disabled,
}: {
  label: string; value: boolean; onChange: (v: boolean) => void;
  desc?: string; disabled?: boolean;
}) {
  return (
    <div className={`flex items-center gap-2.5 mb-2.5 ${disabled ? "opacity-30" : ""}`}>
      <button
        onClick={() => !disabled && onChange(!value)}
        className="relative w-9 h-5 rounded-[10px] border-none transition-colors"
        style={{ background: value ? "#3b82f6" : "rgba(255,255,255,0.1)", cursor: disabled ? "not-allowed" : "pointer" }}
      >
        <div
          className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-[left]"
          style={{ left: value ? 18 : 2 }}
        />
      </button>
      <div>
        <div className="text-[11px] text-[#e2e8f0] font-medium">{label}</div>
        {desc && <div className="text-[9px] text-gray-600">{desc}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationMessages
// ---------------------------------------------------------------------------

function ValidationMessages({ errors, warnings }: { errors: string[]; warnings: string[] }) {
  if (errors.length === 0 && warnings.length === 0) return null;
  return (
    <div className="mt-2.5 flex flex-col gap-1">
      {errors.map((e, i) => (
        <div key={`e${i}`} className="text-[10px] px-2 py-1 rounded bg-red-500/10 border border-red-500/20 text-red-400">
          {e}
        </div>
      ))}
      {warnings.map((w, i) => (
        <div key={`w${i}`} className="text-[10px] px-2 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400">
          {w}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CostEstimate
// ---------------------------------------------------------------------------

function CostEstimate({ settings, limits }: { settings: LocalSettings; limits: ModelLimitsInfo }) {
  const avgInput = 3000;
  const thinkTokens = settings.thinking_enabled ? settings.thinking_budget * 0.7 : 0;
  const textTokens = Math.min(settings.max_tokens, 4000);
  const totalOutput = thinkTokens + textTokens;
  const inputCost = (avgInput / 1_000_000) * limits.inputCost;
  const outputCost = (totalOutput / 1_000_000) * limits.outputCost;
  const total = inputCost + outputCost;

  return (
    <div className="mt-2.5 p-2.5 bg-black/20 rounded-md border border-white/[0.04]">
      <div className="text-[9px] text-gray-600 font-semibold tracking-wide mb-1.5">ESTIMATED COST PER CALL</div>
      <div className="flex gap-4 text-[10px]">
        <div><span className="text-gray-600">Input: </span><span className="text-gray-400">${inputCost.toFixed(4)}</span></div>
        <div>
          <span className="text-gray-600">Output: </span><span className="text-gray-400">${outputCost.toFixed(4)}</span>
          <span className="text-gray-700"> ({fmt(Math.round(thinkTokens))} think + {fmt(Math.round(textTokens))} text)</span>
        </div>
        <div><span className="text-gray-600">Total: </span><span className="text-[#e2e8f0] font-bold">${total.toFixed(3)}</span></div>
      </div>
      <div className="text-[9px] text-gray-700 mt-1">&times;200 questions &asymp; ${(total * 200).toFixed(0)}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ApiPreview
// ---------------------------------------------------------------------------

function ApiPreview({ modelId, settings }: { modelId: string; settings: LocalSettings }) {
  const lines = [`client.messages.create(`];
  lines.push(`  model="${modelId}",`);
  lines.push(`  max_tokens=${settings.max_tokens},`);
  if (settings.thinking_enabled) {
    lines.push(`  thinking={`);
    lines.push(`    "type": "enabled",`);
    lines.push(`    "budget_tokens": ${settings.thinking_budget}`);
    lines.push(`  },`);
  }
  if (settings.interleaved_thinking) {
    lines.push(`  betas=["interleaved-thinking-2025-05-14"],`);
  }
  if (settings.temperature !== 1.0) {
    lines.push(`  temperature=${settings.temperature},`);
  }
  lines.push(`  messages=[...]`);
  lines.push(`)`);

  return (
    <div className="mt-3 p-2.5 bg-black/30 rounded-md border border-white/[0.04]">
      <div className="text-[9px] text-gray-600 font-semibold tracking-wide mb-1.5">API CALL PREVIEW</div>
      <pre className="text-[10px] text-gray-500 m-0 font-mono leading-relaxed whitespace-pre-wrap">
        {lines.join("\n")}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function ModelSettingsPanel({
  modelId, roleId, paradigmId, paradigmColor, onClose, onSaved,
}: Props) {
  const queryClient = useQueryClient();

  // Fetch limits + resolved settings
  const { data: allLimits } = useQuery({
    queryKey: ["model-limits"],
    queryFn: getModelLimits,
  });

  const { data: resolved, isLoading: resolving } = useQuery({
    queryKey: ["model-settings-resolve", paradigmId, roleId, modelId],
    queryFn: () => resolveModelSettings(paradigmId, roleId, modelId),
    enabled: !!modelId,
  });

  // Find any existing saved settings for this scope (to get its id for delete)
  const { data: savedList } = useQuery({
    queryKey: ["model-settings-list", paradigmId, modelId],
    queryFn: () => listModelSettings({ paradigm_id: paradigmId, model_id: modelId }),
    enabled: !!modelId,
  });
  const existingSaved = savedList?.find(
    (s) => s.paradigm_id === paradigmId && s.role_id === roleId && s.model_id === modelId
  );

  const limits = allLimits?.[modelId];

  // Local editable state
  const [local, setLocal] = useState<LocalSettings | null>(null);
  const [dirty, setDirty] = useState(false);

  // Seed local from resolved
  useEffect(() => {
    if (resolved && !local) {
      setLocal({
        context_window: resolved.context_window,
        max_tokens: resolved.max_tokens,
        thinking_enabled: resolved.thinking_enabled,
        thinking_budget: resolved.thinking_budget,
        interleaved_thinking: resolved.interleaved_thinking,
        temperature: resolved.temperature,
      });
    }
  }, [resolved, local]);

  const update = (key: keyof LocalSettings, value: number | boolean) => {
    setLocal((prev) => prev ? { ...prev, [key]: value } : prev);
    setDirty(true);
  };

  // Validation
  const validation = useMemo(() => {
    const errors: string[] = [];
    const warnings: string[] = [];
    if (!local || !limits) return { errors, warnings };

    if (local.context_window > limits.maxContext) errors.push(`Context window max for ${limits.name}: ${fmt(limits.maxContext)}`);
    if (local.max_tokens > limits.maxOutput) errors.push(`Max output for ${limits.name}: ${fmt(limits.maxOutput)}`);
    if (local.thinking_enabled) {
      if (local.thinking_budget < 1024) errors.push("Thinking budget minimum: 1,024 tokens");
      if (!local.interleaved_thinking && local.thinking_budget >= local.max_tokens) {
        errors.push(`budget_tokens (${fmt(local.thinking_budget)}) must be < max_tokens (${fmt(local.max_tokens)}) — enable Interleaved Thinking to bypass`);
      }
    }
    if (local.max_tokens > local.context_window * 0.8) warnings.push("Max tokens uses >80% of context window");
    if (local.thinking_enabled && local.thinking_budget > 64000) warnings.push("Very high thinking budget — diminishing returns above 64K for most tasks");

    return { errors, warnings };
  }, [local, limits]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!local) return;
      await upsertModelSettings({
        paradigm_id: paradigmId,
        role_id: roleId,
        model_id: modelId,
        ...local,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-settings-resolve"] });
      queryClient.invalidateQueries({ queryKey: ["model-settings-list"] });
      setDirty(false);
      onSaved();
    },
  });

  // Reset (delete override)
  const resetMutation = useMutation({
    mutationFn: async () => {
      if (existingSaved) {
        await deleteModelSettings(existingSaved.id);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-settings-resolve"] });
      queryClient.invalidateQueries({ queryKey: ["model-settings-list"] });
      setLocal(null);
      setDirty(false);
    },
  });

  // Apply preset
  const applyPreset = (presetId: string) => {
    const preset = PRESETS[presetId];
    if (!preset || !limits) return;
    setLocal((prev) => prev ? {
      ...prev,
      thinking_budget: Math.min(preset.thinking_budget, limits.maxOutput),
      max_tokens: Math.min(preset.max_tokens, limits.maxOutput),
      thinking_enabled: true,
    } : prev);
    setDirty(true);
  };

  if (resolving || !local || !limits) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
        <div className="bg-[#12121a] border border-white/10 rounded-xl p-8">
          <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-8">
      <div className="bg-[#12121a] border border-white/10 rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-lg font-extrabold text-white">Model Settings</span>
            <span
              className="text-[9px] px-2 py-0.5 rounded font-semibold"
              style={{ background: `${paradigmColor}20`, color: paradigmColor }}
            >
              {paradigmId.toUpperCase()} / {roleId.toUpperCase()}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Resolved-from badge */}
          {resolved && (
            <div className="mb-3 text-[10px] text-gray-500">
              Resolved from: <span className="text-gray-400 font-semibold">{resolved.resolved_from}</span>
              {existingSaved && (
                <span className="ml-2 text-green-400/70">(has override)</span>
              )}
            </div>
          )}

          {/* Quick presets */}
          <div className="mb-4">
            <div className="text-[9px] text-gray-600 font-semibold tracking-wide mb-1.5">QUICK PRESETS</div>
            <div className="flex gap-1">
              {Object.entries(PRESETS).map(([id, p]) => (
                <button
                  key={id}
                  onClick={() => applyPreset(id)}
                  className="px-2.5 py-1 text-[10px] bg-white/[0.04] border border-white/[0.08] rounded text-gray-400 hover:bg-white/[0.08] transition-colors cursor-pointer"
                  title={`Think: ${fmt(p.thinking_budget)} · Out: ${fmt(p.max_tokens)}`}
                >{p.label}</button>
              ))}
            </div>
          </div>

          {/* Context Window */}
          <SliderWithPresets
            label="Context Window"
            value={local.context_window}
            onChange={(v) => update("context_window", v)}
            min={8192} max={limits.maxContext} step={8192}
            presets={
              limits.maxContext >= 200000
                ? [32000, 64000, 128000, 200000]
                : limits.maxContext >= 128000
                  ? [32000, 64000, 128000]
                  : [16000, 32000, 64000]
            }
            color="#64748b"
          />

          {/* Max Output Tokens */}
          <SliderWithPresets
            label="Max Output Tokens"
            value={local.max_tokens}
            onChange={(v) => update("max_tokens", v)}
            min={1024} max={limits.maxOutput} step={1024}
            presets={
              limits.maxOutput >= 64000
                ? [4096, 8192, 16000, 32000, 64000]
                : limits.maxOutput >= 16384
                  ? [4096, 8192, 16384]
                  : [4096, 8192]
            }
            color="#3b82f6"
          />

          {/* Thinking toggle */}
          <Toggle
            label="Extended Thinking"
            value={local.thinking_enabled}
            onChange={(v) => update("thinking_enabled", v)}
            desc={limits.thinking ? "Enable chain-of-thought reasoning" : "Not supported by this model"}
            disabled={!limits.thinking}
          />

          {/* Thinking Budget */}
          {local.thinking_enabled && limits.thinking && (
            <>
              <SliderWithPresets
                label="Thinking Budget"
                value={local.thinking_budget}
                onChange={(v) => update("thinking_budget", v)}
                min={1024}
                max={local.interleaved_thinking ? limits.maxContext : Math.min(local.max_tokens - 1, limits.maxOutput)}
                step={1024}
                presets={
                  local.interleaved_thinking
                    ? [1024, 10000, 32000, 64000, 120000]
                    : [1024, 4096, 8192, Math.max(1024, local.max_tokens - 2048)]
                }
                color="#f59e0b"
              />

              <Toggle
                label="Interleaved Thinking"
                value={local.interleaved_thinking}
                onChange={(v) => update("interleaved_thinking", v)}
                desc={limits.interleaved
                  ? "Allows thinking budget > max_tokens. Uses beta header."
                  : "Not supported by this model"
                }
                disabled={!limits.interleaved}
              />
            </>
          )}

          {/* Temperature */}
          <SliderWithPresets
            label="Temperature"
            value={local.temperature}
            onChange={(v) => update("temperature", v)}
            min={0} max={1} step={0.05}
            presets={[0, 0.3, 0.7, 1.0]}
            unit=""
            color="#10b981"
          />

          {/* Validation */}
          <ValidationMessages errors={validation.errors} warnings={validation.warnings} />

          {/* Cost estimate */}
          <CostEstimate settings={local} limits={limits} />

          {/* API preview */}
          <ApiPreview modelId={modelId} settings={local} />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-white/[0.06]">
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending || !existingSaved}
            className="px-3 py-1.5 text-[11px] bg-white/[0.04] border border-white/[0.08] rounded text-gray-500 hover:bg-white/[0.08] transition-colors disabled:opacity-30"
          >
            {resetMutation.isPending ? "Resetting..." : "Reset to Defaults"}
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!dirty || validation.errors.length > 0 || saveMutation.isPending}
            className="px-5 py-2 text-xs font-semibold rounded-md transition-colors disabled:opacity-30"
            style={{
              background: dirty && validation.errors.length === 0 ? `${paradigmColor}25` : "rgba(255,255,255,0.03)",
              border: `1px solid ${dirty && validation.errors.length === 0 ? `${paradigmColor}50` : "rgba(255,255,255,0.06)"}`,
              color: dirty && validation.errors.length === 0 ? paradigmColor : "#334155",
            }}
          >
            {saveMutation.isPending ? (
              <span className="flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin" /> Saving...</span>
            ) : dirty ? "Save Settings" : "Saved"}
          </button>
        </div>
      </div>
    </div>
  );
}
