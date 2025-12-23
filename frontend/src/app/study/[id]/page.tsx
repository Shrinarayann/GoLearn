"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

interface SessionData {
    session_id: string;
    title: string;
    status: string;
    exploration_result?: Record<string, unknown>;
    engagement_result?: Record<string, unknown>;
    application_result?: Record<string, unknown>;
}

export default function StudySessionPage() {
    const { user, token, loading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const sessionId = params.id as string;

    const [session, setSession] = useState<SessionData | null>(null);
    const [content, setContent] = useState("");
    const [comprehending, setComprehending] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    useEffect(() => {
        if (token && sessionId) {
            loadSession();
        }
    }, [token, sessionId]);

    const loadSession = async () => {
        if (!token) return;
        try {
            const data = await api.getSession(token, sessionId);
            setSession(data);
        } catch (error) {
            console.error("Failed to load session:", error);
            setError("Failed to load session");
        }
    };

    const runComprehension = async () => {
        if (!token || !content.trim()) {
            setError("Please paste your study content first");
            return;
        }

        setComprehending(true);
        setError("");

        try {
            const result = await api.runComprehension(token, sessionId, content);
            setSession((prev) =>
                prev
                    ? {
                        ...prev,
                        status: result.status,
                        exploration_result: result.exploration,
                        engagement_result: result.engagement,
                        application_result: result.application,
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
                    <div className="flex items-center gap-4">
                        <Link href="/dashboard" className="text-indigo-600 hover:underline">
                            ← Back
                        </Link>
                        <h1 className="text-xl font-bold text-gray-800 dark:text-white">
                            {session?.title || "Loading..."}
                        </h1>
                    </div>
                    {session?.status === "ready" && (
                        <Link
                            href={`/quiz/${sessionId}`}
                            className="px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700"
                        >
                            Start Quiz →
                        </Link>
                    )}
                </div>
            </header>

            <main className="container mx-auto px-4 py-8">
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
                        {error}
                    </div>
                )}

                {/* Input Section */}
                {session?.status === "created" || session?.status === "uploaded" ? (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-8">
                        <h2 className="text-lg font-semibold mb-4 text-gray-800 dark:text-white">
                            Step 1: Paste Your Study Material
                        </h2>
                        <textarea
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            placeholder="Paste your study notes, textbook content, or article here..."
                            className="w-full h-64 px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                        />
                        <div className="mt-4 flex justify-end">
                            <button
                                onClick={runComprehension}
                                disabled={comprehending || !content.trim()}
                                className="px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                {comprehending && (
                                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                                )}
                                {comprehending ? "Analyzing..." : "Run Three-Pass Analysis"}
                            </button>
                        </div>
                    </div>
                ) : null}

                {/* Comprehending State */}
                {session?.status === "comprehending" && (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 text-center">
                        <div className="animate-spin rounded-full h-16 w-16 border-4 border-indigo-600 border-t-transparent mx-auto mb-4"></div>
                        <h2 className="text-xl font-semibold text-gray-800 dark:text-white">
                            Analyzing Your Content...
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 mt-2">
                            Running exploration, engagement, and application passes
                        </p>
                    </div>
                )}

                {/* Results Section */}
                {session?.status === "ready" && (
                    <div className="space-y-6">
                        {/* Exploration */}
                        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                            <h2 className="text-lg font-semibold mb-4 text-indigo-600 flex items-center gap-2">
                                <span className="text-2xl">📖</span> Pass 1: Exploration
                            </h2>
                            <pre className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg overflow-auto text-sm text-gray-800 dark:text-gray-200">
                                {JSON.stringify(session.exploration_result, null, 2)}
                            </pre>
                        </div>

                        {/* Engagement */}
                        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                            <h2 className="text-lg font-semibold mb-4 text-green-600 flex items-center gap-2">
                                <span className="text-2xl">🔍</span> Pass 2: Engagement
                            </h2>
                            <pre className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg overflow-auto text-sm text-gray-800 dark:text-gray-200">
                                {JSON.stringify(session.engagement_result, null, 2)}
                            </pre>
                        </div>

                        {/* Application */}
                        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                            <h2 className="text-lg font-semibold mb-4 text-purple-600 flex items-center gap-2">
                                <span className="text-2xl">🚀</span> Pass 3: Application
                            </h2>
                            <pre className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg overflow-auto text-sm text-gray-800 dark:text-gray-200">
                                {JSON.stringify(session.application_result, null, 2)}
                            </pre>
                        </div>

                        {/* Next Step */}
                        <div className="text-center py-6">
                            <Link
                                href={`/quiz/${sessionId}`}
                                className="inline-flex items-center gap-2 px-8 py-4 bg-purple-600 text-white rounded-full text-lg font-semibold hover:bg-purple-700 transition-all shadow-lg hover:shadow-xl"
                            >
                                Ready to Test Your Knowledge? Start Quiz →
                            </Link>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
