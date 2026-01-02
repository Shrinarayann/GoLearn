"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import VoiceChatPanel from "./VoiceChatPanel";

interface Message {
    role: "user" | "agent";
    text: string;
}

interface FeynmanTopic {
    name: string;
    mastery?: {
        score: number;
        updated_at?: string;
    };
}

export default function FeynmanPage() {
    const { user, token, loading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const sessionId = params.id as string;

    const [sessionTitle, setSessionTitle] = useState("Loading...");
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const [loadingGreeting, setLoadingGreeting] = useState(false);
    const [error, setError] = useState("");
    const [topics, setTopics] = useState<FeynmanTopic[]>([]);
    const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
    const [showTopicModal, setShowTopicModal] = useState(false);
    const [isEvaluating, setIsEvaluating] = useState(false);
    const [evaluationResult, setEvaluationResult] = useState<{ score: number; feedback: string } | null>(null);
    const [isVoiceMode, setIsVoiceMode] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    useEffect(() => {
        if (token && sessionId) {
            loadInitialData();
        }
    }, [token, sessionId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const loadInitialData = async () => {
        if (!token) return;
        try {
            const sessionData = await api.getSession(token, sessionId);
            setSessionTitle(sessionData.title);

            const topicsData = await api.getFeynmanTopics(token, sessionId);
            setTopics(topicsData.topics);

            // If there's only one topic, select it automatically
            if (topicsData.topics.length === 1) {
                handleTopicSelect(topicsData.topics[0].name);
            } else if (topicsData.topics.length > 0) {
                setShowTopicModal(true);
            } else {
                // Fallback if no specific topics found
                setError("No specific topics were identified in the analysis. Try explaining the main title!");
                handleTopicSelect(sessionData.title);
            }
        } catch (error) {
            console.error("Failed to load initial data:", error);
            setError("Failed to load session context");
        }
    };

    const handleTopicSelect = async (topic: string) => {
        if (!token) return;
        setSelectedTopic(topic);
        setMessages([]);
        setShowTopicModal(false);
        setLoadingGreeting(true);
        setError("");
        setEvaluationResult(null);

        try {
            const greetingData = await api.getFeynmanGreeting(token, sessionId, topic);
            setMessages([{ role: "agent", text: greetingData.response }]);
        } catch (error) {
            console.error("Failed to load greeting:", error);
            setMessages([{
                role: "agent",
                text: `Hi! I'm really curious about ${topic}. Could you explain it to me?`
            }]);
        } finally {
            setLoadingGreeting(false);
        }
    };

    const triggerEvaluation = async () => {
        if (!token || !selectedTopic || messages.length < 4 || isEvaluating) return;

        setIsEvaluating(true);
        try {
            const transcript = messages.map(m => ({ role: m.role, content: m.text }));
            const result = await api.evaluateFeynmanMastery(token, sessionId, selectedTopic, transcript);
            setEvaluationResult(result);

            // Refresh topics to show new mastery %
            const topicsData = await api.getFeynmanTopics(token, sessionId);
            setTopics(topicsData.topics);
        } catch (err) {
            console.error("Evaluation failed:", err);
        } finally {
            setIsEvaluating(false);
        }
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const handleSend = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim() || sending || !token) return;

        const userMsg = input.trim();
        setInput("");
        setMessages(prev => [...prev, { role: "user", text: userMsg }]);
        setSending(true);
        setError("");

        try {
            const result = await api.sendFeynmanMessage(token, sessionId, userMsg, selectedTopic || undefined);
            setMessages(prev => [...prev, { role: "agent", text: result.response }]);

            // Auto-trigger evaluation every 5 user messages
            const userMessageCount = messages.filter(m => m.role === 'user').length + 1;
            if (userMessageCount >= 5 && userMessageCount % 5 === 0) {
                triggerEvaluation();
            }
        } catch (err) {
            console.error("Feynman chat failed:", err);
            setError("Something went wrong. Please try again.");
        } finally {
            setSending(false);
        }
    };

    if (loading || !user) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#FAFBFC]">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-[#0052CC] border-t-transparent"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#FAFBFC] flex flex-col">
            {/* Header */}
            <header className="bg-white border-b border-[#DFE1E6] py-3 px-4 sm:px-6 flex-shrink-0">
                <div className="max-w-4xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-4 min-w-0">
                        <Link
                            href={`/study/${sessionId}`}
                            className="text-[#6B778C] hover:text-[#172B4D] transition-colors text-sm font-medium"
                        >
                            ← Back
                        </Link>
                        <div className="flex flex-col min-w-0">
                            <h1 className="text-base font-semibold text-[#172B4D] truncate">
                                Learn with Feynman
                            </h1>
                            <div className="flex items-center gap-2">
                                <p className="text-xs text-[#6B778C] truncate">{sessionTitle}</p>
                                {selectedTopic && (
                                    <>
                                        <span className="text-[#DFE1E6]">•</span>
                                        <button
                                            onClick={() => setShowTopicModal(true)}
                                            className="text-xs font-medium text-[#0052CC] hover:underline"
                                        >
                                            Topic: {selectedTopic}
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                    {/* Voice/Text Mode Toggle */}
                    <button
                        onClick={() => setIsVoiceMode(!isVoiceMode)}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${isVoiceMode
                            ? "bg-[#6554C0] text-white hover:bg-[#5243AA]"
                            : "bg-[#F4F5F7] text-[#172B4D] hover:bg-[#EBECF0]"
                            }`}
                    >
                        {isVoiceMode ? (
                            <>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                Text Mode
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                                </svg>
                                Voice Mode
                            </>
                        )}
                    </button>
                </div>
            </header>

            {/* Voice Chat Mode */}
            {isVoiceMode ? (
                <main className="flex-1 overflow-hidden">
                    {token && (
                        <VoiceChatPanel
                            sessionId={sessionId}
                            topic={selectedTopic}
                            token={token}
                            onTranscript={(text, role) => {
                                setMessages(prev => [...prev, { role, text }]);
                            }}
                        />
                    )}
                </main>
            ) : (
                <>
                    {/* Chat Area */}
                    <main className="flex-1 overflow-y-auto p-4 sm:p-6">
                        <div className="max-w-3xl mx-auto space-y-4">
                            {/* Welcome Card */}
                            <div className="bg-[#EAE6FF] rounded-lg p-4 mb-6 border border-[#DED9FF]">
                                <div className="flex gap-3">
                                    <div className="w-8 h-8 rounded-full bg-[#6554C0] flex items-center justify-center text-white flex-shrink-0 text-sm">
                                        🎓
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h3 className="text-sm font-semibold text-[#403294]">The Feynman Technique</h3>
                                        <p className="text-xs text-[#403294]/80 mt-0.5 leading-relaxed">
                                            Teach the concept to our AI student. If you can explain it simply enough for a beginner to understand, you've mastered it!
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Mastery Evaluation Card */}
                            {evaluationResult && (
                                <div className="bg-white border-2 border-[#36B37E] rounded-xl p-5 mb-6 shadow-sm">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="w-10 h-10 rounded-full bg-[#E3FCEF] flex items-center justify-center text-[#36B37E] font-bold text-lg">
                                            {evaluationResult.score}%
                                        </div>
                                        <div>
                                            <h4 className="text-sm font-bold text-[#172B4D]">Mastery Achievement</h4>
                                            <p className="text-xs text-[#6B778C]">Based on your recent explanation</p>
                                        </div>
                                    </div>
                                    <div className="bg-[#F4F5F7] rounded-lg p-3 text-xs text-[#172B4D] italic leading-relaxed">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {evaluationResult.feedback}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            )}

                            {messages.map((msg, i) => (
                                <div
                                    key={i}
                                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                                >
                                    <div
                                        className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${msg.role === "user"
                                            ? "bg-[#0052CC] text-white rounded-br-none"
                                            : "bg-white border border-[#DFE1E6] text-[#172B4D] rounded-bl-none shadow-sm"
                                            }`}
                                    >
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                p: ({ node, ...props }) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
                                                strong: ({ node, ...props }) => <strong className="font-bold underline underline-offset-2 decoration-[#4C9AFF]/30" {...props} />,
                                                code: ({ node, ...props }) => (
                                                    <code className={`px-1 py-0.5 rounded text-xs font-mono ${msg.role === 'user' ? 'bg-white/20 text-white' : 'bg-[#F4F5F7] text-[#0052CC]'
                                                        }`} {...props} />
                                                ),
                                                ul: ({ node, ...props }) => <ul className="list-disc ml-4 mb-2" {...props} />,
                                                ol: ({ node, ...props }) => <ol className="list-decimal ml-4 mb-2" {...props} />,
                                                li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                                            }}
                                        >
                                            {msg.text}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            ))}

                            {loadingGreeting && (
                                <div className="flex justify-start">
                                    <div className="bg-white border border-[#DFE1E6] rounded-2xl rounded-bl-none px-4 py-3 shadow-sm">
                                        <div className="flex gap-1">
                                            <div className="w-1.5 h-1.5 bg-[#6B778C] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                            <div className="w-1.5 h-1.5 bg-[#6B778C] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                            <div className="w-1.5 h-1.5 bg-[#6B778C] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {sending && (
                                <div className="flex justify-start">
                                    <div className="bg-white border border-[#DFE1E6] rounded-2xl rounded-bl-none px-4 py-3 shadow-sm">
                                        <div className="flex gap-1">
                                            <div className="w-1.5 h-1.5 bg-[#6B778C] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                            <div className="w-1.5 h-1.5 bg-[#6B778C] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                            <div className="w-1.5 h-1.5 bg-[#6B778C] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {error && (
                                <div className="bg-[#FFEBE6] border border-[#FF8F73] text-[#DE350B] px-4 py-2 rounded text-xs text-center">
                                    {error}
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    </main>

                    {/* Input Area */}
                    <div className="bg-white border-t border-[#DFE1E6] p-4 flex-shrink-0">
                        <form
                            onSubmit={handleSend}
                            className="max-w-3xl mx-auto relative"
                        >
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSend();
                                    }
                                }}
                                placeholder="Explain the concept to the student..."
                                className="w-full bg-[#F4F5F7] border-none rounded-xl pl-4 pr-12 py-3 focus:ring-2 focus:ring-[#4C9AFF] resize-none text-sm min-h-[44px] max-h-32"
                                rows={1}
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || sending}
                                className="absolute right-2 bottom-2 p-1.5 text-[#0052CC] hover:bg-[#DEEBFF] rounded-lg disabled:opacity-30 transition-colors"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                            </button>
                        </form>
                        <p className="text-[10px] text-[#6B778C] text-center mt-2">
                            Shift + Enter for new line. Keep it simple and use analogies!
                        </p>
                    </div>
                    {/* Topic Selection Modal */}
                    {showTopicModal && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                            <div className="absolute inset-0 bg-[#091E42]/50 backdrop-blur-sm" onClick={() => selectedTopic && setShowTopicModal(false)} />
                            <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">
                                <div className="p-6 border-b border-[#DFE1E6]">
                                    <h2 className="text-xl font-bold text-[#172B4D]">Select a Topic to Master</h2>
                                    <p className="text-sm text-[#6B778C] mt-1">Which concept would you like to explain today?</p>
                                </div>
                                <div className="p-2 max-h-[60vh] overflow-y-auto">
                                    {topics.map((topic, i) => (
                                        <button
                                            key={i}
                                            onClick={() => handleTopicSelect(topic.name)}
                                            className={`w-full text-left p-4 rounded-lg transition-all border-2 mb-2 ${selectedTopic === topic.name
                                                ? "border-[#0052CC] bg-[#DEEBFF]"
                                                : "border-transparent hover:bg-[#F4F5F7]"
                                                }`}
                                        >
                                            <div className="flex justify-between items-center mb-2">
                                                <span className={`font-semibold text-sm ${selectedTopic === topic.name ? "text-[#0052CC]" : "text-[#172B4D]"}`}>
                                                    {topic.name}
                                                </span>
                                                {topic.mastery && (
                                                    <span className="text-xs font-bold text-[#36B37E]">
                                                        {topic.mastery.score}% Mastered
                                                    </span>
                                                )}
                                            </div>
                                            <div className="w-full h-1.5 bg-[#DFE1E6] rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-[#36B37E] transition-all duration-500"
                                                    style={{ width: `${topic.mastery?.score || 0}%` }}
                                                />
                                            </div>
                                        </button>
                                    ))}
                                </div>
                                <div className="p-4 bg-[#F4F5F7] text-right">
                                    <button
                                        onClick={() => setShowTopicModal(false)}
                                        disabled={!selectedTopic}
                                        className="px-4 py-2 bg-[#0052CC] text-white rounded font-medium disabled:opacity-50 hover:bg-[#0747A6] transition-colors shadow-sm"
                                    >
                                        {selectedTopic ? "Continue" : "Select a Topic"}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Evaluation Spinner Overlay */}
                    {isEvaluating && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
                            <div className="bg-white/90 backdrop-blur-sm rounded-full px-6 py-3 shadow-xl border border-[#DFE1E6] flex items-center gap-3 animate-bounce">
                                <div className="w-4 h-4 border-2 border-[#36B37E] border-t-transparent rounded-full animate-spin" />
                                <span className="text-sm font-bold text-[#172B4D]">Evaluating your performance...</span>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
