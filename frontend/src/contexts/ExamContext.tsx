"use client";

/**
 * Exam Context for managing global exam generation state.
 * Persists across page navigation and handles polling.
 */
import {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    ReactNode,
} from "react";
import { api } from "@/lib/api";
import { useAuth } from "./AuthContext";

// Exam state for a single session
interface ExamState {
    status: "idle" | "generating" | "ready" | "error";
    pdfUrl?: string;
    error?: string;
    generatedAt?: string;
}

// Context type
interface ExamContextType {
    examStates: Record<string, ExamState>;
    startExamGeneration: (sessionId: string, file: File) => Promise<void>;
    getExamStatus: (sessionId: string) => ExamState;
    refreshExamStatus: (sessionId: string) => Promise<void>;
    resetExamStatus: (sessionId: string) => Promise<void>;
}

const ExamContext = createContext<ExamContextType | undefined>(undefined);

// Polling interval in milliseconds
const POLL_INTERVAL = 5000;

export function ExamProvider({ children }: { children: ReactNode }) {
    const { token } = useAuth();
    const [examStates, setExamStates] = useState<Record<string, ExamState>>({});
    const [pollingSessionIds, setPollingSessionIds] = useState<Set<string>>(new Set());

    // Poll for status updates on generating sessions
    useEffect(() => {
        if (!token || pollingSessionIds.size === 0) return;

        const pollStatus = async () => {
            for (const sessionId of pollingSessionIds) {
                try {
                    const status = await api.getExamStatus(token, sessionId);

                    setExamStates((prev) => ({
                        ...prev,
                        [sessionId]: {
                            status: status.status as ExamState["status"],
                            pdfUrl: status.pdf_url,
                            error: status.error,
                            generatedAt: status.generated_at,
                        },
                    }));

                    // Stop polling if no longer generating
                    if (status.status !== "generating") {
                        setPollingSessionIds((prev) => {
                            const next = new Set(prev);
                            next.delete(sessionId);
                            return next;
                        });
                    }
                } catch (error) {
                    console.error(`Failed to poll exam status for ${sessionId}:`, error);
                }
            }
        };

        // Initial poll
        pollStatus();

        // Set up interval
        const interval = setInterval(pollStatus, POLL_INTERVAL);

        return () => clearInterval(interval);
    }, [token, pollingSessionIds]);

    // Start exam generation
    const startExamGeneration = useCallback(
        async (sessionId: string, file: File) => {
            if (!token) throw new Error("Not authenticated");

            // Set status to generating immediately
            setExamStates((prev) => ({
                ...prev,
                [sessionId]: { status: "generating" },
            }));

            try {
                // Call API to start generation
                await api.startExamGeneration(token, sessionId, file);

                // Start polling
                setPollingSessionIds((prev) => new Set(prev).add(sessionId));
            } catch (error) {
                setExamStates((prev) => ({
                    ...prev,
                    [sessionId]: {
                        status: "error",
                        error: error instanceof Error ? error.message : "Unknown error",
                    },
                }));
                throw error;
            }
        },
        [token]
    );

    // Get exam status for a session
    const getExamStatus = useCallback(
        (sessionId: string): ExamState => {
            return examStates[sessionId] || { status: "idle" };
        },
        [examStates]
    );

    // Manually refresh status from server
    const refreshExamStatus = useCallback(
        async (sessionId: string) => {
            if (!token) return;

            try {
                const status = await api.getExamStatus(token, sessionId);

                setExamStates((prev) => ({
                    ...prev,
                    [sessionId]: {
                        status: status.status as ExamState["status"],
                        pdfUrl: status.pdf_url,
                        error: status.error,
                        generatedAt: status.generated_at,
                    },
                }));

                // Start polling if generating
                if (status.status === "generating") {
                    setPollingSessionIds((prev) => new Set(prev).add(sessionId));
                }
            } catch (error) {
                console.error(`Failed to refresh exam status for ${sessionId}:`, error);
            }
        },
        [token]
    );

    // Reset exam status to idle
    const resetExamStatus = useCallback(
        async (sessionId: string) => {
            if (!token) return;

            try {
                await api.resetExamStatus(token, sessionId);

                setExamStates((prev) => ({
                    ...prev,
                    [sessionId]: { status: "idle" },
                }));
            } catch (error) {
                console.error(`Failed to reset exam status for ${sessionId}:`, error);
            }
        },
        [token]
    );

    return (
        <ExamContext.Provider
            value={{
                examStates,
                startExamGeneration,
                getExamStatus,
                refreshExamStatus,
                resetExamStatus,
            }}
        >
            {children}
        </ExamContext.Provider>
    );
}

export function useExam() {
    const context = useContext(ExamContext);
    if (context === undefined) {
        throw new Error("useExam must be used within an ExamProvider");
    }
    return context;
}
