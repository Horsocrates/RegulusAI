"use client";

import { useState } from "react";
import {
  Database, ArrowLeft, Loader2, ChevronRight, BookOpen,
  Search, RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  getBenchmarks, getBenchmarkDetail, getBenchmarkDomains, getBenchmarkSample,
  getBenchmarkIndexStatus, indexBenchmark,
  type BenchmarkSummary, type BenchmarkDetail, type BenchmarkDomain, type BenchmarkQuestion,
  type BenchmarkIndexStatus,
} from "@/lib/lab-api";

function BenchmarkCard({
  benchmark,
  selected,
  onSelect,
}: {
  benchmark: BenchmarkSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-4 rounded-lg border transition-colors ${
        selected
          ? "bg-green-500/10 border-green-400/40"
          : "bg-[#12121a] border-[#1e1e2e] hover:border-green-400/20"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-white font-medium">{benchmark.name}</h3>
        <ChevronRight className={`w-4 h-4 transition-transform ${selected ? "rotate-90 text-green-400" : "text-gray-600"}`} />
      </div>
      <p className="text-sm text-gray-500 mb-3">{benchmark.description}</p>
      <div className="flex items-center gap-4 text-xs text-gray-600">
        <span>{benchmark.total_examples.toLocaleString()} questions</span>
        <span>{benchmark.domains_count} domains</span>
        <span>v{benchmark.version}</span>
      </div>
      <div className="mt-2">
        <IndexStatusBadge benchmarkId={benchmark.id} />
      </div>
    </button>
  );
}

function DomainList({ domains }: { domains: BenchmarkDomain[] }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-400 mb-3">Domains ({domains.length})</h3>
      <div className="grid gap-2 md:grid-cols-2">
        {domains.map((d) => (
          <div
            key={d.name}
            className="flex items-center justify-between px-3 py-2 bg-[#12121a] border border-[#1e1e2e] rounded-lg"
          >
            <span className="text-white text-sm">{d.name.replace(/_/g, " ")}</span>
            <span className="text-xs text-gray-500">{d.example_count}q</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SampleQuestions({ questions }: { questions: BenchmarkQuestion[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-400 mb-3">Sample Questions</h3>
      <div className="space-y-2">
        {questions.map((q) => (
          <div
            key={q.id}
            className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden"
          >
            <button
              onClick={() => setExpanded(expanded === q.id ? null : q.id)}
              className="w-full text-left px-4 py-3 flex items-start gap-3"
            >
              <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded shrink-0 mt-0.5">
                {q.domain.replace(/_/g, " ")}
              </span>
              <span className="text-sm text-gray-300 line-clamp-2">{q.input}</span>
            </button>
            {expanded === q.id && (
              <div className="px-4 pb-3 border-t border-[#1e1e2e]">
                <div className="mt-2 text-sm">
                  <span className="text-gray-500">Target: </span>
                  <span className="text-green-400">{q.target}</span>
                </div>
                <div className="mt-1 text-xs text-gray-600">ID: {q.id}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function IndexStatusBadge({ benchmarkId }: { benchmarkId: string }) {
  const [indexingNow, setIndexingNow] = useState(false);
  const { data: status, refetch } = useQuery({
    queryKey: ["benchmark-index-status", benchmarkId],
    queryFn: () => getBenchmarkIndexStatus(benchmarkId),
  });

  if (!status) return null;

  if (status.status === "ready") {
    const hasAttempts = status.questions_attempted > 0;
    return (
      <div className="space-y-1">
        <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded inline-block">
          Indexed: {status.total_questions.toLocaleString()} questions
        </span>
        {hasAttempts && (
          <div className="text-xs text-gray-500">
            {status.questions_attempted} attempted &middot; {(status.overall_accuracy * 100).toFixed(1)}% accuracy
          </div>
        )}
      </div>
    );
  }

  if (indexingNow || status.status === "indexing") {
    return (
      <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded flex items-center gap-1">
        <Loader2 className="w-3 h-3 animate-spin" />
        Indexing...
      </span>
    );
  }

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        setIndexingNow(true);
        indexBenchmark(benchmarkId)
          .then(() => { refetch(); setIndexingNow(false); })
          .catch(() => setIndexingNow(false));
      }}
      className="text-xs px-2 py-0.5 bg-[#1a1a2e] text-gray-400 rounded hover:text-white hover:bg-[#252540] transition-colors"
    >
      Index Benchmark
    </button>
  );
}

export default function BenchmarksPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: benchmarks, isLoading } = useQuery({
    queryKey: ["lab-benchmarks"],
    queryFn: getBenchmarks,
  });

  const { data: domains, isLoading: loadingDomains } = useQuery({
    queryKey: ["benchmark-domains", selectedId],
    queryFn: () => getBenchmarkDomains(selectedId!),
    enabled: !!selectedId,
  });

  const { data: samples, isLoading: loadingSamples } = useQuery({
    queryKey: ["benchmark-samples", selectedId],
    queryFn: () => getBenchmarkSample(selectedId!, 10),
    enabled: !!selectedId,
  });

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <Database className="w-8 h-8 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">Benchmark Browser</h1>
            <p className="text-sm text-gray-500">Explore available benchmarks and their questions</p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
          </div>
        ) : (
          <div className="flex gap-6">
            {/* Left: benchmark list */}
            <div className="w-80 flex-shrink-0 space-y-3">
              {benchmarks?.map((b) => (
                <BenchmarkCard
                  key={b.id}
                  benchmark={b}
                  selected={selectedId === b.id}
                  onSelect={() => setSelectedId(b.id)}
                />
              ))}
            </div>

            {/* Right: detail panel */}
            <div className="flex-1 min-w-0">
              {!selectedId ? (
                <div className="text-center py-20">
                  <BookOpen className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                  <p className="text-gray-500">Select a benchmark to explore</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {loadingDomains ? (
                    <div className="flex items-center gap-2 text-gray-500">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Loading domains...
                    </div>
                  ) : domains ? (
                    <DomainList domains={domains} />
                  ) : null}

                  {loadingSamples ? (
                    <div className="flex items-center gap-2 text-gray-500">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Loading samples...
                    </div>
                  ) : samples ? (
                    <SampleQuestions questions={samples} />
                  ) : null}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
