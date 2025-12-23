"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

interface Question {
    question_id: string;
    question: string;
    question_type: string;
    difficulty: string;
    concept: string;
    leitner_box: number;
}

interface AnswerResult {
    correct: boolean;
    correct_answer: string;
    explanation: string;
    new_leitner_box: number;
    feedback?: string;
}

export default function QuizPage() {
    const { user, token, loading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const sessionId = params.id as string;

    const [questions, setQuestions] = useState<Question[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [answer, setAnswer] = useState("");
    const [result, setResult] = useState<AnswerResult | null>(null);
    const [generating, setGenerating] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [completed, setCompleted] = useState(false);
    const [score, setScore] = useState({ correct: 0, total: 0 });

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    useEffect(() => {
        if (token && sessionId) {
            loadQuestions();
        }
    }, [token, sessionId]);

    const loadQuestions = async () => {
        if (!token) return;
        // Don't reload if we already have questions
        if (questions.length > 0) return;

        try {
            const data = await api.getQuestions(token, sessionId);
            if (data.length > 0) {
                setQuestions(data);
            } else {
                // Generate new questions
                generateQuiz();
            }
        } catch (error) {
            generateQuiz();
        }
    };

    const generateQuiz = async () => {
        if (!token) return;
        setGenerating(true);
        try {
            const data = await api.generateQuiz(token, sessionId);
            setQuestions(data);
        } catch (error) {
            console.error("Failed to generate quiz:", error);
        } finally {
            setGenerating(false);
        }
    };

    const submitAnswer = async () => {
        if (!token || !answer.trim()) return;

        const currentQuestion = questions[currentIndex];
        setSubmitting(true);

        try {
            const res = await api.submitAnswer(token, currentQuestion.question_id, answer);
            setResult(res);
            setScore((prev) => ({
                correct: prev.correct + (res.correct ? 1 : 0),
                total: prev.total + 1,
            }));
        } catch (error) {
            console.error("Failed to submit answer:", error);
        } finally {
            setSubmitting(false);
        }
    };

    const nextQuestion = () => {
        if (currentIndex < questions.length - 1) {
            setCurrentIndex((prev) => prev + 1);
            setAnswer("");
            setResult(null);
        } else {
            setCompleted(true);
        }
    };

    if (loading || !user) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    const currentQuestion = questions[currentIndex];

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            {/* Header */}
            <header className="bg-white dark:bg-gray-800 shadow">
                <div className="container mx-auto px-4 py-4 flex items-center justify-between">
                    <Link href={`/study/${sessionId}`} className="text-indigo-600 hover:underline">
                        ← Back to Study
                    </Link>
                    <div className="flex items-center gap-4">
                        <span className="text-gray-600 dark:text-gray-300">
                            Question {currentIndex + 1} of {questions.length}
                        </span>
                        <span className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-medium">
                            Score: {score.correct}/{score.total}
                        </span>
                    </div>
                </div>
            </header>

            <main className="container mx-auto px-4 py-8 max-w-3xl">
                {generating ? (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 text-center">
                        <div className="animate-spin rounded-full h-16 w-16 border-4 border-purple-600 border-t-transparent mx-auto mb-4"></div>
                        <h2 className="text-xl font-semibold text-gray-800 dark:text-white">
                            Generating Quiz Questions...
                        </h2>
                    </div>
                ) : completed ? (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 text-center">
                        <div className="text-6xl mb-4">🎉</div>
                        <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">
                            Quiz Complete!
                        </h2>
                        <p className="text-xl text-gray-600 dark:text-gray-400 mb-6">
                            You scored {score.correct} out of {score.total} (
                            {Math.round((score.correct / score.total) * 100)}%)
                        </p>
                        <div className="flex gap-4 justify-center">
                            <Link
                                href={`/study/${sessionId}`}
                                className="px-6 py-3 bg-gray-200 text-gray-800 rounded-lg font-medium hover:bg-gray-300"
                            >
                                Back to Study
                            </Link>
                            <Link
                                href="/dashboard"
                                className="px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700"
                            >
                                Dashboard
                            </Link>
                        </div>
                    </div>
                ) : currentQuestion ? (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                        {/* Question */}
                        <div className="mb-6">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                                    {currentQuestion.question_type}
                                </span>
                                <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                                    {currentQuestion.difficulty}
                                </span>
                                <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                                    Box {currentQuestion.leitner_box}
                                </span>
                            </div>
                            <h2 className="text-xl font-semibold text-gray-800 dark:text-white">
                                {currentQuestion.question}
                            </h2>
                        </div>

                        {/* Answer Input */}
                        {!result && (
                            <div>
                                <textarea
                                    value={answer}
                                    onChange={(e) => setAnswer(e.target.value)}
                                    placeholder="Type your answer here..."
                                    className="w-full h-32 px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                />
                                <button
                                    onClick={submitAnswer}
                                    disabled={submitting || !answer.trim()}
                                    className="mt-4 w-full px-6 py-3 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {submitting ? "Checking..." : "Submit Answer"}
                                </button>
                            </div>
                        )}

                        {/* Result */}
                        {result && (
                            <div>
                                <div
                                    className={`p-4 rounded-lg mb-4 ${result.correct
                                        ? "bg-green-50 border border-green-200"
                                        : "bg-red-50 border border-red-200"
                                        }`}
                                >
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="text-2xl">{result.correct ? "✅" : "❌"}</span>
                                        <span
                                            className={`font-semibold ${result.correct ? "text-green-700" : "text-red-700"
                                                }`}
                                        >
                                            {result.correct ? "Correct!" : "Incorrect"}
                                        </span>
                                        <span className="text-sm text-gray-500">
                                            → Box {result.new_leitner_box}
                                        </span>
                                    </div>
                                    {!result.correct && (
                                        <p className="text-gray-700">
                                            <strong>Correct answer:</strong> {result.correct_answer}
                                        </p>
                                    )}
                                    {result.explanation && (
                                        <p className="text-gray-600 mt-2 text-sm">{result.explanation}</p>
                                    )}
                                    {result.feedback && (
                                        <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
                                            <strong>💡 Tip:</strong> {result.feedback}
                                        </div>
                                    )}
                                </div>
                                <button
                                    onClick={nextQuestion}
                                    className="w-full px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700"
                                >
                                    {currentIndex < questions.length - 1
                                        ? "Next Question →"
                                        : "Finish Quiz"}
                                </button>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-center py-8 text-gray-500">
                        No questions available.
                    </div>
                )}
            </main>
        </div>
    );
}
