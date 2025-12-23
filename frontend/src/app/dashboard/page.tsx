"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    useEffect(() => {
        if (token) {
            loadSessions();
        }
    }, [token]);

    const loadSessions = async () => {
        if (!token) return;
        try {
            const data = await api.getSessions(token);
            setSessions(data);
        } catch (error) {
            console.error("Failed to load sessions:", error);
        } finally {
            setLoadingSessions(false);
        }
    };

    const createSession = async () => {
        if (!token || !newTitle.trim()) return;

        setCreating(true);
        try {
            const session = await api.createSession(token, newTitle);
            router.push(`/study/${session.session_id}`);
        } catch (error) {
            console.error("Failed to create session:", error);
        } finally {
            setCreating(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "ready":
                return "bg-green-100 text-green-800";
            case "comprehending":
                return "bg-yellow-100 text-yellow-800";
            case "quizzing":
                return "bg-purple-100 text-purple-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    if (loading || !user) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            {/* Header */}
            <header className="bg-white dark:bg-gray-800 shadow">
                <div className="container mx-auto px-4 py-4 flex items-center justify-between">
                    <h1 className="text-2xl font-bold text-indigo-600">GoLearn</h1>
                    <div className="flex items-center gap-4">
                        <span className="text-gray-600 dark:text-gray-300">
                            {user.email}
                        </span>
                        <button
                            onClick={signOut}
                            className="text-sm text-gray-500 hover:text-gray-700"
                        >
                            Sign Out
                        </button>
                    </div>
                </div>
            </header>

            <main className="container mx-auto px-4 py-8">
                {/* New Session */}
                <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-8">
                    <h2 className="text-xl font-semibold mb-4 text-gray-800 dark:text-white">
                        Start a New Study Session
                    </h2>
                    <div className="flex gap-4">
                        <input
                            type="text"
                            placeholder="Enter study topic (e.g., Machine Learning Basics)"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                            onKeyDown={(e) => e.key === "Enter" && createSession()}
                        />
                        <button
                            onClick={createSession}
                            disabled={creating || !newTitle.trim()}
                            className="px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {creating ? "Creating..." : "Start Session"}
                        </button>
                    </div>
                </div>

                {/* Sessions List */}
                <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                    <h2 className="text-xl font-semibold mb-4 text-gray-800 dark:text-white">
                        Your Study Sessions
                    </h2>

                    {loadingSessions ? (
                        <div className="text-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
                        </div>
                    ) : sessions.length === 0 ? (
                        <div className="text-center py-8 text-gray-500">
                            No study sessions yet. Create your first one above!
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {sessions.map((session) => (
                                <Link
                                    key={session.session_id}
                                    href={`/study/${session.session_id}`}
                                    className="block p-4 rounded-lg border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all dark:border-gray-700"
                                >
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h3 className="font-medium text-gray-800 dark:text-white">
                                                {session.title}
                                            </h3>
                                            <p className="text-sm text-gray-500">
                                                {new Date(session.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <span
                                            className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
                                                session.status
                                            )}`}
                                        >
                                            {session.status}
                                        </span>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
