"use client";

import { useState } from "react";
import {
  FileText, ArrowLeft, Loader2, FileJson, FileCode, Download,
} from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  listReports, getReportContent,
  type ReportSummary,
} from "@/lib/lab-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function ReportCard({ report }: { report: ReportSummary }) {
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);

  const mdFilename = report.filename.replace(".json", ".md");

  const handleView = async () => {
    setLoading(true);
    try {
      const data = await getReportContent(mdFilename);
      setContent(data.content);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadJson = async () => {
    const res = await fetch(`${API_URL}/api/lab/reports/${report.filename}`);
    if (res.ok) {
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = report.filename;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleDownloadMd = async () => {
    const res = await fetch(`${API_URL}/api/lab/reports/${mdFilename}`);
    if (res.ok) {
      const data = await res.json();
      const blob = new Blob([data.content], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = mdFilename;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-medium text-white">{report.name}</h3>
            <p className="text-sm text-gray-500">
              Run #{report.run_id} / {report.dataset}
            </p>
          </div>
          <div className="text-right">
            <div className={`text-lg font-bold ${
              report.correct_rate >= 70 ? "text-green-400" :
              report.correct_rate >= 40 ? "text-yellow-400" : "text-red-400"
            }`}>
              {report.correct_rate.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-600">correct</div>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2 text-xs text-gray-600">
          <span>Created: {new Date(report.created_at).toLocaleDateString()}</span>
          <span>/</span>
          <span>Exported: {new Date(report.exported_at).toLocaleString()}</span>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={handleView}
            disabled={loading}
            className="flex-1 px-3 py-2 text-sm bg-[#1a1a2e] hover:bg-[#252540] text-gray-300 rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            View
          </button>
          <button
            onClick={handleDownloadMd}
            className="px-3 py-2 text-sm bg-[#1a1a2e] hover:bg-[#252540] text-gray-300 rounded-lg flex items-center gap-1 transition-colors"
            title="Download Markdown"
          >
            <FileCode className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownloadJson}
            className="px-3 py-2 text-sm bg-[#1a1a2e] hover:bg-[#252540] text-gray-300 rounded-lg flex items-center gap-1 transition-colors"
            title="Download JSON"
          >
            <FileJson className="w-4 h-4" />
          </button>
        </div>
      </div>

      {content && (
        <div className="border-t border-[#1e1e2e] p-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-400">Report Preview</span>
            <button
              onClick={() => setContent(null)}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              Close
            </button>
          </div>
          <div className="bg-[#1a1a2e] border border-[#2a2a3e] rounded p-4 max-h-96 overflow-y-auto">
            <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">{content}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ["lab-reports"],
    queryFn: listReports,
  });

  const allReports = reports ?? [];

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FileText className="w-8 h-8 text-purple-400" />
          <div>
            <h1 className="text-xl font-bold text-white">Reports</h1>
            <p className="text-sm text-gray-500">Exported benchmark reports</p>
          </div>
        </div>

        {/* Reports List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
          </div>
        ) : allReports.length === 0 ? (
          <div className="text-center py-20">
            <FileText className="w-12 h-12 text-gray-700 mx-auto mb-4" />
            <h2 className="text-lg font-medium text-gray-400 mb-2">No reports yet</h2>
            <p className="text-gray-600 mb-6">
              Export a completed Lab run to create a report
            </p>
            <Link
              href="/lab"
              className="text-purple-400 hover:text-purple-300"
            >
              Go to Lab
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {allReports.map((report) => (
              <ReportCard key={report.filename} report={report} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
