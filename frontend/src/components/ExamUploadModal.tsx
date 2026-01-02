"use client";

/**
 * Exam Upload Modal Component
 * Centered modal for uploading sample exam papers.
 */
import { useState, useRef } from "react";
import { useExam } from "@/contexts/ExamContext";

interface ExamUploadModalProps {
    isOpen: boolean;
    onClose: () => void;
    sessionId: string;
}

export default function ExamUploadModal({
    isOpen,
    onClose,
    sessionId,
}: ExamUploadModalProps) {
    const { startExamGeneration } = useExam();
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    if (!isOpen) return null;

    const handleFileChange = (selectedFile: File) => {
        if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
            setError("Only PDF files are supported");
            return;
        }
        setFile(selectedFile);
        setError("");
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile) handleFileChange(droppedFile);
    };

    const handleGenerate = async () => {
        if (!file) {
            setError("Please upload a sample exam paper");
            return;
        }

        setUploading(true);
        setError("");

        try {
            await startExamGeneration(sessionId, file);
            // Close modal immediately - generation continues in background
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to start generation");
            setUploading(false);
        }
    };

    const handleClose = () => {
        if (!uploading) {
            setFile(null);
            setError("");
            onClose();
        }
    };

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 z-40"
                onClick={handleClose}
            />

            {/* Modal */}
            <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
                <div
                    className="bg-white rounded-lg shadow-xl w-full max-w-md"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b border-[#DFE1E6]">
                        <h2 className="text-lg font-semibold text-[#172B4D]">
                            Create Exam Paper
                        </h2>
                        <button
                            onClick={handleClose}
                            disabled={uploading}
                            className="text-[#6B778C] hover:text-[#172B4D] disabled:opacity-50"
                        >
                            <svg
                                className="w-5 h-5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M6 18L18 6M6 6l12 12"
                                />
                            </svg>
                        </button>
                    </div>

                    {/* Body */}
                    <div className="p-4 space-y-4">
                        <p className="text-sm text-[#6B778C]">
                            Upload a sample exam paper (PDF) to generate a practice exam based on your study material.
                        </p>

                        {/* Error message */}
                        {error && (
                            <div className="bg-[#FFEBE6] border border-[#FF8F73] text-[#DE350B] px-3 py-2 rounded text-sm">
                                {error}
                            </div>
                        )}

                        {/* Upload zone */}
                        <div
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${file
                                    ? "border-[#36B37E] bg-[#E3FCEF]"
                                    : "border-[#DFE1E6] hover:border-[#4C9AFF] hover:bg-[#F4F5F7]"
                                }`}
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) =>
                                    e.target.files?.[0] &&
                                    handleFileChange(e.target.files[0])
                                }
                            />

                            {file ? (
                                <div className="flex flex-col items-center">
                                    <div className="w-10 h-10 bg-[#36B37E] rounded-full flex items-center justify-center mb-2">
                                        <svg
                                            className="w-5 h-5 text-white"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                        >
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M5 13l4 4L19 7"
                                            />
                                        </svg>
                                    </div>
                                    <p className="text-[#172B4D] font-medium text-sm">
                                        {file.name}
                                    </p>
                                    <p className="text-xs text-[#6B778C] mt-1">
                                        Click to replace
                                    </p>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center">
                                    <div className="w-10 h-10 bg-[#F4F5F7] rounded-full flex items-center justify-center mb-2">
                                        <svg
                                            className="w-5 h-5 text-[#6B778C]"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                        >
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                            />
                                        </svg>
                                    </div>
                                    <p className="text-[#172B4D] font-medium text-sm">
                                        Drop sample paper or click to browse
                                    </p>
                                    <p className="text-xs text-[#6B778C] mt-1">
                                        PDF files only
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="flex justify-end gap-3 p-4 border-t border-[#DFE1E6]">
                        <button
                            onClick={handleClose}
                            disabled={uploading}
                            className="px-4 py-2 text-[#6B778C] hover:text-[#172B4D] font-medium text-sm disabled:opacity-50"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleGenerate}
                            disabled={!file || uploading}
                            className="px-4 py-2 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm flex items-center gap-2"
                        >
                            {uploading && (
                                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                            )}
                            {uploading ? "Starting..." : "Generate Paper"}
                        </button>
                    </div>
                </div>
            </div>
        </>
    );
}
