"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface ConversationMessage {
    role: "user" | "agent";
    text: string;
}

interface VoiceChatPanelProps {
    sessionId: string;
    topic: string | null;
    token: string;
    onTranscript?: (text: string, role: "user" | "agent") => void;
    initialHistory?: ConversationMessage[];
}

type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

export default function VoiceChatPanel({
    sessionId,
    topic,
    token,
    onTranscript,
    initialHistory = [],
}: VoiceChatPanelProps) {
    const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
    const [isRecording, setIsRecording] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [audioLevel, setAudioLevel] = useState(0);

    // Track conversation history for memory persistence
    const conversationHistoryRef = useRef<ConversationMessage[]>([...initialHistory]);

    // Track turn completion and audio state for proper icon timing
    const turnCompleteReceivedRef = useRef(false);
    const pendingAgentTextRef = useRef<string>("");

    const wsRef = useRef<WebSocket | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const playbackContextRef = useRef<AudioContext | null>(null); // Separate context for playback
    const mediaStreamRef = useRef<MediaStream | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const animationFrameRef = useRef<number | null>(null);
    const audioQueueRef = useRef<ArrayBuffer[]>([]);
    const isPlayingRef = useRef(false);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const WS_URL = API_BASE.replace("http", "ws");

    // Connect to WebSocket
    const connect = useCallback(async () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        setConnectionState("connecting");
        setError(null);

        try {
            const url = `${WS_URL}/ws/feynman/${sessionId}/voice?token=${token}`;
            const ws = new WebSocket(url);

            ws.onopen = () => {
                console.log("Voice WebSocket connected");
            };

            ws.onmessage = async (event) => {
                try {
                    const message = JSON.parse(event.data);

                    switch (message.type) {
                        case "connected":
                            setConnectionState("connected");
                            // Send conversation history to maintain context
                            if (conversationHistoryRef.current.length > 0) {
                                ws.send(JSON.stringify({
                                    type: "history",
                                    messages: conversationHistoryRef.current
                                }));
                            }
                            // Reset turn state
                            turnCompleteReceivedRef.current = false;
                            pendingAgentTextRef.current = "";
                            break;

                        case "audio":
                            // Queue audio for playback
                            const audioData = base64ToArrayBuffer(message.data);
                            audioQueueRef.current.push(audioData);
                            setIsSpeaking(true); // Start speaking indicator
                            if (!isPlayingRef.current) {
                                playNextAudio();
                            }
                            break;

                        case "transcript":
                            // Accumulate agent transcript text
                            pendingAgentTextRef.current += message.text;
                            onTranscript?.(message.text, "agent");
                            break;

                        case "user_transcript":
                            // User's speech was transcribed - add to history
                            if (message.text?.trim()) {
                                conversationHistoryRef.current.push({
                                    role: "user",
                                    text: message.text.trim()
                                });
                                onTranscript?.(message.text, "user");
                            }
                            break;

                        case "turn_complete":
                            // Mark turn as complete - but don't change icon yet
                            turnCompleteReceivedRef.current = true;
                            // If audio is done playing, finalize now
                            if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
                                finalizeTurn();
                            }
                            break;

                        case "error":
                            setError(message.message);
                            setConnectionState("error");
                            break;
                    }
                } catch (e) {
                    console.error("Failed to parse WebSocket message:", e);
                }
            };

            ws.onerror = (event) => {
                console.error("WebSocket error:", event);
                setError("Connection error");
                setConnectionState("error");
            };

            ws.onclose = () => {
                console.log("WebSocket closed");
                setConnectionState("disconnected");
                stopRecording();
            };

            wsRef.current = ws;
        } catch (e) {
            console.error("Failed to connect:", e);
            setError("Failed to connect to voice chat");
            setConnectionState("error");
        }
    }, [sessionId, token, WS_URL, onTranscript]);

    // Disconnect
    const disconnect = useCallback(() => {
        stopRecording();
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        setConnectionState("disconnected");
    }, []);

    // Start recording
    const startRecording = async () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            await connect();
            // Wait for connection
            await new Promise((resolve) => setTimeout(resolve, 500));
        }

        try {
            // Get microphone access - let browser use native sample rate for better compatibility
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });

            mediaStreamRef.current = stream;

            // Create audio context with default sample rate (browser's native rate)
            const audioContext = new AudioContext();
            audioContextRef.current = audioContext;

            // Create analyser for visualization
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyserRef.current = analyser;

            const source = audioContext.createMediaStreamSource(stream);
            source.connect(analyser);

            // Create ScriptProcessor for audio capture
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            // Get the actual sample rate from the context
            const contextSampleRate = audioContext.sampleRate;
            const targetSampleRate = 16000;

            processor.onaudioprocess = (e) => {
                if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

                const inputData = e.inputBuffer.getChannelData(0);
                
                // Resample to 16kHz if needed
                let resampledData: Float32Array;
                if (contextSampleRate !== targetSampleRate) {
                    const ratio = contextSampleRate / targetSampleRate;
                    const newLength = Math.floor(inputData.length / ratio);
                    resampledData = new Float32Array(newLength);
                    for (let i = 0; i < newLength; i++) {
                        resampledData[i] = inputData[Math.floor(i * ratio)];
                    }
                } else {
                    resampledData = new Float32Array(inputData);
                }
                
                // Convert to 16-bit PCM
                const pcmData = new Int16Array(resampledData.length);
                for (let i = 0; i < resampledData.length; i++) {
                    pcmData[i] = Math.max(-32768, Math.min(32767, resampledData[i] * 32768));
                }

                // Send to WebSocket as base64
                const base64 = arrayBufferToBase64(pcmData.buffer);
                wsRef.current.send(JSON.stringify({ type: "audio", data: base64 }));
            };

            source.connect(processor);
            processor.connect(audioContext.destination);

            setIsRecording(true);
            startAudioVisualization();
        } catch (e) {
            console.error("Failed to start recording:", e);
            setError("Microphone access denied");
        }
    };

    // Stop recording
    const stopRecording = () => {
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((track) => track.stop());
            mediaStreamRef.current = null;
        }

        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }

        // Signal end of turn
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "end_turn" }));
        }

        setIsRecording(false);
        setAudioLevel(0);
    };

    // Audio visualization
    const startAudioVisualization = () => {
        const updateLevel = () => {
            if (!analyserRef.current) return;

            const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
            analyserRef.current.getByteFrequencyData(dataArray);

            // Calculate average level
            const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            setAudioLevel(average / 255);

            animationFrameRef.current = requestAnimationFrame(updateLevel);
        };

        updateLevel();
    };

    // Finalize the agent's turn - called when all audio is done AND turn_complete received
    const finalizeTurn = () => {
        setIsSpeaking(false);
        // Add agent's complete response to conversation history
        if (pendingAgentTextRef.current.trim()) {
            conversationHistoryRef.current.push({
                role: "agent",
                text: pendingAgentTextRef.current.trim()
            });
        }
        // Reset for next turn
        pendingAgentTextRef.current = "";
        turnCompleteReceivedRef.current = false;
    };

    // Play audio from queue
    const playNextAudio = async () => {
        if (audioQueueRef.current.length === 0) {
            isPlayingRef.current = false;
            // Check if turn was already marked complete - if so, finalize now
            if (turnCompleteReceivedRef.current) {
                finalizeTurn();
            }
            return;
        }

        isPlayingRef.current = true;

        const audioData = audioQueueRef.current.shift()!;

        try {
            // Reuse or create playback audio context
            if (!playbackContextRef.current || playbackContextRef.current.state === 'closed') {
                playbackContextRef.current = new AudioContext({ sampleRate: 24000 });
            }
            const audioContext = playbackContextRef.current;

            // Convert PCM to AudioBuffer
            const int16Data = new Int16Array(audioData);
            const float32Data = new Float32Array(int16Data.length);
            for (let i = 0; i < int16Data.length; i++) {
                float32Data[i] = int16Data[i] / 32768;
            }

            const audioBuffer = audioContext.createBuffer(1, float32Data.length, 24000);
            audioBuffer.getChannelData(0).set(float32Data);

            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);

            source.onended = () => {
                playNextAudio();
            };

            source.start();
        } catch (e) {
            console.error("Failed to play audio:", e);
            playNextAudio();
        }
    };

    // Utility functions
    const base64ToArrayBuffer = (base64: string): ArrayBuffer => {
        const binaryString = atob(base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    };

    const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    // Toggle recording
    const toggleRecording = () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    };

    return (
        <div className="flex flex-col items-center justify-center h-full p-8 bg-gradient-to-b from-[#FAFBFC] to-[#F4F5F7]">
            {/* Connection Status */}
            <div className="mb-8 text-center">
                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${connectionState === "connected"
                    ? "bg-[#E3FCEF] text-[#006644]"
                    : connectionState === "connecting"
                        ? "bg-[#FFFAE6] text-[#FF8B00]"
                        : connectionState === "error"
                            ? "bg-[#FFEBE6] text-[#DE350B]"
                            : "bg-[#F4F5F7] text-[#6B778C]"
                    }`}>
                    <span className={`w-2 h-2 rounded-full ${connectionState === "connected"
                        ? "bg-[#36B37E] animate-pulse"
                        : connectionState === "connecting"
                            ? "bg-[#FF8B00] animate-pulse"
                            : connectionState === "error"
                                ? "bg-[#DE350B]"
                                : "bg-[#6B778C]"
                        }`} />
                    {connectionState === "connected" && "Voice chat active"}
                    {connectionState === "connecting" && "Connecting..."}
                    {connectionState === "error" && "Connection error"}
                    {connectionState === "disconnected" && "Click mic to start"}
                </div>
            </div>

            {/* Topic Display */}
            {topic && (
                <div className="mb-6 text-center">
                    <p className="text-sm text-[#6B778C]">Teaching about:</p>
                    <p className="text-lg font-semibold text-[#172B4D]">{topic}</p>
                </div>
            )}

            {/* Microphone Button with Visualization */}
            <div className="relative mb-8">
                {/* Ripple effect when recording */}
                {isRecording && (
                    <>
                        <div
                            className="absolute inset-0 rounded-full bg-[#0052CC] opacity-20 animate-ping"
                            style={{ transform: `scale(${1 + audioLevel * 0.5})` }}
                        />
                        <div
                            className="absolute inset-0 rounded-full bg-[#0052CC] opacity-10"
                            style={{ transform: `scale(${1.2 + audioLevel * 0.3})` }}
                        />
                    </>
                )}

                {/* Speaking indicator */}
                {isSpeaking && (
                    <div className="absolute inset-0 rounded-full bg-[#6554C0] opacity-30 animate-pulse"
                        style={{ transform: "scale(1.3)" }} />
                )}

                <button
                    onClick={toggleRecording}
                    disabled={connectionState === "connecting"}
                    className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-200 shadow-lg ${isRecording
                        ? "bg-[#DE350B] hover:bg-[#BF2600] scale-110"
                        : isSpeaking
                            ? "bg-[#6554C0] cursor-default"
                            : "bg-[#0052CC] hover:bg-[#0747A6] hover:scale-105"
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                    {isRecording ? (
                        // Stop icon
                        <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <rect x="6" y="6" width="12" height="12" rx="2" />
                        </svg>
                    ) : isSpeaking ? (
                        // Speaker icon
                        <svg className="w-10 h-10 text-white animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M11 5l-6 4H2v6h3l6 4V5z" />
                        </svg>
                    ) : (
                        // Microphone icon
                        <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                    )}
                </button>
            </div>

            {/* Audio Level Visualization */}
            {isRecording && (
                <div className="flex items-center gap-1 mb-6 h-8">
                    {[...Array(12)].map((_, i) => (
                        <div
                            key={i}
                            className="w-1.5 bg-[#0052CC] rounded-full transition-all duration-75"
                            style={{
                                height: `${Math.max(4, Math.min(32, (audioLevel * 100) * Math.sin((i + 1) * 0.5 + Date.now() / 100)))}px`,
                                opacity: 0.4 + audioLevel * 0.6,
                            }}
                        />
                    ))}
                </div>
            )}

            {/* Instructions */}
            <div className="text-center max-w-md">
                {isRecording ? (
                    <p className="text-sm text-[#172B4D] font-medium">
                        🎙️ Listening... Explain the concept to your student!
                    </p>
                ) : isSpeaking ? (
                    <p className="text-sm text-[#6554C0] font-medium">
                        🗣️ Student is responding...
                    </p>
                ) : (
                    <p className="text-sm text-[#6B778C]">
                        Press the microphone to start teaching. The AI student will listen and ask questions like a curious beginner.
                    </p>
                )}
            </div>

            {/* Error Display */}
            {error && (
                <div className="mt-6 bg-[#FFEBE6] border border-[#FF8F73] rounded-lg px-4 py-3 text-sm text-[#DE350B]">
                    {error}
                    <button
                        onClick={() => { setError(null); connect(); }}
                        className="ml-2 underline hover:no-underline"
                    >
                        Retry
                    </button>
                </div>
            )}

            {/* Disconnect Button */}
            {connectionState === "connected" && (
                <button
                    onClick={disconnect}
                    className="mt-8 text-sm text-[#6B778C] hover:text-[#DE350B] transition-colors"
                >
                    End voice session
                </button>
            )}
        </div>
    );
}
