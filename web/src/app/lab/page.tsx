"use client";

import { useState, useEffect } from "react";
import { FlaskConical, Plus, Trash2, Play, FileText, ArrowLeft, Loader2, CheckCircle, Clock, PauseCircle, XCircle, DollarSign } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = "http://localhost:8000";

interface CostInfo {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  spent_cost: number;
  estimated_remaining: number;
  estimated_total: number;
  currency: string;
}

interface LabRun {
  id: number;
  name: string;
  dataset: string;
  provider: string;
  total_questions: number;
  num_steps: number;
  status: string;
  current_step: number;
  completed_questions: number;
  valid_count: number;
  correct_count: number;
  total_time: number;
  progress_percent: number;
  input_tokens: number;
  output_tokens: number;
  cost: CostInfo | null;
  created_at: string;
  updated_at: string;
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    created: { color: "bg-gray-100 text-gray-700", icon: Clock },
    running: { color: "bg-blue-100 text-blue-700", icon: Loader2 },
    paused: { color: "bg-yellow-100 text-yellow-700", icon: PauseCircle },
    completed: { color: "bg-green-100 text-green-700", icon: CheckCircle },
    failed: { color: "bg-red-100 text-red-700", icon: XCircle },
  }[status] || { color: "bg-gray-100 text-gray-700", icon: Clock };

  const Icon = config.icon;
  const isAnimating = status === "running";

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
      <Icon className={`w-3 h-3 ${isAnimating ? "animate-spin" : ""}`} />
      {status}
    </span>
  );
}

const DATASETS = [
  { id: "simpleqa", name: "SimpleQA", total: 4326, description: "OpenAI factual QA benchmark" },
];

// Cost estimates per question (input + output tokens)
// Claude Sonnet: $3/1M input, $15/1M output
// GPT-4o: $2.50/1M input, $10/1M output
const COST_PER_QUESTION = {
  claude: 0.072,  // ~8K input + ~4K output at Claude pricing
  openai: 0.06,   // ~8K input + ~4K output at GPT-4o pricing
};

function formatCost(cost: number): string {
  if (cost < 0.01) return "<$0.01";
  return `$${cost.toFixed(2)}`;
}

function CreateRunModal({ isOpen, onClose, onCreated }: { isOpen: boolean; onClose: () => void; onCreated: (run: LabRun) => void }) {
  const [name, setName] = useState("");
  const [dataset, setDataset] = useState("simpleqa");
  const [totalQuestions, setTotalQuestions] = useState(100);
  const [numStepsInput, setNumStepsInput] = useState("4");
  const [provider, setProvider] = useState("claude");
  const [concurrency, setConcurrency] = useState(5);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedDataset = DATASETS.find(d => d.id === dataset) || DATASETS[0];
  const maxQuestions = selectedDataset.total;

  // Calculate actual number of steps (cap at totalQuestions)
  const parsedSteps = parseInt(numStepsInput) || 1;
  const actualSteps = Math.min(Math.max(1, parsedSteps), totalQuestions);
  const questionsPerStep = Math.ceil(totalQuestions / actualSteps);

  // Estimated cost
  const estimatedCost = totalQuestions * (COST_PER_QUESTION[provider as keyof typeof COST_PER_QUESTION] || 0.07);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/lab/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          total_questions: totalQuestions,
          num_steps: actualSteps,
          dataset,
          provider,
          concurrency,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        const detail = errData?.detail;
        if (Array.isArray(detail)) {
          throw new Error(detail.map((d: any) => d.msg).join(", "));
        }
        throw new Error(detail || `Failed to create run: ${res.status}`);
      }

      const run = await res.json();
      onCreated(run);
      onClose();
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold mb-4">Create New Lab Run</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Run Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., SimpleQA Test Run 1"
              className="w-full px-3 py-2 border rounded-lg"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Dataset</label>
            <select
              value={dataset}
              onChange={(e) => {
                setDataset(e.target.value);
                const ds = DATASETS.find(d => d.id === e.target.value);
                if (ds && totalQuestions > ds.total) {
                  setTotalQuestions(ds.total);
                }
              }}
              className="w-full px-3 py-2 border rounded-lg"
            >
              {DATASETS.map(ds => (
                <option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.total} questions)
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">{selectedDataset.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Total Questions</label>
              <select
                value={totalQuestions}
                onChange={(e) => setTotalQuestions(Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
                {maxQuestions >= 4326 && <option value={4326}>4326 (all)</option>}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Number of Steps</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={1}
                  max={totalQuestions}
                  value={numStepsInput}
                  onChange={(e) => setNumStepsInput(e.target.value)}
                  className="flex-1 px-3 py-2 border rounded-lg"
                  placeholder="e.g., 4"
                />
                <button
                  type="button"
                  onClick={() => setNumStepsInput(String(Math.ceil(totalQuestions / concurrency)))}
                  className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200"
                  title="Set steps = questions / concurrency"
                >
                  Auto
                </button>
              </div>
              {parsedSteps > totalQuestions && (
                <p className="text-xs text-yellow-600 mt-1">
                  Capped to {totalQuestions} (1 question/step)
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg"
              >
                <option value="claude">Claude</option>
                <option value="openai">GPT-4</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Concurrency</label>
              <select
                value={concurrency}
                onChange={(e) => setConcurrency(Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg"
              >
                <option value={1}>1 (sequential)</option>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
              </select>
            </div>
          </div>

          <div className="text-sm bg-gray-50 p-3 rounded space-y-2">
            <div className="grid grid-cols-3 gap-2 text-center text-gray-600">
              <div>
                <div className="text-lg font-bold text-purple-600">{actualSteps}</div>
                <div className="text-xs">steps</div>
              </div>
              <div>
                <div className="text-lg font-bold text-purple-600">{questionsPerStep}</div>
                <div className="text-xs">questions/step</div>
              </div>
              <div>
                <div className="text-lg font-bold text-purple-600">{Math.min(concurrency, questionsPerStep)}</div>
                <div className="text-xs">parallel</div>
              </div>
            </div>
            <div className="flex items-center justify-center gap-2 text-green-700 bg-green-50 px-2 py-1.5 rounded">
              <DollarSign className="w-4 h-4" />
              <span>Estimated: <strong>{formatCost(estimatedCost)}</strong></span>
              <span className="text-xs text-green-600">
                (~{formatCost(COST_PER_QUESTION[provider as keyof typeof COST_PER_QUESTION] || 0.07)}/q)
              </span>
            </div>
          </div>

          {error && (
            <div className="text-red-600 text-sm bg-red-50 p-2 rounded">{error}</div>
          )}

          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
            >
              {creating && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Run
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RunCard({ run, onDelete }: { run: LabRun; onDelete: (id: number) => void }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete run "${run.name}"?`)) return;

    setDeleting(true);
    try {
      await fetch(`${API_URL}/api/lab/runs/${run.id}`, { method: "DELETE" });
      onDelete(run.id);
    } catch (err) {
      console.error(err);
    } finally {
      setDeleting(false);
    }
  };

  const correctRate = run.completed_questions > 0
    ? (run.correct_count / run.completed_questions * 100).toFixed(1)
    : "0.0";

  return (
    <div
      onClick={() => router.push(`/lab/run/${run.id}`)}
      className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{run.name}</h3>
          <p className="text-sm text-gray-500">
            {run.dataset} / {run.provider} / {run.num_steps} steps
          </p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="mb-3">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-500">Progress</span>
          <span className="font-medium">{run.progress_percent.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-purple-600 h-2 rounded-full transition-all"
            style={{ width: `${run.progress_percent}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 text-sm mb-3">
        <div className="text-center">
          <div className="text-gray-500">Questions</div>
          <div className="font-medium">{run.completed_questions}/{run.total_questions}</div>
        </div>
        <div className="text-center">
          <div className="text-gray-500">Valid</div>
          <div className="font-medium text-green-600">{run.valid_count}</div>
        </div>
        <div className="text-center">
          <div className="text-gray-500">Correct</div>
          <div className="font-medium text-blue-600">{correctRate}%</div>
        </div>
        <div className="text-center">
          <div className="text-gray-500">Cost</div>
          <div className="font-medium text-emerald-600">
            {run.cost ? formatCost(run.cost.spent_cost) : "-"}
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center text-xs text-gray-400">
        <span>Created: {new Date(run.created_at).toLocaleString()}</span>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="p-1 hover:bg-red-50 hover:text-red-600 rounded"
        >
          {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

export default function LabPage() {
  const [runs, setRuns] = useState<LabRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const fetchRuns = async () => {
    try {
      const res = await fetch(`${API_URL}/api/lab/runs`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleCreated = (run: LabRun) => {
    setRuns((prev) => [run, ...prev]);
  };

  const handleDelete = (id: number) => {
    setRuns((prev) => prev.filter((r) => r.id !== id));
  };

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/" className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FlaskConical className="w-10 h-10 text-purple-600" />
          <div className="flex-1">
            <h1 className="text-2xl font-bold">Lab</h1>
            <p className="text-gray-500">Stepped benchmark testing with persistence</p>
          </div>
          <Link
            href="/lab/reports"
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg flex items-center gap-2"
          >
            <FileText className="w-4 h-4" />
            Reports
          </Link>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Run
          </button>
        </div>

        {/* Runs Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
          </div>
        ) : runs.length === 0 ? (
          <div className="bg-white border rounded-lg p-12 text-center">
            <FlaskConical className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <h2 className="text-xl font-medium text-gray-700 mb-2">No runs yet</h2>
            <p className="text-gray-500 mb-4">Create your first Lab run to get started</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Run
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {runs.map((run) => (
              <RunCard key={run.id} run={run} onDelete={handleDelete} />
            ))}
          </div>
        )}

        <CreateRunModal
          isOpen={showCreate}
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      </div>
    </main>
  );
}
