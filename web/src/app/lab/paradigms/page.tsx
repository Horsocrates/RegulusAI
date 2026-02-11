"use client";

import { useState, useEffect } from "react";
import {
  ArrowLeft, BookOpen, Loader2, Save, ChevronDown,
  FileText, Eye, X, FolderOpen,
} from "lucide-react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listParadigms,
  listInstructionSetDirs,
  getInstructionSetDetail,
  getParadigmRoleInstructions,
  updateParadigmRoleInstructions,
  type ParadigmInfo,
  type InstructionSetSummary,
} from "@/lib/lab-api";

// Role definitions — default file per role
const AGENT_KEYS = [
  { key: "team_lead", label: "Team Lead", defaultFile: "analyze.md", icon: "\u25C6" },
  { key: "d1", label: "D1 \u2014 Recognition", defaultFile: "d1-recognize.md", icon: "\u2460" },
  { key: "d2", label: "D2 \u2014 Clarification", defaultFile: "d2-clarify.md", icon: "\u2461" },
  { key: "d3", label: "D3 \u2014 Framework", defaultFile: "d3-framework.md", icon: "\u2462" },
  { key: "d4", label: "D4 \u2014 Comparison", defaultFile: "d4-compare.md", icon: "\u2463" },
  { key: "d5", label: "D5 \u2014 Inference", defaultFile: "d5-infer.md", icon: "\u2464" },
  { key: "d6", label: "D6 \u2014 Reflection", defaultFile: "d6-reflect.md", icon: "\u2465" },
];

// Special key for storing the selected folder in the configs dict
const SET_KEY = "_instruction_set";

// ---------------------------------------------------------------------------
// Preview Modal
// ---------------------------------------------------------------------------

function PreviewModal({
  roleName,
  fileName,
  content,
  onClose,
}: {
  roleName: string;
  fileName: string;
  content: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-8">
      <div className="bg-[#12121a] border border-[#2a2a3e] rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-[#1e1e2e]">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white">{roleName}</h2>
            <span className="text-xs text-gray-500 font-mono">{fileName}</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <pre className="text-sm text-gray-300 font-mono whitespace-pre-wrap leading-relaxed">
            {content}
          </pre>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ParadigmsPage() {
  const queryClient = useQueryClient();

  // State
  const [selectedParadigm, setSelectedParadigm] = useState<string>("default");
  const [localConfigs, setLocalConfigs] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [previewRole, setPreviewRole] = useState<string | null>(null);

  // The selected instruction set folder
  const selectedSetId = localConfigs[SET_KEY] || "default";

  // Queries
  const { data: paradigms } = useQuery({
    queryKey: ["paradigms"],
    queryFn: listParadigms,
  });

  const { data: instructionSets } = useQuery({
    queryKey: ["instruction-sets"],
    queryFn: listInstructionSetDirs,
  });

  const { data: savedConfigs, isLoading: loadingConfigs } = useQuery({
    queryKey: ["paradigm-role-instructions", selectedParadigm],
    queryFn: () => getParadigmRoleInstructions(selectedParadigm),
    enabled: !!selectedParadigm,
  });

  // Fetch file list + content for the selected folder
  const { data: folderDetail } = useQuery({
    queryKey: ["instruction-set-detail", selectedSetId],
    queryFn: () => getInstructionSetDetail(selectedSetId),
    enabled: !!selectedSetId,
  });

  // Available files in the selected folder
  const availableFiles = folderDetail ? Object.keys(folderDetail.files).sort() : [];

  // Sync saved configs -> local state when loaded
  useEffect(() => {
    if (savedConfigs) {
      setLocalConfigs(savedConfigs);
      setDirty(false);
    }
  }, [savedConfigs]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: () => updateParadigmRoleInstructions(selectedParadigm, localConfigs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paradigm-role-instructions", selectedParadigm] });
      setDirty(false);
    },
  });

  const handleSwitchParadigm = (pid: string) => {
    setSelectedParadigm(pid);
    setDirty(false);
    setPreviewRole(null);
  };

  const handleFolderChange = (setId: string) => {
    setLocalConfigs((prev) => ({ ...prev, [SET_KEY]: setId }));
    setDirty(true);
  };

  const handleFileChange = (role: string, fileName: string) => {
    setLocalConfigs((prev) => ({ ...prev, [role]: fileName }));
    setDirty(true);
  };

  // Get file content for preview
  const getFileContent = (role: string): string => {
    const agent = AGENT_KEYS.find((a) => a.key === role);
    if (!agent || !folderDetail) return "";
    const fileName = localConfigs[role] || agent.defaultFile;
    return folderDetail.files?.[fileName] || "";
  };

  // Preview modal data
  const previewAgent = previewRole ? AGENT_KEYS.find((a) => a.key === previewRole) : null;
  const previewFileName = previewRole
    ? localConfigs[previewRole] || (previewAgent?.defaultFile ?? "")
    : "";
  const previewContent = previewRole ? getFileContent(previewRole) : "";

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e2e8f0] p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/lab" className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <BookOpen className="w-8 h-8 text-purple-400" />
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">Paradigm Instructions</h1>
            <p className="text-gray-500 text-sm">
              Select instruction set and assign files to each agent role per paradigm
            </p>
          </div>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!dirty || saveMutation.isPending}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            {saveMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save
          </button>
        </div>

        {/* Paradigm Tabs */}
        <div className="flex flex-wrap gap-2 mb-6">
          {(paradigms || []).map((p: ParadigmInfo) => (
            <button
              key={p.id}
              onClick={() => handleSwitchParadigm(p.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                selectedParadigm === p.id
                  ? "bg-purple-600 text-white"
                  : "bg-[#1a1a2e] text-gray-400 hover:bg-[#2a2a3e] hover:text-gray-200"
              }`}
              title={p.description}
            >
              {p.name}
            </button>
          ))}
        </div>

        {/* Loading */}
        {loadingConfigs ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
          </div>
        ) : (
          <>
            {/* Instruction Set Folder Selector */}
            <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 mb-6">
              <div className="flex items-center gap-3">
                <FolderOpen className="w-5 h-5 text-purple-400 shrink-0" />
                <div className="flex-1">
                  <div className="text-[10px] text-gray-500 font-semibold tracking-widest mb-1">
                    INSTRUCTION SET
                  </div>
                  <div className="relative">
                    <select
                      value={selectedSetId}
                      onChange={(e) => handleFolderChange(e.target.value)}
                      className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500 appearance-none pr-8"
                    >
                      {(instructionSets || []).map((s: InstructionSetSummary) => (
                        <option key={s.id} value={s.id}>
                          {s.id}/ — {s.name} ({s.file_count} files)
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                  </div>
                </div>
              </div>
              <div className="text-[10px] text-gray-600 mt-2 ml-8">
                Folder: <span className="font-mono text-gray-400">regulus/instructions/{selectedSetId}/</span>
                {availableFiles.length > 0 && (
                  <span className="ml-2">
                    · Files: {availableFiles.map((f) => (
                      <span key={f} className="font-mono text-gray-500 ml-1">{f}</span>
                    ))}
                  </span>
                )}
              </div>
            </div>

            {/* Team Lead note */}
            <div className="bg-amber-500/[0.06] border border-amber-500/15 rounded-lg p-3 mb-6">
              <div className="text-xs text-amber-400/80">
                {"\u25C6"} <strong>Team Lead</strong>: after determining the paradigm, loads the selected instruction files for each domain agent.
              </div>
            </div>

            {/* Role Cards — file selection per role */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              {AGENT_KEYS.map(({ key, label, defaultFile, icon }) => {
                const selectedFile = localConfigs[key] || defaultFile;
                const fileContent = folderDetail?.files?.[selectedFile] || "";
                const preview = fileContent.slice(0, 200).replace(/\n/g, " ");
                const lineCount = fileContent ? fileContent.split("\n").length : 0;
                const isDefault = !localConfigs[key] || localConfigs[key] === defaultFile;

                return (
                  <div
                    key={key}
                    className={`bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 transition-colors ${
                      key === "team_lead" ? "col-span-2" : ""
                    }`}
                  >
                    {/* Role header */}
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-base w-7 h-7 flex items-center justify-center rounded-md bg-purple-500/10 text-purple-400">
                        {icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-gray-200">{label}</div>
                      </div>
                      {!isDefault && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-purple-500/15 text-purple-400 rounded font-medium">
                          CUSTOM
                        </span>
                      )}
                    </div>

                    {/* File dropdown */}
                    <div className="flex items-center gap-2 mb-2">
                      <div className="relative flex-1">
                        <select
                          value={selectedFile}
                          onChange={(e) => handleFileChange(key, e.target.value)}
                          className="w-full bg-[#1a1a2e] border border-[#2a2a3e] rounded px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-purple-500 appearance-none pr-8"
                        >
                          {availableFiles.map((f) => (
                            <option key={f} value={f}>
                              {f}{f === defaultFile ? " (default)" : ""}
                            </option>
                          ))}
                        </select>
                        <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                      </div>
                      <button
                        onClick={() => setPreviewRole(key)}
                        disabled={!fileContent}
                        className="px-2.5 py-2 border border-[#2a2a3e] hover:bg-[#1a1a2e] disabled:opacity-30 text-gray-400 rounded text-xs flex items-center gap-1 transition-colors"
                        title="Preview instruction file"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View
                      </button>
                    </div>

                    {/* File preview */}
                    {fileContent ? (
                      <p className="text-[11px] text-gray-600 font-mono truncate">
                        {lineCount} lines · {preview}...
                      </p>
                    ) : (
                      <p className="text-[11px] text-gray-700 italic">
                        {availableFiles.length === 0 ? "Loading files..." : "File not found in this set"}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* Unsaved indicator */}
        {dirty && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-yellow-500/20 border border-yellow-500/40 text-yellow-300 px-4 py-2 rounded-full text-sm flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            Unsaved changes
          </div>
        )}

        {/* Preview Modal */}
        {previewRole && previewAgent && (
          <PreviewModal
            roleName={previewAgent.label}
            fileName={previewFileName}
            content={previewContent}
            onClose={() => setPreviewRole(null)}
          />
        )}
      </div>
    </main>
  );
}
