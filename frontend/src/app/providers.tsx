"use client";

import { AuthProvider } from "@/contexts/AuthContext";
import { ExamProvider } from "@/contexts/ExamContext";

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <AuthProvider>
            <ExamProvider>{children}</ExamProvider>
        </AuthProvider>
    );
}
