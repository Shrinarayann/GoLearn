"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
    role: "user" | "agent";
    text: string;
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
    const [loadingGreeting, setLoadingGreeting] = useState(true);
    const [error, setError] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

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

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const loadSession = async () => {
        if (!token) return;
        try {
            const data = await api.getSession(token, sessionId);
            setSessionTitle(data.title);

            // Fetch contextual greeting
            setLoadingGreeting(true);
            const greetingData = await api.getFeynmanGreeting(token, sessionId);
            setMessages([{ role: "agent", text: greetingData.response }]);
        } catch (error) {
            console.error("Failed to load session:", error);
            setError("Failed to load session context");
            // Fallback greeting
            setMessages([{
                role: "agent",
                text: "Hi! I'm really curious about what you're studying. Could you explain it to me?"
            }]);
        } finally {
            setLoadingGreeting(false);
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
            const result = await api.sendFeynmanMessage(token, sessionId, userMsg);
            setMessages(prev => [...prev, { role: "agent", text: result.response }]);
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
                            <p className="text-xs text-[#6B778C] truncate">{sessionTitle}</p>
                        </div>
                    </div>
                </div>
            </header>

            {/* Chat Area */}
            <main className="flex-1 overflow-y-auto p-4 sm:p-6">
                <div className="max-w-3xl mx-auto space-y-4">
                    {/* Welcome Card */}
                    <div className="bg-[#EAE6FF] rounded-lg p-4 mb-6 border border-[#DED9FF]">
                        <div className="flex gap-3">
                            <div className="w-8 h-8 rounded-full bg-[#6554C0] flex items-center justify-center text-white flex-shrink-0">
                                🎓
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-[#403294]">The Feynman Technique</h3>
                                <p className="text-xs text-[#403294]/80 mt-1">
                                    Teach the concept to our AI student. If you can explain it simply enough for a beginner to understand, you've mastered it!
                                </p>
                            </div>
                        </div>
                    </div>

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
        </div>
    );
}
