"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

interface Session {
    session_id: string;
    title: string;
    status: string;
    created_at: string;
    enable_spaced_repetition?: boolean;
}

interface SessionProgress {
    due_for_review: number;
    total_concepts: number;
    mastery_percentage: number;
}

interface GlobalProgress {
    total_due: number;
    total_concepts: number;
    overall_mastery_percentage: number;
}

export default function DashboardPage() {
    const { user, token, loading, signOut } = useAuth();
    const router = useRouter();
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loadingSessions, setLoadingSessions] = useState(true);
    const [loadingProgress, setLoadingProgress] = useState(true);
    const [newTitle, setNewTitle] = useState("");
    const [enableSpacedRepetition, setEnableSpacedRepetition] = useState(true);
    const [creating, setCreating] = useState(false);
    const [showModal, setShowModal] = useState(false);
    const [progressData, setProgressData] = useState<Record<string, SessionProgress>>({});
    const [globalProgress, setGlobalProgress] = useState<GlobalProgress | null>(null);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    // Phase 1: Load sessions list immediately (fast)
    const loadSessions = useCallback(async () => {
        if (!token) return;
        try {
            const sessionsData = await api.getSessions(token);
            setSessions(sessionsData);
        } catch (error) {
            console.error("Failed to load sessions:", error);
        } finally {
            setLoadingSessions(false);
        }
    }, [token]);

    // Phase 2: Load progress data in background (slower)
    const loadProgressData = useCallback(async () => {
        if (!token) return;
        try {
            const data = await api.getDashboardData(token);
            
            // Update sessions with fresh data
            setSessions(data.sessions);
            
            // Set global progress
            setGlobalProgress(data.global_progress);

            // Build progress map from sessions_progress
            const progressMap: Record<string, SessionProgress> = {};
            data.sessions_progress.forEach((session: { session_id: string; due_count: number; total: number; mastery_percentage: number; }) => {
                progressMap[session.session_id] = {
                    due_for_review: session.due_count,
                    total_concepts: session.total,
                    mastery_percentage: session.mastery_percentage,
                };
            });
            setProgressData(progressMap);
        } catch (error) {
            console.error("Failed to load progress data:", error);
        } finally {
            setLoadingProgress(false);
        }
    }, [token]);

    useEffect(() => {
        if (token) {
            // Load sessions first (fast), then progress (slower) in parallel
            loadSessions();
            loadProgressData();
        }
    }, [token, loadSessions, loadProgressData]);

    const deleteSession = async (sessionId: string) => {
        if (!token) return;

        if (!window.confirm("Are you sure you want to permanently delete this study session and all its data? This action cannot be undone.")) {
            return;
        }

        try {
            await api.deleteSession(token, sessionId);
            // Refresh all data to ensure global stats and sessions are synchronized
            await loadDashboardData();
        } catch (error) {
            console.error("Failed to delete session:", error);
            alert("Failed to delete session. Please try again.");
        }
    };

    const createSession = async () => {
        if (!token || !newTitle.trim()) return;

        setCreating(true);
        try {
            const session = await api.createSession(token, newTitle.trim(), undefined, enableSpacedRepetition);
            setShowModal(false);
            setNewTitle("");
            setEnableSpacedRepetition(true); // Reset to default
            router.push(`/study/${session.session_id}`);
        } catch (error) {
            console.error("Failed to create session:", error);
        } finally {
            setCreating(false);
        }
    };

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            created: "bg-[#DFE1E6] text-[#42526E]",
            uploaded: "bg-[#DEEBFF] text-[#0747A6]",
            comprehending: "bg-[#FFFAE6] text-[#974F0C]",
            ready: "bg-[#E3FCEF] text-[#006644]",
            quizzing: "bg-[#DEEBFF] text-[#0747A6]",
        };
        const labels: Record<string, string> = {
            created: "New",
            uploaded: "Uploaded",
            comprehending: "Analyzing",
            ready: "Ready",
            quizzing: "Active",
        };
        return (
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || "bg-[#F4F5F7] text-[#6B778C]"}`}>
                {labels[status] || status}
            </span>
        );
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    };

    if (loading || !user) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#FAFBFC]">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-[#0052CC] border-t-transparent"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#FAFBFC]">
            {/* Header */}
            <header className="bg-white border-b border-[#DFE1E6]">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 sm:gap-3">
                            <div className="w-8 h-8 bg-[#0052CC] rounded flex items-center justify-center">
                                <span className="text-white font-bold text-sm">GL</span>
                            </div>
                            <h1 className="text-lg font-semibold text-[#172B4D]">GoLearn</h1>
                        </div>
                        <div className="flex items-center gap-2 sm:gap-4">
                            <span className="text-sm text-[#6B778C] hidden sm:inline">{user.email}</span>
                            <button
                                onClick={signOut}
                                className="text-sm text-[#6B778C] hover:text-[#172B4D] transition-colors"
                            >
                                Sign out
                            </button>
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
                {/* Welcome Section */}
                <div className="mb-6 sm:mb-8">
                    <h2 className="text-xl sm:text-2xl font-semibold text-[#172B4D] mb-1 sm:mb-2">
                        Welcome back{user.displayName ? `, ${user.displayName.split(" ")[0]}` : ""}
                    </h2>
                    <p className="text-[#6B778C] text-sm sm:text-base">Your study sessions and progress</p>
                </div>

                {/* Global Review Center */}
                {globalProgress && globalProgress.total_due > 0 && (
                    <div className="mb-6 sm:mb-8">
                        <div className="bg-white rounded-lg border border-[#DFE1E6] p-6 sm:p-8">
                            <div className="flex items-start justify-between gap-4 mb-4">
                                <div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="w-8 h-8 bg-[#DEEBFF] rounded flex items-center justify-center">
                                            <svg className="w-5 h-5 text-[#0052CC]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        </div>
                                        <h3 className="text-lg sm:text-xl font-semibold text-[#172B4D]">Global Review</h3>
                                    </div>
                                    <p className="text-[#6B778C] text-sm sm:text-base">Review questions from all your sessions</p>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
                                <div className="bg-[#F4F5F7] rounded-lg p-4">
                                    <div className="text-2xl sm:text-3xl font-bold text-[#0052CC] mb-1">{globalProgress.total_due}</div>
                                    <div className="text-[#6B778C] text-xs sm:text-sm">Cards Due</div>
                                </div>
                                <div className="bg-[#F4F5F7] rounded-lg p-4">
                                    <div className="text-2xl sm:text-3xl font-bold text-[#172B4D] mb-1">{globalProgress.total_concepts}</div>
                                    <div className="text-[#6B778C] text-xs sm:text-sm">Total Cards</div>
                                </div>
                                <div className="col-span-2 sm:col-span-1 bg-[#F4F5F7] rounded-lg p-4">
                                    <div className="text-2xl sm:text-3xl font-bold text-[#36B37E] mb-1">{globalProgress.overall_mastery_percentage}%</div>
                                    <div className="text-[#6B778C] text-xs sm:text-sm">Mastery</div>
                                </div>
                            </div>
                            <Link
                                href="/quiz/global?mode=global"
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors w-full sm:w-auto"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                Start Global Review
                            </Link>
                        </div>
                    </div>
                )}

                {/* Actions */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-0 mb-4 sm:mb-6">
                    <h3 className="text-xs sm:text-sm font-semibold text-[#6B778C] uppercase tracking-wide">
                        Study Sessions
                    </h3>
                    <button
                        onClick={() => setShowModal(true)}
                        className="w-full sm:w-auto px-4 py-2 bg-[#0052CC] text-white text-sm font-medium rounded hover:bg-[#0747A6] transition-colors flex items-center justify-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        New Session
                    </button>
                </div>

                {/* Sessions List */}
                {loadingSessions ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0052CC] border-t-transparent mx-auto"></div>
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-[#F4F5F7] rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-6 h-6 sm:w-8 sm:h-8 text-[#6B778C]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                            </svg>
                        </div>
                        <h3 className="text-base sm:text-lg font-semibold text-[#172B4D] mb-2">No study sessions yet</h3>
                        <p className="text-[#6B778C] mb-6 text-sm">Create your first session to start learning</p>
                        <button
                            onClick={() => setShowModal(true)}
                            className="px-4 py-2 bg-[#0052CC] text-white text-sm font-medium rounded hover:bg-[#0747A6] transition-colors"
                        >
                            Create First Session
                        </button>
                    </div>
                ) : (
                    <>
                        {/* Mobile Cards View */}
                        <div className="sm:hidden space-y-3">
                            {sessions.map((session) => {
                                const progress = progressData[session.session_id];
                                const hasDue = session.enable_spaced_repetition !== false && progress && progress.due_for_review > 0;

                                return (
                                    <div key={session.session_id} className="bg-white rounded-lg border border-[#DFE1E6] p-4">
                                        <Link
                                            href={`/study/${session.session_id}`}
                                            className="block hover:opacity-80 transition-opacity"
                                        >
                                            <div className="flex items-start justify-between gap-3 mb-2">
                                                <div className="flex-1">
                                                    <h4 className="font-medium text-[#172B4D] mb-1">{session.title}</h4>
                                                    <div className="flex items-center gap-2">
                                                        {getStatusBadge(session.status)}
                                                        {session.enable_spaced_repetition === false && (
                                                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-[#F4F5F7] text-[#6B778C] flex items-center gap-1">
                                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                                                </svg>
                                                                No SR
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        e.stopPropagation();
                                                        deleteSession(session.session_id);
                                                    }}
                                                    className="p-1.5 text-[#6B778C] hover:text-[#DE350B] hover:bg-[#FFEBE6] rounded transition-colors"
                                                    title="Delete session"
                                                >
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                    </svg>
                                                </button>
                                            </div>
                                            <p className="text-xs text-[#6B778C]">{formatDate(session.created_at)}</p>
                                        </Link>
                                        {hasDue && (
                                            <div className="mt-3 pt-3 border-t border-[#DFE1E6] flex items-center justify-between gap-2">
                                                <span className="text-xs text-[#6B778C]">
                                                    {progress.due_for_review} card{progress.due_for_review !== 1 ? 's' : ''} due
                                                </span>
                                                <Link
                                                    href={`/quiz/${session.session_id}?mode=review`}
                                                    className="px-3 py-1.5 bg-[#DEEBFF] text-[#0747A6] rounded text-xs font-medium hover:bg-[#B3D4FF] transition-colors"
                                                >
                                                    Review Now
                                                </Link>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Desktop Table View */}
                        <div className="hidden sm:block bg-white rounded-lg border border-[#DFE1E6] overflow-hidden">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-[#DFE1E6] bg-[#FAFBFC]">
                                        <th className="text-left px-4 py-3 text-xs font-semibold text-[#6B778C] uppercase tracking-wide">
                                            Title
                                        </th>
                                        <th className="text-left px-4 py-3 text-xs font-semibold text-[#6B778C] uppercase tracking-wide">
                                            Status
                                        </th>
                                        <th className="text-left px-4 py-3 text-xs font-semibold text-[#6B778C] uppercase tracking-wide">
                                            Created
                                        </th>
                                        <th className="text-right px-4 py-3"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sessions.map((session) => {
                                        const progress = progressData[session.session_id];
                                        const hasDue = session.enable_spaced_repetition !== false && progress && progress.due_for_review > 0;

                                        return (
                                            <tr
                                                key={session.session_id}
                                                className="border-b border-[#DFE1E6] hover:bg-[#FAFBFC] transition-colors"
                                            >
                                                <td className="px-4 py-4">
                                                    <Link
                                                        href={`/study/${session.session_id}`}
                                                        className="text-[#0052CC] font-medium hover:underline"
                                                    >
                                                        {session.title}
                                                    </Link>
                                                    <div className="flex items-center gap-2 mt-1">
                                                        {hasDue && (
                                                            <div className="text-xs text-[#FF8B00]">
                                                                {progress.due_for_review} due for review
                                                            </div>
                                                        )}
                                                        {session.enable_spaced_repetition === false && (
                                                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-[#F4F5F7] text-[#6B778C] flex items-center gap-1">
                                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                                                </svg>
                                                                No Spaced Repetition
                                                            </span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    {getStatusBadge(session.status)}
                                                </td>
                                                <td className="px-4 py-4 text-sm text-[#6B778C]">
                                                    {formatDate(session.created_at)}
                                                </td>
                                                <td className="px-4 py-4 text-right">
                                                    <div className="flex items-center justify-end gap-4">
                                                        {hasDue && (
                                                            <Link
                                                                href={`/quiz/${session.session_id}?mode=review`}
                                                                className="px-3 py-1.5 bg-[#DEEBFF] text-[#0747A6] rounded text-xs font-medium hover:bg-[#B3D4FF] transition-colors"
                                                            >
                                                                Review
                                                            </Link>
                                                        )}
                                                        <Link
                                                            href={`/study/${session.session_id}`}
                                                            className="text-sm text-[#6B778C] hover:text-[#0052CC] transition-colors"
                                                        >
                                                            Open
                                                        </Link>
                                                        <button
                                                            onClick={() => deleteSession(session.session_id)}
                                                            className="p-1.5 text-[#6B778C] hover:text-[#DE350B] hover:bg-[#FFEBE6] rounded transition-colors"
                                                            title="Delete session"
                                                        >
                                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </main>

            {/* Create Session Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
                        <div className="border-b border-[#DFE1E6] px-4 sm:px-6 py-4">
                            <h3 className="text-lg font-semibold text-[#172B4D]">Create New Session</h3>
                        </div>
                        <div className="p-4 sm:p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-[#172B4D] mb-2">
                                    Session Title
                                </label>
                                <input
                                    type="text"
                                    value={newTitle}
                                    onChange={(e) => setNewTitle(e.target.value)}
                                    placeholder="e.g., Machine Learning Basics"
                                    className="w-full px-4 py-2.5 border border-[#DFE1E6] rounded focus:ring-2 focus:ring-[#4C9AFF] focus:border-transparent text-[#172B4D] placeholder-[#6B778C]"
                                    autoFocus
                                    onKeyDown={(e) => e.key === "Enter" && createSession()}
                                />
                            </div>
                            <div className="flex items-start gap-3">
                                <input
                                    type="checkbox"
                                    id="enableSpacedRepetition"
                                    checked={enableSpacedRepetition}
                                    onChange={(e) => setEnableSpacedRepetition(e.target.checked)}
                                    className="mt-0.5 w-4 h-4 text-[#0052CC] border-[#DFE1E6] rounded focus:ring-2 focus:ring-[#4C9AFF]"
                                />
                                <label htmlFor="enableSpacedRepetition" className="text-sm text-[#172B4D] cursor-pointer">
                                    <div className="font-medium">Enable spaced repetition</div>
                                    <div className="text-xs text-[#6B778C] mt-0.5">Generate quiz questions and track review progress for this session</div>
                                </label>
                            </div>
                        </div>
                        <div className="border-t border-[#DFE1E6] px-4 sm:px-6 py-4 flex flex-col-reverse sm:flex-row justify-end gap-2 sm:gap-3">
                            <button
                                onClick={() => {
                                    setShowModal(false);
                                    setNewTitle("");
                                    setEnableSpacedRepetition(true); // Reset to default
                                }}
                                className="w-full sm:w-auto px-4 py-2 text-sm font-medium text-[#6B778C] hover:text-[#172B4D] transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={createSession}
                                disabled={creating || !newTitle.trim()}
                                className="w-full sm:w-auto px-4 py-2 bg-[#0052CC] text-white text-sm font-medium rounded hover:bg-[#0747A6] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                            >
                                {creating && (
                                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                                )}
                                {creating ? "Creating..." : "Create"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
