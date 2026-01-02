"use client";

import { useState, useEffect, useCallback } from "react";

type TimerState = "idle" | "working" | "break_prompt" | "short_break" | "long_break";

interface PomodoroTimerProps {
    autoStart?: boolean;
    onPomodoroComplete?: () => void;
}

const WORK_DURATION = 25 * 60; // 25 minutes
const SHORT_BREAK_DURATION = 5 * 60; // 5 minutes
const LONG_BREAK_DURATION = 15 * 60; // 15 minutes
const POMODOROS_BEFORE_LONG_BREAK = 4;

export default function PomodoroTimer({ autoStart = true, onPomodoroComplete }: PomodoroTimerProps) {
    const [timeLeft, setTimeLeft] = useState(WORK_DURATION);
    const [timerState, setTimerState] = useState<TimerState>("idle");
    const [isRunning, setIsRunning] = useState(false);
    const [completedPomodoros, setCompletedPomodoros] = useState(0);
    const [showBreakModal, setShowBreakModal] = useState(false);
    const [showBreakEndModal, setShowBreakEndModal] = useState(false);

    // Auto-start on mount
    useEffect(() => {
        if (autoStart && timerState === "idle") {
            setTimerState("working");
            setTimeLeft(WORK_DURATION);
            setIsRunning(true);
        }
    }, [autoStart, timerState]);

    // Format time as mm:ss
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    // Play notification sound
    const playNotification = useCallback(() => {
        try {
            const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = 800;
            oscillator.type = "sine";
            gainNode.gain.value = 0.3;

            oscillator.start();
            setTimeout(() => {
                oscillator.stop();
                audioContext.close();
            }, 200);
        } catch (e) {
            console.log("Audio not supported");
        }
    }, []);

    // Timer countdown effect
    useEffect(() => {
        let interval: NodeJS.Timeout;

        if (isRunning && timeLeft > 0) {
            interval = setInterval(() => {
                setTimeLeft((prev) => prev - 1);
            }, 1000);
        } else if (timeLeft === 0 && isRunning) {
            setIsRunning(false);
            playNotification();

            if (timerState === "working") {
                const newCount = completedPomodoros + 1;
                setCompletedPomodoros(newCount);
                onPomodoroComplete?.();
                setShowBreakModal(true);
                setTimerState("break_prompt");
            } else if (timerState === "short_break" || timerState === "long_break") {
                setShowBreakEndModal(true);
            }
        }

        return () => clearInterval(interval);
    }, [isRunning, timeLeft, timerState, completedPomodoros, onPomodoroComplete, playNotification]);

    const toggleTimer = () => {
        if (timerState === "idle") {
            setTimerState("working");
            setTimeLeft(WORK_DURATION);
            setIsRunning(true);
        } else {
            setIsRunning(!isRunning);
        }
    };

    const resetTimer = () => {
        setIsRunning(false);
        setTimerState("working");
        setTimeLeft(WORK_DURATION);
        setIsRunning(true);
    };

    const handleTakeBreak = () => {
        setShowBreakModal(false);
        const isLongBreak = completedPomodoros % POMODOROS_BEFORE_LONG_BREAK === 0;
        if (isLongBreak) {
            setTimerState("long_break");
            setTimeLeft(LONG_BREAK_DURATION);
        } else {
            setTimerState("short_break");
            setTimeLeft(SHORT_BREAK_DURATION);
        }
        setIsRunning(true);
    };

    const handleContinueWorking = () => {
        setShowBreakModal(false);
        setTimerState("working");
        setTimeLeft(WORK_DURATION);
        setIsRunning(true);
    };

    const handleBreakEnd = () => {
        setShowBreakEndModal(false);
        setTimerState("working");
        setTimeLeft(WORK_DURATION);
        setIsRunning(true);
    };

    // Get state info
    const getStateInfo = () => {
        switch (timerState) {
            case "working":
                return { label: "Focus", color: "text-[#0052CC]", bg: "bg-[#DEEBFF]", border: "border-[#B3D4FF]" };
            case "short_break":
                return { label: "Break", color: "text-[#36B37E]", bg: "bg-[#E3FCEF]", border: "border-[#ABF5D1]" };
            case "long_break":
                return { label: "Long Break", color: "text-[#6554C0]", bg: "bg-[#EAE6FF]", border: "border-[#C0B6F2]" };
            default:
                return { label: "Ready", color: "text-[#6B778C]", bg: "bg-[#F4F5F7]", border: "border-[#DFE1E6]" };
        }
    };

    const stateInfo = getStateInfo();

    return (
        <>
            {/* Compact Inline Timer */}
            <div className={`inline-flex items-center gap-3 px-4 py-2 rounded-lg ${stateInfo.bg} border ${stateInfo.border}`}>
                {/* Pomodoro count */}
                <div className="flex items-center gap-1">
                    {completedPomodoros > 0 ? (
                        Array.from({ length: Math.min(completedPomodoros, 4) }).map((_, i) => (
                            <span key={i} className="text-sm">🍅</span>
                        ))
                    ) : (
                        <span className="text-sm">🍅</span>
                    )}
                </div>

                {/* State label */}
                <span className={`text-xs font-medium ${stateInfo.color} hidden sm:inline`}>
                    {stateInfo.label}
                </span>

                {/* Timer display */}
                <span className={`font-mono font-bold text-lg ${stateInfo.color} tabular-nums min-w-[60px] text-center`}>
                    {formatTime(timeLeft)}
                </span>

                {/* Pause/Resume button */}
                <button
                    onClick={toggleTimer}
                    className={`p-1.5 rounded-md transition-colors ${isRunning
                            ? "bg-[#FFAB00] hover:bg-[#FF991F] text-white"
                            : "bg-[#0052CC] hover:bg-[#0747A6] text-white"
                        }`}
                    title={isRunning ? "Pause" : "Start"}
                >
                    {isRunning ? (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                    ) : (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11v11.78a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                        </svg>
                    )}
                </button>

                {/* Reset button */}
                <button
                    onClick={resetTimer}
                    className="p-1.5 bg-[#F4F5F7] hover:bg-[#EBECF0] text-[#42526E] rounded-md transition-colors"
                    title="Reset"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                </button>
            </div>

            {/* Break Prompt Modal */}
            {showBreakModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 overflow-hidden animate-in fade-in zoom-in duration-200">
                        <div className="bg-[#E3FCEF] px-6 py-8 text-center">
                            <div className="text-6xl mb-4">🎉</div>
                            <h2 className="text-2xl font-bold text-[#172B4D] mb-2">
                                Great work!
                            </h2>
                            <p className="text-[#42526E]">
                                You've completed a pomodoro. Time for a{" "}
                                {completedPomodoros % POMODOROS_BEFORE_LONG_BREAK === 0
                                    ? "15-minute long break"
                                    : "5-minute short break"}!
                            </p>
                        </div>
                        <div className="p-6 flex gap-3">
                            <button
                                onClick={handleContinueWorking}
                                className="flex-1 bg-[#F4F5F7] hover:bg-[#EBECF0] text-[#42526E] font-medium py-3 px-4 rounded-lg transition-colors"
                            >
                                Continue Working
                            </button>
                            <button
                                onClick={handleTakeBreak}
                                className="flex-1 bg-[#36B37E] hover:bg-[#2A9D6E] text-white font-medium py-3 px-4 rounded-lg transition-colors"
                            >
                                Take a Break
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Break End Modal */}
            {showBreakEndModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 overflow-hidden animate-in fade-in zoom-in duration-200">
                        <div className="bg-[#DEEBFF] px-6 py-8 text-center">
                            <div className="text-6xl mb-4">💪</div>
                            <h2 className="text-2xl font-bold text-[#172B4D] mb-2">
                                Break's over!
                            </h2>
                            <p className="text-[#42526E]">
                                Feeling refreshed? Let's get back to work!
                            </p>
                        </div>
                        <div className="p-6">
                            <button
                                onClick={handleBreakEnd}
                                className="w-full bg-[#0052CC] hover:bg-[#0747A6] text-white font-medium py-3 px-4 rounded-lg transition-colors"
                            >
                                Start Working
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
