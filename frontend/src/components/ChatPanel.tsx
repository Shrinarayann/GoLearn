"use client";

import React, { useState, useRef, useEffect } from 'react';
import styles from './ChatPanel.module.css';

interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp?: string;
}

interface ChatPanelProps {
    sessionId: string;
    isOpen: boolean;
    onClose: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ChatPanel({ sessionId, isOpen, onClose }: ChatPanelProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [streamingContent, setStreamingContent] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, streamingContent]);

    // Focus input when panel opens
    useEffect(() => {
        if (isOpen) {
            inputRef.current?.focus();
            loadHistory();
        }
    }, [isOpen, sessionId]);

    const loadHistory = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/history`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setMessages(data.messages || []);
            }
        } catch (error) {
            console.error('Failed to load chat history:', error);
        }
    };

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setIsLoading(true);
        setStreamingContent('');

        // Add user message to UI immediately
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({ message: userMessage })
            });

            if (!response.ok) throw new Error('Failed to send message');

            // Handle SSE streaming
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let fullContent = '';

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                if (data.content) {
                                    fullContent += data.content;
                                    setStreamingContent(fullContent);
                                }
                                if (data.done) {
                                    // Streaming complete, add to messages
                                    setMessages(prev => [...prev, { role: 'assistant', content: fullContent }]);
                                    setStreamingContent('');
                                }
                                if (data.error) {
                                    console.error('Chat error:', data.error);
                                }
                            } catch (e) {
                                // Ignore parse errors for incomplete chunks
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Chat error:', error);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: 'Sorry, I encountered an error. Please try again.'
            }]);
        } finally {
            setIsLoading(false);
            setStreamingContent('');
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    if (!isOpen) return null;

    return (
        <div className={styles.panel}>
            <div className={styles.header}>
                <h3>Study Assistant</h3>
                <button onClick={onClose} className={styles.closeBtn}>×</button>
            </div>

            <div className={styles.messages}>
                {messages.length === 0 && !streamingContent && (
                    <div className={styles.emptyState}>
                        Ask questions about your study material!
                    </div>
                )}
                {messages.map((msg, i) => (
                    <div key={i} className={`${styles.message} ${styles[msg.role]}`}>
                        <div className={styles.messageContent}>{msg.content}</div>
                    </div>
                ))}
                {streamingContent && (
                    <div className={`${styles.message} ${styles.assistant}`}>
                        <div className={styles.messageContent}>{streamingContent}</div>
                    </div>
                )}
                {isLoading && !streamingContent && (
                    <div className={`${styles.message} ${styles.assistant}`}>
                        <div className={styles.typing}>
                            <span></span><span></span><span></span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className={styles.inputArea}>
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask about your notes..."
                    disabled={isLoading}
                    className={styles.input}
                />
                <button
                    onClick={sendMessage}
                    disabled={isLoading || !input.trim()}
                    className={styles.sendBtn}
                >
                    ➤
                </button>
            </div>
        </div>
    );
}
