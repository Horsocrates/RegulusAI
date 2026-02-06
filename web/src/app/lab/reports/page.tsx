"use client";

import { useState, useEffect } from "react";
import { FileText, ArrowLeft, Download, Loader2, FileJson, FileCode } from "lucide-react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReportSummary {
  filename: string;
  run_id: number;
  name: string;
  dataset: string;
  created_at: string;
  exported_at: string;
  correct_rate: number;
}

function ReportCard({ report }: { report: ReportSummary }) {
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);

  const isJson = report.filename.endsWith(".json");
  const mdFilename = report.filename.replace(".json", ".md");

  const handleView = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/lab/reports/${mdFilename}`);
      if (res.ok) {
        const data = await res.json();
        setContent(data.content);
      }
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
    <div className="bg-white border rounded-lg overflow-hidden">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-medium text-gray-900">{report.name}</h3>
            <p className="text-sm text-gray-500">
              Run #{report.run_id} / {report.dataset}
            </p>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold text-blue-600">{report.correct_rate.toFixed(1)}%</div>
            <div className="text-xs text-gray-400">correct</div>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
          <span>Created: {new Date(report.created_at).toLocaleDateString()}</span>
          <span>/</span>
          <span>Exported: {new Date(report.exported_at).toLocaleString()}</span>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={handleView}
            disabled={loading}
            className="flex-1 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            View
          </button>
          <button
            onClick={handleDownloadMd}
            className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center gap-1"
            title="Download Markdown"
          >
            <FileCode className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownloadJson}
            className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center gap-1"
            title="Download JSON"
          >
            <FileJson className="w-4 h-4" />
          </button>
        </div>
      </div>

      {content && (
        <div className="border-t bg-gray-50 p-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">Report Preview</span>
            <button
              onClick={() => setContent(null)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Close
            </button>
          </div>
          <div className="bg-white border rounded p-4 max-h-96 overflow-y-auto">
            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{content}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const res = await fetch(`${API_URL}/api/lab/reports`);
        if (res.ok) {
          const data = await res.json();
          setReports(data);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchReports();
  }, []);

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/lab" className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FileText className="w-8 h-8 text-purple-600" />
          <div>
            <h1 className="text-xl font-bold">Reports</h1>
            <p className="text-sm text-gray-500">Exported benchmark reports</p>
          </div>
        </div>

        {/* Reports List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
          </div>
        ) : reports.length === 0 ? (
          <div className="bg-white border rounded-lg p-12 text-center">
            <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <h2 className="text-xl font-medium text-gray-700 mb-2">No reports yet</h2>
            <p className="text-gray-500 mb-4">
              Export a completed Lab run to create a report
            </p>
            <Link
              href="/lab"
              className="text-purple-600 hover:underline"
            >
              Go to Lab
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {reports.map((report) => (
              <ReportCard key={report.filename} report={report} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
