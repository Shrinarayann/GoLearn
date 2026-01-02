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

    // Study Sessions
    async createSession(token: string, title: string, content?: string) {
        return this.request<{
            session_id: string;
            title: string;
            status: string;
        }>("/study/sessions", {
            method: "POST",
            token,
            body: { title, content },
        });
    }

    async getSessions(token: string) {
        return this.request<Array<{
            session_id: string;
            title: string;
            status: string;
            created_at: string;
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
        }>>(`/quiz/sessions/${sessionId}/generate`, {
            method: "POST",
            token,
        });
    }

    async getQuestions(token: string, sessionId: string, dueOnly: boolean = false) {
        const url = `/quiz/sessions/${sessionId}/questions${dueOnly ? "?due_only=true" : ""}`;
        return this.request<Array<{
            question_id: string;
            question: string;
            question_type: string;
            difficulty: string;
            concept: string;
            stability: number;
            fsrs_difficulty: number;
            leitner_box: number;
        }>>(url, { token });
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