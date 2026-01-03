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
    stability?: number;
    fsrs_difficulty?: number;
    leitner_box: number;
    session_id?: string;
    session_title?: string;
}

interface QuizResult {
    question_id: string;
    question: string;
    question_type: string;
    difficulty: string;
    concept: string;
    user_answer: string;
    correct: boolean | null;
    correct_answer: string;
    explanation: string;
    feedback: string | null;
    new_leitner_box: number | null;
    evaluation_status: string;
}

interface QuizResultsData {
    session_id: string;
    total_questions: number;
    evaluated_count: number;
    correct_count: number;
    results: QuizResult[];
}

// Track submitted answers locally for global mode
interface SubmittedAnswer {
    questionId: string;
    answer: string;
    sessionId: string;
}

export default function QuizPage() {
    const { user, token, loading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const searchParams = useSearchParams();
    const sessionId = params.id as string;
    const isGlobalMode = sessionId === "global" && searchParams.get("mode") === "global";
    const isReviewMode = searchParams.get("mode") === "review";

    const [questions, setQuestions] = useState<Question[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [answer, setAnswer] = useState("");
    const [generating, setGenerating] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    // New states for batch evaluation
    const [allAnswered, setAllAnswered] = useState(false);
    const [loadingResults, setLoadingResults] = useState(false);
    const [quizResults, setQuizResults] = useState<QuizResultsData | null>(null);
    const [submittedAnswers, setSubmittedAnswers] = useState<SubmittedAnswer[]>([]);

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
            if (isGlobalMode) {
                const data = await api.getGlobalDueQuestions(token);
                setQuestions(data);
            } else {
                const data = await api.getQuestions(token, sessionId, isReviewMode);
                if (data.length > 0) {
                    setQuestions(data);
                } else if (!isReviewMode) {
                    generateQuiz();
                }
            }
        } catch (error) {
            if (!isReviewMode && !isGlobalMode) {
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

    const submitAnswer = () => {
        if (!token || !answer.trim()) return;

        const currentQuestion = questions[currentIndex];
        setSubmitting(true);

        // Fire-and-forget submission - don't await!
        api.submitAnswerAsync(token, currentQuestion.question_id, answer)
            .catch(error => console.error("Failed to submit answer:", error));

        // Track submitted answer locally (for global mode results)
        setSubmittedAnswers(prev => [...prev, {
            questionId: currentQuestion.question_id,
            answer: answer,
            sessionId: currentQuestion.session_id || sessionId
        }]);

        // Move to next question immediately
        if (currentIndex < questions.length - 1) {
            setCurrentIndex(prev => prev + 1);
            setAnswer("");
        } else {
            // All questions answered
            setAllAnswered(true);
        }

        setSubmitting(false);
    };

    const fetchResults = async () => {
        if (!token) return;
        setLoadingResults(true);

        try {
            if (isGlobalMode) {
                // For global mode, we need to fetch results from multiple sessions
                const sessionIds = [...new Set(submittedAnswers.map(a => a.sessionId))];
                const allResults: QuizResult[] = [];
                let totalCorrect = 0;
                let totalEvaluated = 0;

                for (const sid of sessionIds) {
                    try {
                        const results = await api.getQuizResults(token, sid);
                        // Filter to only include questions we answered in this quiz session
                        const answeredIds = new Set(submittedAnswers.filter(a => a.sessionId === sid).map(a => a.questionId));
                        const filteredResults = results.results.filter(r => answeredIds.has(r.question_id));
                        allResults.push(...filteredResults);
                        totalCorrect += filteredResults.filter(r => r.correct).length;
                        totalEvaluated += filteredResults.filter(r => r.evaluation_status === "completed").length;
                    } catch (e) {
                        console.error(`Failed to get results for session ${sid}:`, e);
                    }
                }

                setQuizResults({
                    session_id: "global",
                    total_questions: allResults.length,
                    evaluated_count: totalEvaluated,
                    correct_count: totalCorrect,
                    results: allResults
                });
            } else {
                const results = await api.getQuizResults(token, sessionId);
                setQuizResults(results);
            }
        } catch (error) {
            console.error("Failed to fetch results:", error);
        } finally {
            setLoadingResults(false);
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
    const answeredProgress = questions.length > 0 ? (submittedAnswers.length / questions.length) * 100 : 0;

    const getDifficultyColor = (diff: string) => {
        switch (diff) {
            case "easy": return "bg-[#E3FCEF] text-[#006644]";
            case "medium": return "bg-[#FFFAE6] text-[#974F0C]";
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

    // Show results view
    if (quizResults) {
        const percentage = quizResults.total_questions > 0
            ? Math.round((quizResults.correct_count / quizResults.total_questions) * 100)
            : 0;

        return (
            <div className="min-h-screen bg-[#FAFBFC]">
                <header className="bg-white border-b border-[#DFE1E6] sticky top-0 z-10">
                    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4">
                        <div className="flex items-center justify-between">
                            <h1 className="text-xl font-bold text-[#172B4D]">Quiz Results</h1>
                            <div className="flex items-center gap-3">
                                <span className={`px-4 py-2 rounded-lg text-lg font-bold ${percentage >= 70 ? "bg-[#E3FCEF] text-[#006644]" :
                                    percentage >= 50 ? "bg-[#FFFAE6] text-[#FF8B00]" :
                                        "bg-[#FFEBE6] text-[#DE350B]"
                                    }`}>
                                    {quizResults.correct_count}/{quizResults.total_questions} ({percentage}%)
                                </span>
                            </div>
                        </div>
                    </div>
                </header>

                <main className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
                    {/* Summary Card */}
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-6 mb-6">
                        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                            <div className="text-center sm:text-left">
                                <h2 className="text-2xl font-bold text-[#172B4D] mb-1">
                                    {percentage >= 70 ? "🎉 Great job!" : percentage >= 50 ? "👍 Good effort!" : "📚 Keep practicing!"}
                                </h2>
                                <p className="text-[#6B778C]">
                                    You got {quizResults.correct_count} out of {quizResults.total_questions} questions correct
                                </p>
                            </div>
                            <div className="flex gap-3">
                                <Link
                                    href={isGlobalMode ? "/dashboard" : `/study/${sessionId}`}
                                    className="px-5 py-2.5 border border-[#DFE1E6] text-[#172B4D] rounded font-medium hover:bg-[#F4F5F7] transition-colors"
                                >
                                    {isGlobalMode ? "Dashboard" : "Back to Study"}
                                </Link>
                            </div>
                        </div>
                    </div>

                    {/* Results List */}
                    <div className="space-y-4">
                        {quizResults.results.map((result, index) => (
                            <div
                                key={result.question_id}
                                className={`bg-white rounded-lg border ${result.evaluation_status === "pending" ? "border-[#DFE1E6]" :
                                    result.correct ? "border-[#36B37E]" : "border-[#DE350B]"
                                    } overflow-hidden`}
                            >
                                {/* Question Header */}
                                <div className={`px-4 py-3 ${result.evaluation_status === "pending" ? "bg-[#F4F5F7]" :
                                    result.correct ? "bg-[#E3FCEF]" : "bg-[#FFEBE6]"
                                    }`}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium text-[#172B4D]">Q{index + 1}</span>
                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getTypeColor(result.question_type)}`}>
                                                {result.question_type}
                                            </span>
                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getDifficultyColor(result.difficulty)}`}>
                                                {result.difficulty}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {result.evaluation_status === "pending" ? (
                                                <span className="flex items-center gap-1 text-[#6B778C] text-sm">
                                                    <div className="animate-spin rounded-full h-3 w-3 border border-[#6B778C] border-t-transparent"></div>
                                                    Evaluating...
                                                </span>
                                            ) : result.correct ? (
                                                <span className="flex items-center gap-1 text-[#006644] font-medium">
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                    </svg>
                                                    Correct
                                                </span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-[#DE350B] font-medium">
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                    </svg>
                                                    Incorrect
                                                </span>
                                            )}
                                            {result.new_leitner_box && (
                                                <span className="text-xs text-[#6B778C]">→ Box {result.new_leitner_box}</span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Question Content */}
                                <div className="p-4 space-y-3">
                                    <p className="text-[#172B4D] font-medium">{result.question}</p>

                                    <div className="grid gap-2 text-sm">
                                        <div className="flex gap-2">
                                            <span className="text-[#6B778C] w-24 flex-shrink-0">Your answer:</span>
                                            <span className="text-[#172B4D]">{result.user_answer}</span>
                                        </div>
                                        {!result.correct && result.evaluation_status === "completed" && (
                                            <div className="flex gap-2">
                                                <span className="text-[#6B778C] w-24 flex-shrink-0">Correct:</span>
                                                <span className="text-[#006644] font-medium">{result.correct_answer}</span>
                                            </div>
                                        )}
                                    </div>

                                    {result.explanation && (
                                        <div className="bg-[#F4F5F7] rounded p-3 text-sm text-[#42526E]">
                                            {result.explanation}
                                        </div>
                                    )}

                                    {result.feedback && (
                                        <div className="bg-[#FFFAE6] border border-[#FFE380] rounded p-3 text-sm text-[#172B4D]">
                                            💡 {result.feedback}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </main>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#FAFBFC]">
            {/* Header */}
            <header className="bg-white border-b border-[#DFE1E6] sticky top-0 z-10">
                <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
                    <div className="flex items-center justify-between gap-4">
                        <Link
                            href={isGlobalMode ? "/dashboard" : `/study/${sessionId}`}
                            className="text-sm text-[#6B778C] hover:text-[#172B4D] transition-colors flex-shrink-0"
                        >
                            <span className="hidden sm:inline">{isGlobalMode ? "← Back to Dashboard" : "← Back to Study"}</span>
                            <span className="sm:hidden">← Back</span>
                        </Link>
                        <div className="flex items-center gap-2 sm:gap-4">
                            {isGlobalMode && (
                                <span className="px-2 py-1 bg-[#DEEBFF] text-[#0747A6] rounded text-xs font-medium">
                                    Global Review
                                </span>
                            )}
                            {isReviewMode && !isGlobalMode && (
                                <span className="px-2 py-1 bg-[#DEEBFF] text-[#0747A6] rounded text-xs font-medium">
                                    Review Mode
                                </span>
                            )}
                            <span className="text-xs sm:text-sm text-[#6B778C]">
                                Question {allAnswered ? questions.length : currentIndex + 1} of {questions.length}
                            </span>
                        </div>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-3 sm:mt-4 h-1 bg-[#DFE1E6] rounded-full overflow-hidden">
                        <div
                            className="h-full bg-[#0052CC] transition-all duration-300"
                            style={{ width: `${allAnswered ? 100 : progress}%` }}
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
                ) : allAnswered ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        {loadingResults ? (
                            <>
                                <div className="animate-spin rounded-full h-10 w-10 sm:h-12 sm:w-12 border-2 border-[#0052CC] border-t-transparent mx-auto mb-4"></div>
                                <h2 className="text-base sm:text-lg font-semibold text-[#172B4D]">Evaluating Your Answers...</h2>
                                <p className="text-[#6B778C] mt-2 text-xs sm:text-sm">Please wait while we check your responses</p>
                            </>
                        ) : (
                            <>
                                <div className="w-12 h-12 sm:w-16 sm:h-16 bg-[#DEEBFF] rounded-full flex items-center justify-center mx-auto mb-4">
                                    <svg className="w-6 h-6 sm:w-8 sm:h-8 text-[#0052CC]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                </div>
                                <h2 className="text-xl sm:text-2xl font-bold text-[#172B4D] mb-2">All Questions Answered!</h2>
                                <p className="text-[#6B778C] mb-6">
                                    You've answered all {questions.length} questions. Click below to see your results.
                                </p>
                                <button
                                    onClick={fetchResults}
                                    className="px-8 py-3 bg-[#0052CC] text-white rounded-lg font-medium hover:bg-[#0747A6] transition-colors text-lg"
                                >
                                    View Results
                                </button>
                            </>
                        )}
                    </div>
                ) : currentQuestion ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6]">
                        {/* Question */}
                        <div className="p-4 sm:p-6 border-b border-[#DFE1E6]">
                            {/* Session context for global mode */}
                            {isGlobalMode && currentQuestion.session_title && (
                                <div className="mb-3">
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#F4F5F7] text-[#6B778C] rounded text-xs font-medium">
                                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                        </svg>
                                        From: {currentQuestion.session_title}
                                    </span>
                                </div>
                            )}
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

                        {/* Answer Input */}
                        <div className="p-4 sm:p-6">
                            <label className="block text-sm font-medium text-[#172B4D] mb-2">
                                Your Answer
                            </label>
                            <textarea
                                value={answer}
                                onChange={(e) => setAnswer(e.target.value)}
                                placeholder="Type your answer here..."
                                className="w-full h-28 sm:h-32 px-3 sm:px-4 py-3 rounded border border-[#DFE1E6] focus:ring-2 focus:ring-[#4C9AFF] focus:border-transparent resize-none text-[#172B4D] placeholder-[#6B778C] text-sm"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && e.metaKey && answer.trim()) {
                                        submitAnswer();
                                    }
                                }}
                            />
                            <button
                                onClick={submitAnswer}
                                disabled={submitting || !answer.trim()}
                                className="mt-4 w-full px-6 py-3 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                            >
                                {submitting && (
                                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                                )}
                                {submitting ? "Submitting..." : currentIndex < questions.length - 1 ? "Submit & Next" : "Submit & Finish"}
                            </button>
                            <p className="text-center text-xs text-[#6B778C] mt-2">
                                Press ⌘+Enter to submit
                            </p>
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
