"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
    user_answer?: string;
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
    const [error, setError] = useState<string | null>(null);
    const [answer, setAnswer] = useState("");
    const [loadingQuestions, setLoadingQuestions] = useState(true);
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

    const initializeQuiz = (data: Question[]) => {
        if (data.length === 0) {
            setLoadingQuestions(false);
            return;
        }

        setQuestions(data);

        // Sync answered questions to local state
        const answeredItems = data
            .filter(q => q.user_answer)
            .map(q => ({
                questionId: q.question_id,
                answer: q.user_answer!,
                sessionId: q.session_id || sessionId
            }));
        setSubmittedAnswers(answeredItems);

        // Determine if all are answered
        if (answeredItems.length === data.length) {
            setAllAnswered(true);
            setLoadingQuestions(false);
            fetchResults();
        } else {
            // Find the first unanswered index to resume exactly where we left off
            const firstUnanswered = data.findIndex(q => !q.user_answer);
            if (firstUnanswered !== -1) {
                setCurrentIndex(firstUnanswered);
            }
            setLoadingQuestions(false);
        }
    };

    const loadQuestions = async () => {
        if (!token) return;
        if (questions.length > 0) return;

        setLoadingQuestions(true);
        try {
            if (isGlobalMode) {
                const data = await api.getGlobalDueQuestions(token);
                initializeQuiz(data);
            } else {
                // Use resume=true for standard quiz loading
                const data = await api.getQuestions(token, sessionId, isReviewMode, true);
                if (data.length > 0) {
                    initializeQuiz(data);
                } else if (!isReviewMode) {
                    generateQuiz();
                } else {
                    setLoadingQuestions(false);
                }
            }
        } catch (error: any) {
            console.error("DEBUG: loadQuestions Failed:", error);
            setError(error.message || "Failed to load quiz questions. Please check if the backend is running.");
            if (!isReviewMode && !isGlobalMode) {
                generateQuiz();
            } else {
                setLoadingQuestions(false);
            }
        }
    };

    const generateQuiz = async () => {
        if (!token) return;
        setGenerating(true);
        setLoadingQuestions(true);
        try {
            const data = await api.generateQuiz(token, sessionId);
            initializeQuiz(data);
        } catch (error) {
            console.error("Failed to generate quiz:", error);
            setLoadingQuestions(false);
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

    // Save progress and show partial results
    const saveAndExit = async () => {
        if (!token || submittedAnswers.length === 0) return;
        setAllAnswered(true);
        await fetchResults();
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
        const d = diff.toLowerCase();
        if (d === 'easy') return "bg-[#E3FCEF] text-[#006644] border border-[#ABF5D1]";
        if (d === 'medium') return "bg-[#FFF0B3] text-[#172B4D] border border-[#FFE380]";
        if (d === 'hard') return "bg-[#FFEBE6] text-[#BF2600] border border-[#FFBDAD]";
        return "bg-[#F4F5F7] text-[#42526E] border border-[#DFE1E6]";
    };

    const getTypeColor = (type: string) => {
        const t = type.toLowerCase();
        if (t === 'multiple choice') return "bg-[#DEEBFF] text-[#0747A6] border border-[#B3D4FF]";
        if (t === 'short answer') return "bg-[#EAE6FF] text-[#403294] border border-[#C0B6F2]";
        return "bg-[#F4F5F7] text-[#42526E] border border-[#DFE1E6]";
    };

    // Show results view
    if (quizResults) {
        const percentage = quizResults.total_questions > 0
            ? Math.round((quizResults.correct_count / quizResults.total_questions) * 100)
            : 0;

        return (
            <div className="min-h-screen bg-[#FAFBFC]">
                <header className="bg-white border-b border-[#DFE1E6] sticky top-0 z-10">
                    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
                        <div className="flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3 sm:gap-4">
                                <Link
                                    href={isGlobalMode ? "/dashboard" : `/study/${sessionId}`}
                                    className="text-[#6B778C] hover:text-[#172B4D] transition-colors text-sm font-medium"
                                >
                                    ← {isGlobalMode ? "Dashboard" : "Back"}
                                </Link>
                                <span className="text-[#DFE1E6] hidden sm:inline">|</span>
                                <h1 className="text-sm font-semibold text-[#172B4D]">Quiz Results</h1>
                            </div>
                            <span className={`px-3 py-1.5 rounded text-sm font-semibold ${percentage >= 70 ? "bg-[#E3FCEF] text-[#006644]" :
                                percentage >= 50 ? "bg-[#FFFAE6] text-[#974F0C]" :
                                    "bg-[#FFEBE6] text-[#DE350B]"
                                }`}>
                                {quizResults.correct_count}/{quizResults.total_questions} ({percentage}%)
                            </span>
                        </div>
                    </div>
                </header>

                <main className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
                    {/* Summary Card */}
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-6 mb-6 shadow-sm">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 rounded bg-[#FAFBFC] border border-[#DFE1E6] flex items-center justify-center flex-shrink-0">
                                    <svg className="w-5 h-5 text-[#42526E]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                    </svg>
                                </div>
                                <div>
                                    <h2 className="text-sm font-semibold text-[#172B4D]">
                                        Performance Overview
                                    </h2>
                                    <p className="text-sm text-[#6B778C]">
                                        {quizResults.correct_count} of {quizResults.total_questions} questions correct • {percentage}% proficiency
                                    </p>
                                </div>
                            </div>
                            <Link
                                href={isGlobalMode ? "/dashboard" : `/study/${sessionId}`}
                                className="px-4 py-2 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors text-sm text-center"
                            >
                                {isGlobalMode ? "Back to Dashboard" : "Return to Session"}
                            </Link>
                        </div>
                    </div>

                    {/* Results List */}
                    <div className="space-y-3">
                        <h3 className="text-[10px] font-bold text-[#6B778C] uppercase tracking-wider mb-3">Question Breakdown</h3>
                        {quizResults.results.map((result, index) => (
                            <div
                                key={result.question_id}
                                className="bg-white rounded-lg border border-[#DFE1E6] border-l-4 border-l-[#0052CC] overflow-hidden"
                            >
                                {/* Question Header */}
                                <div className="px-4 py-3 bg-[#FAFBFC] border-b border-[#DFE1E6]">
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
                                        <div className="flex items-center gap-2 text-sm">
                                            {result.evaluation_status === "pending" ? (
                                                <span className="flex items-center gap-1 text-[#6B778C]">
                                                    <div className="animate-spin rounded-full h-3 w-3 border border-[#6B778C] border-t-transparent"></div>
                                                    Evaluating
                                                </span>
                                            ) : (
                                                <span className={`${result.correct ? "text-[#00875A]" : "text-[#DE350B]/60"} font-medium`}>
                                                    {result.correct ? "Correct" : "Incorrect"}
                                                </span>
                                            )}
                                            {result.new_leitner_box && (
                                                <span className="text-[10px] uppercase font-bold text-[#6B778C] tracking-wider ml-1">→ Box {result.new_leitner_box}</span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="p-4 space-y-4">
                                    <div className="prose max-w-none text-sm text-[#172B4D] font-medium">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.question}</ReactMarkdown>
                                    </div>

                                    <div className="space-y-2 text-sm">
                                        <div className="flex gap-2">
                                            <span className="text-[#6B778C] w-24 flex-shrink-0">Your answer:</span>
                                            <div className="prose max-w-none text-[#172B4D]">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.user_answer}</ReactMarkdown>
                                            </div>
                                        </div>
                                        {!result.correct && result.evaluation_status === "completed" && (
                                            <div className="flex gap-2">
                                                <span className="text-[#6B778C] w-24 flex-shrink-0 font-medium">Correct Answer:</span>
                                                <div className="prose max-w-none text-[#42526E]">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.correct_answer}</ReactMarkdown>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {result.explanation && (
                                        <div className="bg-[#FAFBFC] border border-[#DFE1E6] rounded p-3 text-sm text-[#42526E]">
                                            <div className="text-[10px] font-bold text-[#6B778C] uppercase tracking-wider mb-2">Explanation</div>
                                            <div className="prose max-w-none">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                    {result.explanation}
                                                </ReactMarkdown>
                                            </div>
                                        </div>
                                    )}

                                    {result.feedback && (
                                        <div className="bg-[#F4F5F7] border border-[#DFE1E6] rounded p-3 text-sm text-[#172B4D]">
                                            <div className="prose max-w-none">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                    {result.feedback}
                                                </ReactMarkdown>
                                            </div>
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
                                <span className="px-2 py-1 bg-[#F4F5F7] text-[#42526E] border border-[#DFE1E6] rounded text-[10px] font-bold uppercase tracking-wider">
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
                {error && (
                    <div className="mb-6 p-4 bg-[#FFEBE6] border border-[#FF8F73] text-[#DE350B] rounded-lg flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span className="text-sm font-medium">{error}</span>
                        </div>
                        <button
                            onClick={() => {
                                setError(null);
                                loadQuestions();
                            }}
                            className="px-3 py-1 bg-white border border-[#FF8F73] rounded text-xs font-semibold hover:bg-[#FFF0B3] transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {loadingQuestions ? (
                    <div className="bg-white rounded-lg border border-[#DFE1E6] p-8 sm:p-12 text-center">
                        <div className="animate-spin rounded-full h-10 w-10 sm:h-12 sm:w-12 border-2 border-[#0052CC] border-t-transparent mx-auto mb-4"></div>
                        <h2 className="text-base sm:text-lg font-semibold text-[#172B4D]">Loading Quiz...</h2>
                        <p className="text-[#6B778C] mt-2 text-xs sm:text-sm">Please wait while we prepare your questions</p>
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
                                <h3 className="text-sm font-semibold text-[#172B4D] mb-1">Ready for Results</h3>
                                <p className="text-xs text-[#6B778C] mb-6">
                                    You've completed all {questions.length} questions.
                                </p>
                                <button
                                    onClick={fetchResults}
                                    className="px-6 py-2.5 bg-[#0052CC] text-white rounded font-medium hover:bg-[#0747A6] transition-colors"
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
                                <div className="mb-4">
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#F4F5F7] text-[#6B778C] rounded text-xs font-medium">
                                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                        </svg>
                                        From: {currentQuestion.session_title}
                                    </span>
                                </div>
                            )}
                            <div className="flex items-center gap-2 mb-6">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${getTypeColor(currentQuestion.question_type)}`}>
                                    {currentQuestion.question_type}
                                </span>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${getDifficultyColor(currentQuestion.difficulty)}`}>
                                    {currentQuestion.difficulty}
                                </span>
                                <span className="px-2 py-0.5 bg-[#F4F5F7] text-[#42526E] border border-[#DFE1E6] rounded text-[10px] font-bold uppercase tracking-wider">
                                    Box {currentQuestion.leitner_box}
                                </span>
                            </div>
                            <div className="prose max-w-none text-sm font-medium text-[#172B4D] leading-relaxed">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{currentQuestion.question}</ReactMarkdown>
                            </div>
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

                            {/* Save & Evaluate Progress button - visible when at least one question answered */}
                            {submittedAnswers.length > 0 && (
                                <button
                                    onClick={saveAndExit}
                                    className="mt-3 w-full px-6 py-2.5 border border-[#DFE1E6] text-[#172B4D] rounded font-medium hover:bg-[#F4F5F7] transition-colors flex items-center justify-center gap-2"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                                    </svg>
                                    Save & Evaluate Progress ({submittedAnswers.length}/{questions.length})
                                </button>
                            )}

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
