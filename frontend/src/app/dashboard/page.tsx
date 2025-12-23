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
}

export default function DashboardPage() {
    const { user, token, loading, signOut } = useAuth();
    const router = useRouter();
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loadingSessions, setLoadingSessions] = useState(true);
    const [newTitle, setNewTitle] = useState("");
    const [creating, setCreating] = useState(false);
    const [showModal, setShowModal] = useState(false);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    const loadSessions = useCallback(async () => {
        if (!token) return;
        try {
            const data = await api.getSessions(token);
            setSessions(data);
        } catch (error) {
            console.error("Failed to load sessions:", error);
        } finally {
            setLoadingSessions(false);
        }
    }, [token]);

    useEffect(() => {
        if (token) {
            loadSessions();
        }
    }, [token, loadSessions]);

    const createSession = async () => {
        if (!token || !newTitle.trim()) return;

        setCreating(true);
        try {
            const session = await api.createSession(token, newTitle.trim());
            setShowModal(false);
            setNewTitle("");
            router.push(`/study/${session.session_id}`);
        } catch (error) {
            console.error("Failed to create session:", error);
        } finally {
            setCreating(false);
        }
    };

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            created: "bg-[#E3FCEF] text-[#006644]",
            uploaded: "bg-[#DEEBFF] text-[#0747A6]",
            comprehending: "bg-[#FFFAE6] text-[#FF8B00]",
            ready: "bg-[#36B37E] text-white",
            quizzing: "bg-[#6554C0] text-white",
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
                            {sessions.map((session) => (
                                <Link
                                    key={session.session_id}
                                    href={`/study/${session.session_id}`}
                                    className="block bg-white rounded-lg border border-[#DFE1E6] p-4 hover:border-[#0052CC] transition-colors"
                                >
                                    <div className="flex items-start justify-between gap-3 mb-2">
                                        <h4 className="font-medium text-[#172B4D]">{session.title}</h4>
                                        {getStatusBadge(session.status)}
                                    </div>
                                    <p className="text-xs text-[#6B778C]">{formatDate(session.created_at)}</p>
                                </Link>
                            ))}
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
                                    {sessions.map((session) => (
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
                                            </td>
                                            <td className="px-4 py-4">
                                                {getStatusBadge(session.status)}
                                            </td>
                                            <td className="px-4 py-4 text-sm text-[#6B778C]">
                                                {formatDate(session.created_at)}
                                            </td>
                                            <td className="px-4 py-4 text-right">
                                                <Link
                                                    href={`/study/${session.session_id}`}
                                                    className="text-sm text-[#6B778C] hover:text-[#0052CC] transition-colors"
                                                >
                                                    Open
                                                </Link>
                                            </td>
                                        </tr>
                                    ))}
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
                        <div className="p-4 sm:p-6">
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
                        <div className="border-t border-[#DFE1E6] px-4 sm:px-6 py-4 flex flex-col-reverse sm:flex-row justify-end gap-2 sm:gap-3">
                            <button
                                onClick={() => {
                                    setShowModal(false);
                                    setNewTitle("");
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
