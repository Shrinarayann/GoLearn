"use client";

import { AuthProvider } from "@/contexts/AuthContext";
import { ExamProvider } from "@/contexts/ExamContext";
import NotificationManager from "@/components/NotificationManager";

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <AuthProvider>
            <NotificationManager />
            <ExamProvider>{children}</ExamProvider>
        </AuthProvider>
    );
}
