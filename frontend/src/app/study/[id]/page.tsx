"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useExam } from "@/contexts/ExamContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import PomodoroTimer from "@/components/PomodoroTimer";
import ExamUploadModal from "@/components/ExamUploadModal";

interface SessionData {
    session_id: string;
    title: string;
    status: string;
    enable_spaced_repetition?: boolean;  // New field
    pdf_filename?: string;
    exploration_result?: ExplorationResult;
    engagement_result?: EngagementResult;
    application_result?: ApplicationResult;
}

interface ExplorationResult {
    structural_overview?: string;
    summary?: string;
    key_topics?: string[];
    visual_elements?: string[];
}

// New interface for image captions
interface ImageCaption {
    image_index: number;
    caption: string;
    type: string;
    relevance: string;
    key_points: string[];
    has_image: boolean;
    image_url: string | null;
}

interface EngagementResult {
    summary?: string;
    detailed_analysis?: string;
    concept_explanations?: Record<string, string>;
    image_captions?: ImageCaption[];  // New format
    diagram_interpretations?: any;  // Legacy support
    definitions?: Record<string, string>;
    formulas?: Record<string, string>;
    examples?: string[];
    relationships?: string[];
    misconceptions?: string[];
    key_insights?: string[];
    // Catch-all for any additional fields
    [key: string]: any;
}

interface ApplicationResult {
    practical_applications?: string[];
    connections?: string[];
    critical_analysis?: string;
    study_focus?: string[];
    mental_models?: string[];
}

type TabType = "exploration" | "engagement" | "application";

export default function StudySessionPage() {
    const { user, token, loading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const sessionId = params.id as string;

    const [session, setSession] = useState<SessionData | null>(null);
    const [content, setContent] = useState("");
    const [comprehending, setComprehending] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState("");
    const [uploadedFile, setUploadedFile] = useState<string | null>(null);
    const [pdfFile, setPdfFile] = useState<File | null>(null); // Store actual PDF file
    const [activeTab, setActiveTab] = useState<TabType>("exploration");
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [showExamModal, setShowExamModal] = useState(false);

    // Exam generation context
    const { getExamStatus, refreshExamStatus } = useExam();
    const examStatus = getExamStatus(sessionId);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    useEffect(() => {
        if (token && sessionId) {
            loadSession();
            // Refresh exam status on mount
            refreshExamStatus(sessionId);
        }
    }, [token, sessionId, refreshExamStatus]);

    const loadSession = async () => {
        if (!token) return;
        try {
            const data = await api.getSession(token, sessionId);
            setSession(data as SessionData);
            if (data.pdf_filename) {
                setUploadedFile(data.pdf_filename);
            }
        } catch (error) {
            console.error("Failed to load session:", error);
            setError("Failed to load session");
        }
    };

    const handleFileUpload = async (file: File) => {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            setError("Only PDF files are supported");
            return;
        }

        // Just store the file, don't upload to server yet
        setPdfFile(file);
        setUploadedFile(file.name);
        setError("");
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (file) handleFileUpload(file);
    };

    const runComprehension = async () => {
        if (!token || (!content.trim() && !pdfFile)) {
            setError("Please upload a PDF or paste your study content");
            return;
        }

        setComprehending(true);
        setError("");

        try {
            // Send PDF file directly with comprehension request
            const result = await api.runComprehension(
                token,
                sessionId,
                content || undefined,
                pdfFile || undefined
            );
            setSession((prev) =>
                prev
                    ? {
                        ...prev,
                        status: result.status,
                        exploration_result: result.exploration as ExplorationResult,
                        engagement_result: result.engagement as EngagementResult,
                        application_result: result.application as ApplicationResult,
                    }
                    : null
            );
        } catch (error) {
            console.error("Comprehension failed:", error);
            setError("Comprehension failed. Please try again.");
        } finally {
            setComprehending(false);
        }
    };

    if (loading || !user) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#FAFBFC]">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-[#0052CC] border-t-transparent"></div>
            </div>
        );
    }

    const hasResults = session?.status === "ready" || session?.status === "quizzing";

    const tabs = [
        { id: "exploration" as TabType, label: "Exploration", num: 1 },
        { id: "engagement" as TabType, label: "Engagement", num: 2 },
        { id: "application" as TabType, label: "Application", num: 3 },
    ];

    return (
        <div className="min-h-screen bg-[#FAFBFC]">
            {/* Header */}
            <header className="bg-white border-b border-[#DFE1E6] sticky top-0 z-10">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                            <Link
                                href="/dashboard"
                                className="text-[#6B778C] hover:text-[#172B4D] transition-colors text-sm font-medium flex-shrink-0"
                            >
                                <span className="hidden sm:inline">← Back to Dashboard</span>
                                <span className="sm:hidden">← Back</span>
                            </Link>
                            <span className="text-[#DFE1E6] hidden sm:inline">|</span>
                            <h1 className="text-base sm:text-lg font-semibold text-[#172B4D] truncate">
                                {session?.title || "Loading..."}
                            </h1>
                        </div>
                        {/* Timer and Quiz/Exam buttons - visible on all tabs when results exist */}
                        {hasResults && (
                            <div className="flex items-center gap-3">
                                <PomodoroTimer autoStart={true} />
                                <Link
                                    href={`/quiz/${sessionId}`}
                                    className="px-4 py-2 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors text-sm text-center whitespace-nowrap"
                                >
                                    Start Quiz
                                </Link>

                                {/* Exam button with dynamic states */}
                                {examStatus.status === "generating" ? (
                                    <button
                                        disabled
                                        className="px-4 py-2 bg-[#F4F5F7] text-[#6B778C] border border-[#DFE1E6] rounded font-medium text-sm text-center whitespace-nowrap flex items-center gap-2 cursor-not-allowed"
                                    >
                                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-[#0052CC] border-t-transparent" />
                                        Generating...
                                    </button>
                                ) : examStatus.status === "ready" && examStatus.pdfUrl ? (
                                    <a
                                        href={examStatus.pdfUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="px-4 py-2 bg-[#36B37E] text-white rounded font-medium hover:bg-[#2E9E6E] transition-colors text-sm text-center whitespace-nowrap flex items-center gap-2"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                        Download Paper
                                    </a>
                                ) : examStatus.status === "error" ? (
                                    <button
                                        onClick={() => setShowExamModal(true)}
                                        className="px-4 py-2 bg-[#FFEBE6] text-[#DE350B] border border-[#FF8F73] rounded font-medium hover:bg-[#FFD5CC] transition-colors text-sm text-center whitespace-nowrap"
                                    >
                                        Retry Exam
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => setShowExamModal(true)}
                                        className="px-4 py-2 bg-white text-[#0052CC] border border-[#0052CC] rounded font-medium hover:bg-[#DEEBFF] transition-colors text-sm text-center whitespace-nowrap"
                                    >
                                        Create Exam
                                    </button>
                                )}

                                <Link href={`/study/${sessionId}/feynman`} className="px-6 py-3 bg-white text-[#403294] border border-[#403294] rounded font-medium hover:bg-[#F4F5F7] transition-colors text-sm min-w-[160px]">
                            Learn with Feynman
                        </Link>
                            </div>
                        )}
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
                {error && (
                    <div className="bg-[#FFEBE6] border border-[#FF8F73] text-[#DE350B] px-4 py-3 rounded mb-6 text-sm">
                        {error}
                    </div>
                )}

                {/* Input Section */}
                {(session?.status === "created" || session?.status === "uploaded") && (
                    <div className="space-y-4 sm:space-y-6">
                        {/* PDF Upload */}
                        <div className="bg-white rounded-lg border border-[#DFE1E6] p-4 sm:p-6">
                            <h2 className="text-base font-semibold text-[#172B4D] mb-4">
                                Upload Study Material
                            </h2>
                            <div
                                onDragOver={(e) => e.preventDefault()}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                                className={`border-2 border-dashed rounded-lg p-6 sm:p-10 text-center cursor-pointer transition-all ${uploading
                                    ? "border-[#4C9AFF] bg-[#DEEBFF]"
                                    : uploadedFile
                                        ? "border-[#36B37E] bg-[#E3FCEF]"
                                        : "border-[#DFE1E6] hover:border-[#4C9AFF] hover:bg-[#F4F5F7]"
                                    }`}
                            >
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pdf"
                                    className="hidden"
                                    onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                                />
                                {uploading ? (
                                    <div className="flex flex-col items-center">
                                        <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0052CC] border-t-transparent mb-3"></div>
                                        <p className="text-[#0052CC] font-medium">Uploading...</p>
                                    </div>
                                ) : uploadedFile ? (
                                    <div className="flex flex-col items-center">
                                        <div className="w-10 h-10 sm:w-12 sm:h-12 bg-[#36B37E] rounded-full flex items-center justify-center mb-3">
                                            <svg className="w-5 h-5 sm:w-6 sm:h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                        <p className="text-[#172B4D] font-medium text-sm sm:text-base">{uploadedFile}</p>
                                        <p className="text-xs sm:text-sm text-[#6B778C] mt-1">Click to replace</p>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center">
                                        <div className="w-10 h-10 sm:w-12 sm:h-12 bg-[#F4F5F7] rounded-full flex items-center justify-center mb-3">
                                            <svg className="w-5 h-5 sm:w-6 sm:h-6 text-[#6B778C]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                            </svg>
                                        </div>
                                        <p className="text-[#172B4D] font-medium text-sm sm:text-base">Drop your PDF here or click to browse</p>
                                        <p className="text-xs sm:text-sm text-[#6B778C] mt-1">PDF files up to 20MB</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Text Input */}
                        <div className="bg-white rounded-lg border border-[#DFE1E6] p-4 sm:p-6">
                            <h2 className="text-base font-semibold text-[#172B4D] mb-4">
                                Or paste text content
                            </h2>
                            <textarea
                                value={content}
                                onChange={(e) => setContent(e.target.value)}
                                placeholder="Paste your study notes, textbook content, or article here..."
                                className="w-full h-32 sm:h-40 px-3 sm:px-4 py-3 rounded border border-[#DFE1E6] focus:ring-2 focus:ring-[#4C9AFF] focus:border-transparent resize-none text-[#172B4D] placeholder-[#6B778C] text-sm"
                            />
                        </div>

                        {/* Run Analysis Button */}
                        <div className="flex justify-end">
                            <button
                                onClick={runComprehension}
                                disabled={comprehending || (!content.trim() && !uploadedFile)}
                                className="w-full sm:w-auto px-6 py-3 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                            >
                                {comprehending && (
                                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                                )}
                                {comprehending ? "Analyzing..." : "Run Three-Pass Analysis"}
                            </button>
                        </div>
                    </div>
                )}

                {/* Comprehending State */}
                {session?.status === "comprehending" && (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <div className="animate-spin rounded-full h-10 w-10 sm:h-12 sm:w-12 border-2 border-[#0052CC] border-t-transparent mx-auto mb-4"></div>
                        <h2 className="text-base sm:text-lg font-semibold text-[#172B4D]">Analyzing your content...</h2>
                        <p className="text-[#6B778C] mt-2 text-sm">Running exploration, engagement, and application passes</p>
                    </div>
                )}

                {/* Results Section with Tabs */}
                {hasResults && (
                    <div className="space-y-4 sm:space-y-6">
                        {/* Tabs */}
                        <div className="bg-white rounded-lg border border-[#DFE1E6]">
                            <div className="border-b border-[#DFE1E6] overflow-x-auto">
                                <nav className="flex min-w-max">
                                    {tabs.map((tab) => (
                                        <button
                                            key={tab.id}
                                            onClick={() => setActiveTab(tab.id)}
                                            className={`flex items-center gap-2 px-4 sm:px-6 py-3 sm:py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === tab.id
                                                ? "border-[#0052CC] text-[#0052CC]"
                                                : "border-transparent text-[#6B778C] hover:text-[#172B4D] hover:border-[#DFE1E6]"
                                                }`}
                                        >
                                            <span className="w-5 h-5 rounded-full bg-current/10 text-xs flex items-center justify-center font-bold">{tab.num}</span>
                                            <span className="hidden sm:inline">{tab.label}</span>
                                            <span className="sm:hidden">{tab.label.slice(0, 3)}</span>
                                        </button>
                                    ))}
                                </nav>
                            </div>

                            {/* Tab Content */}
                            <div className="p-4 sm:p-6">
                                {activeTab === "exploration" && session.exploration_result && (
                                    <ExplorationTab data={session.exploration_result} />
                                )}
                                {activeTab === "engagement" && session.engagement_result && (
                                    <EngagementTab data={session.engagement_result} />
                                )}
                                {activeTab === "application" && session.application_result && (
                                    <ApplicationTab data={session.application_result} sessionId={sessionId} />
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </main>

            {/* Exam Upload Modal */}
            <ExamUploadModal
                isOpen={showExamModal}
                onClose={() => setShowExamModal(false)}
                sessionId={sessionId}
            />
        </div>
    );
}

// === Tab Components ===

function ExplorationTab({ data }: { data: ExplorationResult }) {
    console.log("ExplorationTab received:", data);

    // Helper to safely render any value
    const renderValue = (value: any): string => {
        if (typeof value === 'string') return value;
        if (typeof value === 'number') return String(value);
        if (value === null || value === undefined) return '';
        if (typeof value === 'object') {
            if ('explanation' in value) return String(value.explanation);
            if ('text' in value) return String(value.text);
            return JSON.stringify(value, null, 2);
        }
        return String(value);
    };

    // Check if parsing failed on backend
    if ((data as any).parse_error || (data as any).raw_response) {
        return (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-semibold text-yellow-800 mb-2">Raw Response (Parsing Issue)</h3>
                <pre className="text-sm text-yellow-700 whitespace-pre-wrap overflow-auto max-h-96">
                    {(data as any).raw_response || JSON.stringify(data, null, 2)}
                </pre>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Summary */}
            {data.summary && (
                <div className="bg-[#DEEBFF] rounded-lg p-4 sm:p-5">
                    <h3 className="text-xs sm:text-sm font-semibold text-[#0747A6] mb-2 uppercase tracking-wide">Summary</h3>
                    <p className="text-[#172B4D] text-sm sm:text-base whitespace-pre-wrap">{renderValue(data.summary)}</p>
                </div>
            )}

            {/* Structure */}
            {data.structural_overview && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-3 uppercase tracking-wide">Document Structure</h3>
                    <p className="text-[#172B4D] leading-relaxed text-sm sm:text-base">{data.structural_overview}</p>
                </div>
            )}

            {/* Key Topics */}
            {data.key_topics && data.key_topics.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-3 uppercase tracking-wide">Key Topics</h3>
                    <div className="flex flex-wrap gap-2">
                        {data.key_topics.map((topic, i) => (
                            <span
                                key={i}
                                className="px-3 py-1.5 bg-[#F4F5F7] text-[#172B4D] rounded-full text-xs sm:text-sm font-medium"
                            >
                                {topic}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Visual Elements */}
            {data.visual_elements && data.visual_elements.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-3 uppercase tracking-wide">Visual Elements</h3>
                    <ul className="space-y-2">
                        {data.visual_elements.map((elem, i) => (
                            <li key={i} className="flex items-start gap-2 text-[#172B4D] text-sm">
                                <span className="text-[#6B778C]">•</span>
                                {elem}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

function EngagementTab({ data }: { data: EngagementResult }) {
    console.log("EngagementTab received:", data);

    // Helper to safely render any value (string, object, array)
    const renderValue = (value: any): string => {
        if (typeof value === 'string') return value;
        if (typeof value === 'number') return String(value);
        if (value === null || value === undefined) return '';
        if (typeof value === 'object') {
            if ('explanation' in value) return String(value.explanation);
            if ('formula' in value) return String(value.formula);
            if ('text' in value) return String(value.text);
            if ('content' in value) return String(value.content);
            return JSON.stringify(value, null, 2);
        }
        return String(value);
    };

    // Check if parsing failed on backend
    if ((data as any).parse_error || (data as any).raw_response) {
        return (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-semibold text-yellow-800 mb-2">Raw Response (Parsing Issue)</h3>
                <pre className="text-sm text-yellow-700 whitespace-pre-wrap overflow-auto max-h-96">
                    {(data as any).raw_response || JSON.stringify(data, null, 2)}
                </pre>
            </div>
        );
    }

    // Define standard fields with custom rendering
    const standardFields = new Set([
        'summary', 'detailed_analysis', 'concept_explanations', 'image_captions', 'diagram_interpretations',
        'definitions', 'formulas', 'examples', 'relationships', 'misconceptions', 'key_insights'
    ]);

    // Find any additional fields the agent returned
    const additionalFields = Object.entries(data).filter(([key]) => !standardFields.has(key));

    return (
        <div className="space-y-6 sm:space-y-8">
            {/* Summary */}
            {data.summary && (
                <div className="bg-[#DEEBFF] rounded-lg p-4 sm:p-5">
                    <h3 className="text-xs sm:text-sm font-semibold text-[#0747A6] mb-2 uppercase tracking-wide">Engagement Summary</h3>
                    <p className="text-[#172B4D] text-sm sm:text-base leading-relaxed whitespace-pre-wrap">{renderValue(data.summary)}</p>
                </div>
            )}

            {/* Detailed Analysis */}
            {data.detailed_analysis && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-3 uppercase tracking-wide">Detailed Analysis</h3>
                    <div className="bg-[#F4F5F7] rounded-lg p-4 sm:p-5">
                        <p className="text-[#172B4D] text-sm leading-relaxed whitespace-pre-wrap">{renderValue(data.detailed_analysis)}</p>
                    </div>
                </div>
            )}

            {/* Image Captions */}
            {data.image_captions && data.image_captions.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Visual Elements & Diagrams</h3>
                    <div className="space-y-6">
                        {data.image_captions.map((imageCaption, i) => (
                            <div key={i} className="bg-[#E3FCEF] rounded-lg p-4 sm:p-5 border-l-4 border-[#36B37E]">
                                <div className="flex items-start justify-between mb-3">
                                    <h4 className="font-semibold text-[#172B4D] text-sm sm:text-base flex items-center gap-2">
                                        <svg className="w-4 h-4 text-[#36B37E]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                        Figure {imageCaption.image_index + 1}
                                    </h4>
                                    <div className="flex gap-2">
                                        <span className="px-2 py-1 bg-white rounded text-xs font-medium text-[#6B778C]">
                                            {imageCaption.type}
                                        </span>
                                        <span className={`px-2 py-1 rounded text-xs font-medium ${imageCaption.relevance === 'high' ? 'bg-[#DE350B] text-white' :
                                            imageCaption.relevance === 'medium' ? 'bg-[#FFAB00] text-white' :
                                                'bg-[#6B778C] text-white'
                                            }`}>
                                            {imageCaption.relevance}
                                        </span>
                                    </div>
                                </div>
                                {imageCaption.has_image && imageCaption.image_url && (
                                    <div className="mb-4">
                                        <img
                                            src={imageCaption.image_url}
                                            alt={`Figure ${imageCaption.image_index + 1}`}
                                            className="max-w-full h-auto rounded-lg shadow-md border border-gray-200"
                                            style={{ maxHeight: '400px', objectFit: 'contain' }}
                                        />
                                    </div>
                                )}
                                <p className="text-[#172B4D] text-xs sm:text-sm leading-relaxed mb-3">{imageCaption.caption}</p>
                                {imageCaption.key_points && imageCaption.key_points.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-[#36B37E]/20">
                                        <p className="text-xs font-semibold text-[#6B778C] mb-2">Key Points:</p>
                                        <ul className="space-y-1">
                                            {imageCaption.key_points.map((point, idx) => (
                                                <li key={idx} className="flex items-start gap-2 text-xs text-[#172B4D]">
                                                    <span className="text-[#36B37E] mt-0.5">•</span>
                                                    <span>{point}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Concept Explanations */}
            {data.concept_explanations && Object.keys(data.concept_explanations).length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Concept Explanations</h3>
                    <div className="space-y-4">
                        {Object.entries(data.concept_explanations).map(([concept, explanation], i) => (
                            <div key={i} className="border-l-4 border-[#0052CC] pl-4 py-2">
                                <h4 className="font-semibold text-[#172B4D] mb-1 text-sm sm:text-base">{concept}</h4>
                                <p className="text-[#42526E] text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">{renderValue(explanation)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Definitions */}
            {data.definitions && Object.keys(data.definitions).length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Definitions</h3>
                    <div className="bg-[#F4F5F7] rounded-lg divide-y divide-[#DFE1E6]">
                        {Object.entries(data.definitions).map(([term, definition], i) => (
                            <div key={i} className="px-3 sm:px-4 py-3 text-sm">
                                <span className="font-semibold text-[#172B4D]">{term}:</span>
                                <span className="text-[#42526E] ml-2">{renderValue(definition)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Formulas */}
            {data.formulas && Object.keys(data.formulas).length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Formulas & Equations</h3>
                    <div className="space-y-3">
                        {Object.entries(data.formulas).map(([name, formula], i) => (
                            <div key={i} className="bg-[#F4F5F7] rounded-lg p-4">
                                <h4 className="font-semibold text-[#172B4D] mb-2 text-sm">{name}</h4>
                                <code className="block bg-white px-3 py-2 rounded border border-[#DFE1E6] text-[#0052CC] font-mono text-xs sm:text-sm overflow-x-auto whitespace-pre-wrap">
                                    {renderValue(formula)}
                                </code>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Relationships */}
            {data.relationships && data.relationships.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Concept Relationships</h3>
                    <div className="space-y-2">
                        {data.relationships.map((relationship, i) => (
                            <div key={i} className="flex items-start gap-3 bg-[#EAE6FF] rounded-lg p-3 sm:p-4">
                                <svg className="w-4 h-4 text-[#6554C0] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                <p className="text-[#172B4D] text-xs sm:text-sm">{renderValue(relationship)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Examples */}
            {data.examples && data.examples.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Examples</h3>
                    <div className="space-y-3">
                        {data.examples.map((example, i) => (
                            <div key={i} className="flex items-start gap-3 bg-[#E3FCEF] rounded-lg p-3 sm:p-4">
                                <span className="text-[#36B37E] font-bold flex-shrink-0">→</span>
                                <p className="text-[#172B4D] text-xs sm:text-sm whitespace-pre-wrap">{renderValue(example)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
            {/* Misconceptions */}
            {data.misconceptions && data.misconceptions.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Common Misconceptions</h3>
                    <div className="space-y-3">
                        {data.misconceptions.map((misconception, i) => (
                            <div key={i} className="flex items-start gap-3 bg-[#FFEBE6] rounded-lg p-3 sm:p-4 border-l-4 border-[#DE350B]">
                                <svg className="w-4 h-4 text-[#DE350B] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <p className="text-[#172B4D] text-xs sm:text-sm">{renderValue(misconception)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Key Insights */}
            {data.key_insights && data.key_insights.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Key Insights</h3>
                    <div className="grid gap-3">
                        {data.key_insights.map((insight, i) => (
                            <div key={i} className="flex items-start gap-3 bg-[#FFFAE6] rounded-lg p-3 sm:p-4">
                                <svg className="w-4 h-4 text-[#FFAB00] flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                </svg>
                                <p className="text-[#172B4D] text-xs sm:text-sm">{renderValue(insight)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Dynamic Additional Fields */}
            {additionalFields.length > 0 && additionalFields.map(([key, value]) => {
                if (!value) return null;

                return (
                    <div key={key}>
                        <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">
                            {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </h3>
                        {typeof value === 'string' ? (
                            <div className="bg-[#F4F5F7] rounded-lg p-4">
                                <p className="text-[#172B4D] text-sm whitespace-pre-wrap">{value}</p>
                            </div>
                        ) : Array.isArray(value) ? (
                            <div className="space-y-2">
                                {value.map((item, i) => (
                                    <div key={i} className="flex items-start gap-2 bg-[#F4F5F7] rounded p-3">
                                        <span className="text-[#6B778C]">•</span>
                                        <p className="text-[#172B4D] text-sm">{renderValue(item)}</p>
                                    </div>
                                ))}
                            </div>
                        ) : typeof value === 'object' ? (
                            <div className="space-y-2">
                                {Object.entries(value).map(([k, v], i) => (
                                    <div key={i} className="bg-[#F4F5F7] rounded p-3">
                                        <span className="font-semibold text-[#172B4D]">{k}:</span>
                                        <span className="text-[#42526E] ml-2">{renderValue(v)}</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-[#172B4D] text-sm">{String(value)}</p>
                        )}
                    </div>
                );
            })}
        </div>
    );
}

function ApplicationTab({ data, sessionId }: { data: ApplicationResult; sessionId: string }) {
    console.log("ApplicationTab received:", data);

    // Helper to safely render any value
    const renderValue = (value: any): string => {
        if (typeof value === 'string') return value;
        if (typeof value === 'number') return String(value);
        if (value === null || value === undefined) return '';
        if (typeof value === 'object') {
            if ('explanation' in value) return String(value.explanation);
            if ('text' in value) return String(value.text);
            return JSON.stringify(value, null, 2);
        }
        return String(value);
    };

    // Check if parsing failed on backend
    if ((data as any).parse_error || (data as any).raw_response) {
        return (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-semibold text-yellow-800 mb-2">Raw Response (Parsing Issue)</h3>
                <pre className="text-sm text-yellow-700 whitespace-pre-wrap overflow-auto max-h-96">
                    {(data as any).raw_response || JSON.stringify(data, null, 2)}
                </pre>
            </div>
        );
    }

    return (
        <div className="space-y-6 sm:space-y-8">
            {/* Practical Applications */}
            {data.practical_applications && data.practical_applications.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Practical Applications</h3>
                    <div className="grid gap-3">
                        {data.practical_applications.map((app, i) => (
                            <div key={i} className="flex items-start gap-3 p-3 sm:p-4 bg-[#F4F5F7] rounded-lg">
                                <span className="w-5 h-5 sm:w-6 sm:h-6 bg-[#0052CC] text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                                    {i + 1}
                                </span>
                                <p className="text-[#172B4D] text-xs sm:text-sm whitespace-pre-wrap">{renderValue(app)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Connections */}
            {data.connections && data.connections.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Connections to Other Topics</h3>
                    <div className="flex flex-wrap gap-2">
                        {data.connections.map((conn, i) => (
                            <span key={i} className="px-3 py-2 bg-[#EAE6FF] text-[#403294] rounded text-xs sm:text-sm">
                                {renderValue(conn)}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Critical Analysis */}
            {data.critical_analysis && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Critical Analysis</h3>
                    <div className="bg-[#F4F5F7] rounded-lg p-4 sm:p-5">
                        <p className="text-[#172B4D] leading-relaxed text-sm whitespace-pre-wrap">{renderValue(data.critical_analysis)}</p>
                    </div>
                </div>
            )}

            {/* Study Focus */}
            {data.study_focus && data.study_focus.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Areas to Focus On</h3>
                    <ul className="space-y-2">
                        {data.study_focus.map((focus, i) => (
                            <li key={i} className="flex items-center gap-3 text-[#172B4D] text-sm">
                                <span className="w-2 h-2 bg-[#FF5630] rounded-full flex-shrink-0"></span>
                                {renderValue(focus)}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Mental Models */}
            {data.mental_models && data.mental_models.length > 0 && (
                <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] mb-4 uppercase tracking-wide">Memory Aids</h3>
                    <div className="grid gap-3">
                        {data.mental_models.map((model, i) => (
                            <div key={i} className="flex items-start gap-3 p-3 sm:p-4 border border-[#DFE1E6] rounded-lg">
                                <svg className="w-4 h-4 text-[#6B778C] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                                <p className="text-[#172B4D] text-xs sm:text-sm whitespace-pre-wrap">{renderValue(model)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Start Quiz CTA */}
            <div className="mt-6 sm:mt-8 pt-6 border-t border-[#DFE1E6]">
                <div className="bg-[#DEEBFF] rounded-lg p-4 sm:p-6 text-center">
                    <h3 className="text-base sm:text-lg font-semibold text-[#0747A6] mb-2">Ready to test your knowledge?</h3>
                    <p className="text-[#42526E] mb-4 text-xs sm:text-sm">Take a quiz based on the material you just studied.</p>
                    <Link
                        href={`/quiz/${sessionId}`}
                        className="inline-block px-6 py-3 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors text-sm"
                    >
                        Start Quiz
                    </Link>
                </div>
            </div>
        </div>
    );
}
