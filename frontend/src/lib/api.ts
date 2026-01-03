/**
 * API client for communicating with the FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiOptions {
    method?: string;
    body?: unknown;
    token?: string;
}

class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    private async request<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
        const { method = "GET", body, token } = options;

        const headers: Record<string, string> = {
            "Content-Type": "application/json",
        };

        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `API Error: ${response.status}`);
        }

        return response.json();
    }

    // Auth
    async googleSignIn(idToken: string) {
        return this.request<{
            user_id: string;
            email: string;
            display_name: string | null;
            access_token: string;
        }>("/auth/google", {
            method: "POST",
            body: { id_token: idToken },
        });
    }

    async getMe(token: string) {
        return this.request<{
            user_id: string;
            email: string;
            display_name: string | null;
        }>("/auth/me", { token });
    }

    async registerFcmToken(token: string, fcmToken: string) {
        return this.request<{ message: string }>("/notifications/fcm-token", {
            method: "POST",
            token,
            body: { token: fcmToken },
        });
    }

    async triggerNotificationCheck(token: string) {
        return this.request<{ status: string, summary: any }>("/notifications/trigger-check", {
            method: "POST",
            token,
        });
    }

    // Study Sessions
    async createSession(token: string, title: string, content?: string, enableSpacedRepetition: boolean = true) {
        return this.request<{
            session_id: string;
            title: string;
            status: string;
        }>("/study/sessions", {
            method: "POST",
            token,
            body: { title, content, enable_spaced_repetition: enableSpacedRepetition },
        });
    }

    async getSessions(token: string) {
        return this.request<Array<{
            session_id: string;
            title: string;
            status: string;
            created_at: string;
            enable_spaced_repetition?: boolean;
        }>>("/study/sessions", { token });
    }

    async getSession(token: string, sessionId: string) {
        return this.request<{
            session_id: string;
            title: string;
            status: string;
            pdf_filename?: string;
            exploration_result?: Record<string, unknown>;
            engagement_result?: Record<string, unknown>;
            application_result?: Record<string, unknown>;
        }>(`/study/sessions/${sessionId}`, { token });
    }

    async deleteSession(token: string, sessionId: string) {
        return this.request<{ message: string }>(`/study/sessions/${sessionId}`, {
            method: "DELETE",
            token,
        });
    }

    async uploadPdf(token: string, sessionId: string, file: File) {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(
            `${this.baseUrl}/study/sessions/${sessionId}/upload`,
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            }
        );

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Upload failed: ${response.status}`);
        }

        return response.json() as Promise<{
            message: string;
            file_url: string;
            filename: string;
        }>;
    }

    async runComprehension(token: string, sessionId: string, content?: string, pdfFile?: File) {
        // Use FormData if we have a PDF file
        if (pdfFile) {
            const formData = new FormData();
            formData.append("file", pdfFile);
            if (content) {
                // Create a JSON string for the request body
                const blob = new Blob([JSON.stringify({ content })], { type: "application/json" });
                formData.append("request", blob);
            }

            const response = await fetch(`${this.baseUrl}/study/sessions/${sessionId}/comprehend`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `API Error: ${response.status}`);
            }

            return response.json() as Promise<{
                session_id: string;
                status: string;
                exploration: Record<string, unknown>;
                engagement: Record<string, unknown>;
                application: Record<string, unknown>;
            }>;
        }

        // Otherwise use regular JSON request
        return this.request<{
            session_id: string;
            status: string;
            exploration: Record<string, unknown>;
            engagement: Record<string, unknown>;
            application: Record<string, unknown>;
        }>(`/study/sessions/${sessionId}/comprehend`, {
            method: "POST",
            token,
            body: content ? { content } : {},
        });
    }

    /**
     * Run comprehension with SSE streaming.
     * Results are progressively returned via callbacks as each phase completes.
     */
    async runComprehensionStream(
        token: string,
        sessionId: string,
        callbacks: {
            onExploration?: (data: Record<string, unknown>) => void;
            onEngagement?: (data: Record<string, unknown>) => void;
            onApplication?: (data: Record<string, unknown>) => void;
            onStatus?: (message: string) => void;
            onError?: (error: Error) => void;
            onComplete?: () => void;
        },
        content?: string,
        pdfFile?: File
    ): Promise<void> {
        const formData = new FormData();
        
        if (pdfFile) {
            formData.append("file", pdfFile);
        }
        if (content) {
            const blob = new Blob([JSON.stringify({ content })], { type: "application/json" });
            formData.append("request", blob);
        }

        const response = await fetch(
            `${this.baseUrl}/study/sessions/${sessionId}/comprehend-stream`,
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            }
        );

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `API Error: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            switch (data.phase) {
                                case "exploration":
                                    callbacks.onExploration?.(data.data);
                                    break;
                                case "engagement":
                                    callbacks.onEngagement?.(data.data);
                                    break;
                                case "application":
                                    callbacks.onApplication?.(data.data);
                                    break;
                                case "status":
                                    callbacks.onStatus?.(data.message);
                                    break;
                                case "complete":
                                    callbacks.onComplete?.();
                                    break;
                                case "error":
                                    callbacks.onError?.(new Error(data.message));
                                    break;
                            }
                        } catch (e) {
                            console.error("Failed to parse SSE data:", e);
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }

    // Quiz
    async generateQuiz(token: string, sessionId: string) {
        return this.request<Array<{
            question_id: string;
            question: string;
            question_type: string;
            difficulty: string;
            concept: string;
            stability: number;
            fsrs_difficulty: number;
            leitner_box: number;
            user_answer?: string;
            session_id?: string;
        }>>(`/quiz/sessions/${sessionId}/generate`, {
            method: "POST",
            token,
        });
    }

    async getQuestions(token: string, sessionId: string, dueOnly: boolean = false, resume: boolean = false) {
        const params = new URLSearchParams();
        if (dueOnly) params.append("due_only", "true");
        if (resume) params.append("resume", "true");
        const query = params.toString() ? `?${params.toString()}` : "";
        return this.request<Array<{
            question_id: string;
            question: string;
            question_type: string;
            difficulty: string;
            concept: string;
            stability: number;
            fsrs_difficulty: number;
            leitner_box: number;
            user_answer?: string;
            session_id?: string;
        }>>(`/quiz/sessions/${sessionId}/questions${query}`, { token });
    }

    async submitAnswer(token: string, questionId: string, answer: string) {
        return this.request<{
            correct: boolean;
            correct_answer: string;
            explanation: string;
            new_stability: number;
            new_difficulty: number;
            next_review_at: string;
            new_leitner_box?: number;
            feedback?: string;
        }>(`/quiz/questions/${questionId}/answer`, {
            method: "POST",
            token,
            body: { answer },
        });
    }

    async submitAnswerAsync(token: string, questionId: string, answer: string) {
        return this.request<{
            status: string;
            question_id: string;
            message: string;
        }>(`/quiz/questions/${questionId}/submit`, {
            method: "POST",
            token,
            body: { answer },
        });
    }

    async getQuizResults(token: string, sessionId: string) {
        return this.request<{
            session_id: string;
            total_questions: number;
            evaluated_count: number;
            correct_count: number;
            results: Array<{
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
            }>;
        }>(`/quiz/sessions/${sessionId}/results`, { token });
    }

    async getProgress(token: string, sessionId: string) {
        return this.request<{
            session_id: string;
            total_concepts: number;
            box_distribution: Record<number, number>;
            mastery_percentage: number;
            due_for_review: number;
        }>(`/quiz/sessions/${sessionId}/progress`, { token });
    }

    async getGlobalDueQuestions(token: string) {
        return this.request<Array<{
            question_id: string;
            question: string;
            question_type: string;
            difficulty: string;
            concept: string;
            leitner_box: number;
            session_id: string;
            session_title: string;
            user_answer?: string;
        }>>("/quiz/questions/global", { token });
    }

    async getGlobalProgress(token: string) {
        return this.request<{
            total_due: number;
            total_concepts: number;
            overall_mastery_percentage: number;
            sessions_breakdown: Array<{
                session_id: string;
                title: string;
                due_count: number;
                total: number;
                mastery_percentage: number;
            }>;
        }>("/quiz/progress/global", { token });
    }

    async getDashboardData(token: string) {
        return this.request<{
            sessions: Array<{
                session_id: string;
                title: string;
                status: string;
                created_at: string;
                enable_spaced_repetition?: boolean;
            }>;
            global_progress: {
                total_due: number;
                total_concepts: number;
                overall_mastery_percentage: number;
            };
            sessions_progress: Array<{
                session_id: string;
                due_count: number;
                total: number;
                mastery_percentage: number;
            }>;
        }>("/dashboard/data", { token });
    }

    // Feynman Methods
    async sendFeynmanMessage(token: string, sessionId: string, message: string, topic?: string) {
        let endpoint = `/feynman/sessions/${sessionId}/chat`;
        if (topic) {
            const params = new URLSearchParams();
            params.append("topic", topic);
            endpoint += `?${params.toString()}`;
        }

        return this.request<{
            response: string;
        }>(endpoint, {
            method: "POST",
            token,
            body: { message },
        });
    }

    async getFeynmanGreeting(token: string, sessionId: string, topic?: string) {
        let endpoint = `/feynman/sessions/${sessionId}/greeting`;
        if (topic) {
            const params = new URLSearchParams();
            params.append("topic", topic);
            endpoint += `?${params.toString()}`;
        }

        return this.request<{
            response: string;
        }>(endpoint, { token });
    }

    async getFeynmanTopics(token: string, sessionId: string) {
        return this.request<{
            topics: Array<{
                name: string;
                mastery?: {
                    score: number;
                    updated_at?: string;
                };
            }>;
        }>(`/feynman/sessions/${sessionId}/topics`, { token });
    }

    async evaluateFeynmanMastery(token: string, sessionId: string, topic: string, transcript: Array<{ role: string; content: string }>) {
        return this.request<{
            score: number;
            feedback: string;
        }>(`/feynman/sessions/${sessionId}/evaluate`, {
            method: "POST",
            token,
            body: { topic, transcript },
        });
    }

    // Voice Chat
    getVoiceWebSocketUrl(sessionId: string, token: string): string {
        const wsBase = this.baseUrl.replace('http', 'ws');
        return `${wsBase}/ws/feynman/${sessionId}/voice?token=${token}`;
    }

    // Exam Generation
    async startExamGeneration(token: string, sessionId: string, file: File) {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(
            `${this.baseUrl}/exam/generate/${sessionId}`,
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            }
        );

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Exam generation failed: ${response.status}`);
        }

        return response.json() as Promise<{
            message: string;
            status: string;
        }>;
    }

    async getExamStatus(token: string, sessionId: string) {
        return this.request<{
            status: string;
            pdf_url?: string;
            error?: string;
            generated_at?: string;
        }>(`/exam/sessions/${sessionId}/status`, { token });
    }

    async resetExamStatus(token: string, sessionId: string) {
        return this.request<{
            message: string;
        }>(`/exam/sessions/${sessionId}/reset`, {
            method: "DELETE",
            token,
        });
    }
}

export const api = new ApiClient(API_BASE_URL);