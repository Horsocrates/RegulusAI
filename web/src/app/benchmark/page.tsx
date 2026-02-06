"use client";

import { useState, useEffect, useRef } from "react";
import { Shield, Loader2, CheckCircle, XCircle, BarChart3, ArrowLeft, Play, Square, Brain, Sparkles, Scale } from "lucide-react";
import Link from "next/link";
import { BenchmarkItem } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReasoningStep {
  domain: string;
  content: string;
}

interface JudgeResult {
  correct: boolean;
  informative: boolean;
  reason: string;
}

interface ExtendedBenchmarkItem extends BenchmarkItem {
  reasoning_steps?: ReasoningStep[];
  judge?: JudgeResult | null;
}

type Phase = "idle" | "reasoning" | "synthesizing" | "judging" | "done";

function PhaseIndicator({ phase, question }: { phase: Phase; question: string }) {
  const phases = [
    { id: "reasoning", icon: Brain, label: "Reasoning", color: "text-blue-600" },
    { id: "synthesizing", icon: Sparkles, label: "Synthesizing", color: "text-purple-600" },
    { id: "judging", icon: Scale, label: "Judging", color: "text-orange-600" },
  ];

  return (
    <div className="flex items-center gap-4 mb-2">
      {phases.map((p, i) => {
        const Icon = p.icon;
        const isActive = phase === p.id;
        const isPast = phases.findIndex(x => x.id === phase) > i;
        return (
          <div key={p.id} className={`flex items-center gap-1 ${isActive ? p.color : isPast ? "text-green-500" : "text-gray-300"}`}>
            {isActive ? <Loader2 className="w-4 h-4 animate-spin" /> : isPast ? <CheckCircle className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
            <span className={`text-sm font-medium ${isActive ? "" : "opacity-60"}`}>{p.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function ReasoningPanel({ steps, phase, question }: { steps: ReasoningStep[]; phase: Phase; question: string }) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.scrollTop = panelRef.current.scrollHeight;
    }
  }, [steps]);

  const isActive = phase === "reasoning" || phase === "synthesizing" || phase === "judging";

  if (!isActive && phase !== "done") return null;

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-5 h-5 text-blue-400" />
        <span className="font-medium text-white">Agent Reasoning</span>
        <span className="text-xs text-gray-400 ml-auto">First worker only</span>
      </div>

      <PhaseIndicator phase={phase} question={question} />

      <div className="text-xs text-gray-400 mb-2 truncate">
        Q: {question}
      </div>

      <div ref={panelRef} className="bg-gray-950 rounded p-3 max-h-64 overflow-y-auto font-mono text-sm">
        {steps.length === 0 && isActive && (
          <div className="text-gray-500 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            Processing...
          </div>
        )}
        {steps.map((step, i) => (
          <div key={i} className="mb-3">
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold mr-2 ${
              step.domain === "D1" ? "bg-blue-900 text-blue-300" :
              step.domain === "D2" ? "bg-purple-900 text-purple-300" :
              step.domain === "D3" ? "bg-green-900 text-green-300" :
              step.domain === "D4" ? "bg-yellow-900 text-yellow-300" :
              step.domain === "D5" ? "bg-orange-900 text-orange-300" :
              "bg-pink-900 text-pink-300"
            }`}>
              {step.domain}
            </span>
            <span className="text-gray-300">{step.content}</span>
          </div>
        ))}
        {phase === "synthesizing" && (
          <div className="text-purple-400 flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            Generating final answer...
          </div>
        )}
        {phase === "judging" && (
          <div className="text-orange-400 flex items-center gap-2">
            <Scale className="w-4 h-4" />
            Judge evaluating...
          </div>
        )}
      </div>
    </div>
  );
}

function StatsBar({ total, completed, valid, correct }: { total: number; completed: number; valid: number; correct: number }) {
  const remaining = total - completed;
  const correctRate = completed > 0 ? (correct / completed * 100).toFixed(1) : "0.0";

  return (
    <div className="bg-white rounded-lg border p-3 mb-4 flex items-center gap-6 text-sm">
      <div className="flex items-center gap-2">
        <span className="text-gray-500">Progress:</span>
        <span className="font-bold">{completed}/{total}</span>
        <span className="text-gray-400">({remaining} left)</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-gray-500">Valid:</span>
        <span className="font-bold text-green-600">{valid}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-gray-500">Correct:</span>
        <span className="font-bold text-blue-600">{correct}</span>
        <span className="text-gray-400">({correctRate}%)</span>
      </div>
    </div>
  );
}

function ResultRow({ item, index }: { item: ExtendedBenchmarkItem; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const isCorrect = item.judge?.correct;
  const borderColor = isCorrect ? "border-green-300 bg-green-50/50" :
                      item.valid ? "border-yellow-200 bg-yellow-50/30" :
                      "border-red-200 bg-red-50/30";

  return (
    <div className={`border rounded-lg p-4 ${borderColor}`}>
      <div className="flex items-start gap-3">
        <span className="text-sm font-mono text-gray-400 mt-1">#{index + 1}</span>
        {isCorrect ? (
          <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 shrink-0" />
        ) : item.valid ? (
          <XCircle className="w-5 h-5 text-yellow-500 mt-0.5 shrink-0" />
        ) : (
          <XCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800">{item.question}</p>
          <div className="flex flex-wrap gap-2 mt-1 text-xs">
            <span className="text-gray-500">{item.time_seconds.toFixed(1)}s</span>
            {item.corrections > 0 && (
              <span className="text-yellow-600">⚠ {item.corrections} corrections</span>
            )}
            {item.synthesized && (
              <span className="text-blue-600">✓ synthesized</span>
            )}
            {item.judge && (
              <span className={isCorrect ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
                {isCorrect ? "✓ Correct" : "✗ Incorrect"}
              </span>
            )}
          </div>

          {expanded && (
            <div className="mt-3 space-y-2">
              <div className="bg-gray-100 rounded p-2 max-h-32 overflow-y-auto">
                <span className="text-xs font-medium text-gray-500">Expected:</span>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{item.expected}</p>
              </div>
              <div className={`rounded p-2 max-h-64 overflow-y-auto ${isCorrect ? "bg-green-100" : "bg-yellow-100"}`}>
                <span className="text-xs font-medium text-gray-500">Regulus answer:</span>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{item.answer || "No valid response"}</p>
              </div>
              {item.judge?.reason && (
                <div className="bg-blue-50 rounded p-2 max-h-32 overflow-y-auto">
                  <span className="text-xs font-medium text-gray-500">Judge reason:</span>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{item.judge.reason}</p>
                </div>
              )}
            </div>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-blue-600 hover:underline shrink-0"
        >
          {expanded ? "Hide" : "Details"}
        </button>
      </div>
    </div>
  );
}

export default function BenchmarkPage() {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<ExtendedBenchmarkItem[]>([]);
  const [stats, setStats] = useState({ total: 0, completed: 0, valid: 0, correct: 0 });
  const [error, setError] = useState<string | null>(null);
  const [numQuestions, setNumQuestions] = useState(10);
  const [concurrency, setConcurrency] = useState(5);
  const [provider, setProvider] = useState("claude");
  const [phase, setPhase] = useState<Phase>("idle");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const resultsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (resultsEndRef.current && running) {
      resultsEndRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [results.length, running]);

  const handleStart = () => {
    setRunning(true);
    setError(null);
    setResults([]);
    setStats({ total: numQuestions, completed: 0, valid: 0, correct: 0 });
    setPhase("idle");
    setReasoningSteps([]);
    setCurrentQuestion("");

    const url = `${API_URL}/api/benchmark/stream?n=${numQuestions}&concurrency=${concurrency}&provider=${provider}&with_judge=true`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        if (data.type === "status") {
          setPhase(data.phase as Phase);
          if (data.question) {
            setCurrentQuestion(data.question);
          }
        } else if (data.type === "reasoning") {
          setReasoningSteps(prev => [...prev, { domain: data.domain, content: data.content }]);
        } else if (data.type === "progress") {
          setResults(prev => {
            const updated = [...prev];
            updated[data.index] = data.item;
            return updated.filter(Boolean);
          });
          setStats({
            total: data.total,
            completed: data.completed,
            valid: data.valid_so_far,
            correct: data.correct_so_far || 0,
          });
          // Reset reasoning for next question
          if (data.index === 0) {
            setPhase("idle");
            setReasoningSteps([]);
          }
        } else if (data.type === "done") {
          setRunning(false);
          setPhase("done");
          eventSource.close();
        } else if (data.type === "error") {
          setError(data.message);
          setRunning(false);
          eventSource.close();
        }
      } catch (err) {
        console.error("Parse error:", err);
      }
    };

    eventSource.onerror = () => {
      if (running) {
        setError("Connection lost");
        setRunning(false);
      }
      eventSource.close();
    };
  };

  const handleStop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setRunning(false);
    setPhase("idle");
  };

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/" className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <BarChart3 className="w-10 h-10 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold">SimpleQA Benchmark</h1>
            <p className="text-gray-500">Real-time streaming with judge evaluation</p>
          </div>
        </div>

        {/* Stats Bar */}
        {(running || stats.completed > 0) && (
          <StatsBar {...stats} />
        )}

        {/* Controls */}
        <div className="bg-white rounded-lg border p-4 mb-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Questions</label>
              <select
                value={numQuestions}
                onChange={(e) => setNumQuestions(Number(e.target.value))}
                disabled={running}
                className="px-3 py-2 border rounded-lg text-sm disabled:opacity-50"
              >
                <option value={1}>1 (test)</option>
                <option value={5}>5 (quick)</option>
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
                <option value={4326}>4326 (all)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Parallel</label>
              <select
                value={concurrency}
                onChange={(e) => setConcurrency(Number(e.target.value))}
                disabled={running}
                className="px-3 py-2 border rounded-lg text-sm disabled:opacity-50"
              >
                <option value={1}>1 (sequential)</option>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={running}
                className="px-3 py-2 border rounded-lg text-sm disabled:opacity-50"
              >
                <option value="claude">Claude</option>
                <option value="openai">GPT-4</option>
              </select>
            </div>
            {!running ? (
              <button
                onClick={handleStart}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Start
              </button>
            ) : (
              <button
                onClick={handleStop}
                className="px-6 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 flex items-center gap-2"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            )}
          </div>
        </div>

        {/* Reasoning Panel */}
        {(running || phase !== "idle") && (
          <ReasoningPanel steps={reasoningSteps} phase={phase} question={currentQuestion} />
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        {/* Results List */}
        {results.length > 0 && (
          <div>
            <h3 className="font-medium mb-3 flex items-center gap-2">
              Results
              {running && <Loader2 className="w-4 h-4 animate-spin text-blue-600" />}
            </h3>
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {results.map((item, i) => (
                <ResultRow key={i} item={item} index={i} />
              ))}
              <div ref={resultsEndRef} />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
