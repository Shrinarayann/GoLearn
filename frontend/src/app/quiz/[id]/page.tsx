"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams, useSearchParams } from "next/navigation";
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
    const searchParams = useSearchParams();
    const sessionId = params.id as string;
    const isReviewMode = searchParams.get("mode") === "review";

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
        if (questions.length > 0) return;

        try {
            // In review mode, fetch only due questions
            const data = await api.getQuestions(token, sessionId, isReviewMode);
            if (data.length > 0) {
                setQuestions(data);
            } else if (!isReviewMode) {
                // Only generate new quiz if not in review mode
                generateQuiz();
            }
        } catch (error) {
            if (!isReviewMode) {
                generateQuiz();
            }
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
            <div className="min-h-screen flex items-center justify-center bg-[#FAFBFC]">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-[#0052CC] border-t-transparent"></div>
            </div>
        );
    }

    const currentQuestion = questions[currentIndex];
    const progress = questions.length > 0 ? ((currentIndex + 1) / questions.length) * 100 : 0;

    const getDifficultyColor = (diff: string) => {
        switch (diff) {
            case "easy": return "bg-[#E3FCEF] text-[#006644]";
            case "medium": return "bg-[#FFFAE6] text-[#FF8B00]";
            case "hard": return "bg-[#FFEBE6] text-[#DE350B]";
            default: return "bg-[#F4F5F7] text-[#6B778C]";
        }
    };

    const getTypeColor = (type: string) => {
        switch (type) {
            case "recall": return "bg-[#DEEBFF] text-[#0747A6]";
            case "understanding": return "bg-[#EAE6FF] text-[#403294]";
            case "application": return "bg-[#E3FCEF] text-[#006644]";
            default: return "bg-[#F4F5F7] text-[#6B778C]";
        }
    };

    return (
        <div className="min-h-screen bg-[#FAFBFC]">
            {/* Header */}
            <header className="bg-white border-b border-[#DFE1E6] sticky top-0 z-10">
                <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
                    <div className="flex items-center justify-between gap-4">
                        <Link href={`/study/${sessionId}`} className="text-sm text-[#6B778C] hover:text-[#172B4D] transition-colors flex-shrink-0">
                            <span className="hidden sm:inline">← Back to Study</span>
                            <span className="sm:hidden">← Back</span>
                        </Link>
                        <div className="flex items-center gap-2 sm:gap-4">
                            {isReviewMode && (
                                <span className="px-2 py-1 bg-[#FF8B00] text-white rounded text-xs font-medium">
                                    Review Mode
                                </span>
                            )}
                            <span className="text-xs sm:text-sm text-[#6B778C]">
                                {currentIndex + 1}/{questions.length}
                            </span>
                            <span className="px-2 sm:px-3 py-1 bg-[#DEEBFF] text-[#0747A6] rounded text-xs sm:text-sm font-medium">
                                {score.correct}/{score.total}
                            </span>
                        </div>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-3 sm:mt-4 h-1 bg-[#DFE1E6] rounded-full overflow-hidden">
                        <div
                            className="h-full bg-[#0052CC] transition-all duration-300"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
            </header>

            <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
                {generating ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <div className="animate-spin rounded-full h-10 w-10 sm:h-12 sm:w-12 border-2 border-[#0052CC] border-t-transparent mx-auto mb-4"></div>
                        <h2 className="text-base sm:text-lg font-semibold text-[#172B4D]">Generating Quiz Questions...</h2>
                        <p className="text-[#6B778C] mt-2 text-xs sm:text-sm">Creating personalized questions based on your study material</p>
                    </div>
                ) : completed ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-[#E3FCEF] rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-6 h-6 sm:w-8 sm:h-8 text-[#36B37E]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h2 className="text-xl sm:text-2xl font-bold text-[#172B4D] mb-2">Quiz Complete!</h2>
                        <p className="text-lg sm:text-xl text-[#6B778C] mb-6">
                            You scored {score.correct} out of {score.total} ({Math.round((score.correct / score.total) * 100)}%)
                        </p>
                        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
                            <Link
                                href={`/study/${sessionId}`}
                                className="px-5 py-2.5 border border-[#DFE1E6] text-[#172B4D] rounded font-medium hover:bg-[#F4F5F7] transition-colors text-center"
                            >
                                Back to Study
                            </Link>
                            <Link
                                href="/dashboard"
                                className="px-5 py-2.5 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors text-center"
                            >
                                Dashboard
                            </Link>
                        </div>
                    </div>
                ) : currentQuestion ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6]">
                        {/* Question */}
                        <div className="p-4 sm:p-6 border-b border-[#DFE1E6]">
                            <div className="flex flex-wrap items-center gap-2 mb-3 sm:mb-4">
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${getTypeColor(currentQuestion.question_type)}`}>
                                    {currentQuestion.question_type}
                                </span>
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${getDifficultyColor(currentQuestion.difficulty)}`}>
                                    {currentQuestion.difficulty}
                                </span>
                                <span className="px-2 py-0.5 bg-[#F4F5F7] text-[#6B778C] rounded text-xs font-medium">
                                    Box {currentQuestion.leitner_box}
                                </span>
                            </div>
                            <h2 className="text-base sm:text-lg font-medium text-[#172B4D] leading-relaxed">
                                {currentQuestion.question}
                            </h2>
                        </div>

                        {/* Answer Input or Result */}
                        <div className="p-4 sm:p-6">
                            {!result ? (
                                <div>
                                    <label className="block text-sm font-medium text-[#172B4D] mb-2">
                                        Your Answer
                                    </label>
                                    <textarea
                                        value={answer}
                                        onChange={(e) => setAnswer(e.target.value)}
                                        placeholder="Type your answer here..."
                                        className="w-full h-28 sm:h-32 px-3 sm:px-4 py-3 rounded border border-[#DFE1E6] focus:ring-2 focus:ring-[#4C9AFF] focus:border-transparent resize-none text-[#172B4D] placeholder-[#6B778C] text-sm"
                                    />
                                    <button
                                        onClick={submitAnswer}
                                        disabled={submitting || !answer.trim()}
                                        className="mt-4 w-full px-6 py-3 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                                    >
                                        {submitting && (
                                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                                        )}
                                        {submitting ? "Checking..." : "Submit Answer"}
                                    </button>
                                </div>
                            ) : (
                                <div>
                                    {/* Result Banner */}
                                    <div className={`rounded-lg p-4 mb-4 ${result.correct ? "bg-[#E3FCEF]" : "bg-[#FFEBE6]"}`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            {result.correct ? (
                                                <svg className="w-5 h-5 text-[#36B37E]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                </svg>
                                            ) : (
                                                <svg className="w-5 h-5 text-[#DE350B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                </svg>
                                            )}
                                            <span className={`font-semibold ${result.correct ? "text-[#006644]" : "text-[#DE350B]"}`}>
                                                {result.correct ? "Correct!" : "Incorrect"}
                                            </span>
                                            <span className="text-xs sm:text-sm text-[#6B778C]">→ Box {result.new_leitner_box}</span>
                                        </div>
                                        {!result.correct && (
                                            <p className="text-[#172B4D] text-sm">
                                                <strong>Correct answer:</strong> {result.correct_answer}
                                            </p>
                                        )}
                                    </div>

                                    {/* Explanation */}
                                    {result.explanation && (
                                        <div className="bg-[#F4F5F7] rounded-lg p-4 mb-4">
                                            <p className="text-[#42526E] text-sm">{result.explanation}</p>
                                        </div>
                                    )}

                                    {/* Feedback for wrong answers */}
                                    {result.feedback && (
                                        <div className="bg-[#FFFAE6] border border-[#FFE380] rounded-lg p-4 mb-4">
                                            <div className="flex items-start gap-2">
                                                <svg className="w-4 h-4 text-[#FFAB00] flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                                                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                                </svg>
                                                <p className="text-[#172B4D] text-sm">{result.feedback}</p>
                                            </div>
                                        </div>
                                    )}

                                    <button
                                        onClick={nextQuestion}
                                        className="w-full px-6 py-3 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors"
                                    >
                                        {currentIndex < questions.length - 1 ? "Next Question" : "Finish Quiz"}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <p className="text-[#6B778C]">No questions available.</p>
                    </div>
                )}
            </main>
        </div>
    );
}
