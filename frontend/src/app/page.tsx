"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function HomePage() {
  const { user, loading, signInWithGoogle } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.push("/dashboard");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFBFC]">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-[#0052CC] border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-[#DFE1E6]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 bg-[#0052CC] rounded flex items-center justify-center">
                <span className="text-white font-bold text-sm">GL</span>
              </div>
              <span className="text-lg font-semibold text-[#172B4D]">GoLearn</span>
            </div>
            <button
              onClick={signInWithGoogle}
              className="px-4 py-2 text-sm font-medium text-[#0052CC] hover:text-[#0747A6] transition-colors"
            >
              Sign in
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-24">
          <div className="max-w-3xl">
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-[#172B4D] leading-tight mb-4 sm:mb-6">
              Master any subject with AI-powered learning
            </h1>
            <p className="text-base sm:text-xl text-[#6B778C] mb-6 sm:mb-8 leading-relaxed">
              GoLearn uses the Three-Pass Study Method and Leitner System to help you comprehend, retain, and apply knowledge more effectively.
            </p>
            <button
              onClick={signInWithGoogle}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-3 px-6 py-3 bg-[#0052CC] text-white text-base font-medium rounded hover:bg-[#0747A6] transition-colors"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </button>
          </div>
        </div>

        {/* Features */}
        <div className="border-t border-[#DFE1E6] bg-[#FAFBFC]">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
            <h2 className="text-xs sm:text-sm font-semibold text-[#6B778C] uppercase tracking-wide mb-6 sm:mb-8">
              How it works
            </h2>
            <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6 md:gap-8">
              <div className="bg-white rounded-lg border border-[#DFE1E6] p-5 sm:p-6">
                <div className="w-10 h-10 bg-[#DEEBFF] rounded flex items-center justify-center mb-4">
                  <svg className="w-5 h-5 text-[#0052CC]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-[#172B4D] mb-2">1. Explore</h3>
                <p className="text-sm text-[#6B778C] leading-relaxed">
                  Upload a PDF or paste text. Our AI analyzes the structure and identifies key topics and concepts.
                </p>
              </div>
              <div className="bg-white rounded-lg border border-[#DFE1E6] p-5 sm:p-6">
                <div className="w-10 h-10 bg-[#E3FCEF] rounded flex items-center justify-center mb-4">
                  <svg className="w-5 h-5 text-[#36B37E]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h3 className="font-semibold text-[#172B4D] mb-2">2. Engage</h3>
                <p className="text-sm text-[#6B778C] leading-relaxed">
                  Dive deep into explanations, definitions, and examples. Build a solid understanding.
                </p>
              </div>
              <div className="bg-white rounded-lg border border-[#DFE1E6] p-5 sm:p-6 sm:col-span-2 md:col-span-1">
                <div className="w-10 h-10 bg-[#EAE6FF] rounded flex items-center justify-center mb-4">
                  <svg className="w-5 h-5 text-[#6554C0]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-[#172B4D] mb-2">3. Apply</h3>
                <p className="text-sm text-[#6B778C] leading-relaxed">
                  Test your knowledge with AI-generated quizzes. Spaced repetition ensures long-term retention.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="border-t border-[#DFE1E6] py-6 sm:py-8">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center text-sm text-[#6B778C]">
            Built with Google Gemini AI
          </div>
        </footer>
      </main>
    </div>
  );
}
