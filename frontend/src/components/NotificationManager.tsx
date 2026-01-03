"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { getToken, onMessage } from "firebase/messaging";
import { messaging } from "@/lib/firebase";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function NotificationManager() {
    const { user, token: idToken } = useAuth();
    const [permission, setPermission] = useState<NotificationPermission>("default");
    const [isRegistering, setIsRegistering] = useState(false);
    const [status, setStatus] = useState<string | null>(null);
    const lastRegisteredToken = useRef<string | null>(null);

    const updatePermission = useCallback(() => {
        if ("Notification" in window) {
            setPermission(Notification.permission);
        }
    }, []);

    useEffect(() => {
        updatePermission();
        window.addEventListener("focus", updatePermission);
        return () => window.removeEventListener("focus", updatePermission);
    }, [updatePermission]);

    const setupNotifications = useCallback(async () => {
        if (!user || !idToken || !messaging) return;
        if (Notification.permission !== "granted") return;

        setIsRegistering(true);
        setStatus("Starting registration...");

        try {
            const vapidKey = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY;

            console.log("Registering Service Worker...");
            const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js', {
                scope: '/'
            });
            await navigator.serviceWorker.ready;

            console.log("Requesting FCM Token...");
            setStatus("Requesting token from Firebase...");
            const fcmToken = await getToken(messaging, {
                vapidKey: vapidKey,
                serviceWorkerRegistration: registration
            });

            if (fcmToken) {
                console.log("SUCCESS! Got FCM Token:", fcmToken);

                // Only register if token has changed
                if (fcmToken !== lastRegisteredToken.current) {
                    setStatus("Token received! Syncing with backend...");
                    await api.registerFcmToken(idToken, fcmToken);
                    lastRegisteredToken.current = fcmToken;
                    console.log("Token synced successfully.");
                } else {
                    console.log("Token unchanged, skipping registration.");
                }

                setStatus(null);
            } else {
                setStatus("Error: Firebase returned an empty token.");
            }
        } catch (err: any) {
            console.error("FCM Error:", err);
            if (err.name === "NotAllowedError" || err.code === "messaging/permission-blocked" || err.message?.includes("permission")) {
                setStatus("CRITICAL ERROR: Browser/Firebase permission mismatch. Please use the 'NUCLEAR RESET' below.");
            } else {
                setStatus(`Error: ${err.message || "Unknown error"}`);
            }
        } finally {
            setIsRegistering(false);
        }
    }, [user, idToken]);

    useEffect(() => {
        if (permission === "granted" && !isRegistering) {
            setupNotifications();
        }
    }, [permission, setupNotifications, isRegistering]);

    const handleRequest = async () => {
        setStatus(null);
        try {
            const result = await Notification.requestPermission();
            setPermission(result);
            if (result === "default") {
                setStatus("Prompt dismissed. Check the URL bar bell icon 🔔.");
            }
        } catch (err) {
            setStatus("Could not show prompt.");
        }
    };

    /**
     * THE NUCLEAR RESET
     * Clears Service Workers, Caches, and crucially, IndexedDB where Firebase stores corrupted states.
     */
    const handleNuclearReset = async () => {
        setIsRegistering(true);
        setStatus("☢️ NUKING ALL DATA...");
        try {
            // 1. Unregister all service workers
            const registrations = await navigator.serviceWorker.getRegistrations();
            for (const r of registrations) await r.unregister();

            // 2. Clear all caches
            const cacheKeys = await caches.keys();
            for (const key of cacheKeys) await caches.delete(key);

            // 3. Clear IndexedDB (The most important step for 'Permission Mismatch' errors)
            const dbs = ['fcm_token_details_db', 'firebase-messaging-database', 'firebase-heartbeat-database', 'firebase-installations-database'];
            for (const dbName of dbs) {
                await new Promise((resolve) => {
                    const req = indexedDB.deleteDatabase(dbName);
                    req.onsuccess = () => resolve(true);
                    req.onerror = () => resolve(false);
                    req.onblocked = () => resolve(false);
                });
            }

            setStatus("☢️ RESET COMPLETE. Reloading...");
            setTimeout(() => window.location.reload(), 1500);
        } catch (err) {
            setStatus("Reset failed. Please open F12 -> Application -> Clear Site Data manually.");
            setIsRegistering(false);
        }
    };

    // Only show modal if permission not granted, or if there's an error/important status
    // Don't show for transient registration status messages
    const shouldShowModal = permission !== "granted" || (status && !isRegistering);

    if (shouldShowModal) {
        return (
            <div className="fixed bottom-4 right-4 z-50 p-6 bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-100 dark:border-gray-700 max-w-sm transition-all animate-in fade-in duration-500">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                    📢 Study Reminders
                </h3>

                <p className="text-sm text-gray-600 dark:text-gray-400 mb-5 leading-relaxed">
                    {permission === "denied"
                        ? "Notifications are blocked. Reset them in your browser URL bar."
                        : status
                            ? status
                            : "Enable notifications to never miss a review session!"}
                </p>

                <div className="flex flex-col gap-3">
                    {permission !== "granted" && (
                        <button onClick={handleRequest} className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold shadow-lg transition-all active:scale-95">
                            Enable Now
                        </button>
                    )}

                    {status && status.includes("ERROR") && (
                        <button onClick={handleNuclearReset} disabled={isRegistering} className="w-full py-3 bg-red-50 hover:bg-red-100 text-red-600 dark:bg-red-900/20 dark:hover:bg-red-900/30 rounded-xl text-sm font-bold transition-all disabled:opacity-50">
                            ☢️ NUCLEAR RESET (Fix mismatch)
                        </button>
                    )}

                    {(permission === "granted" && !status) || (status && !status.includes("ERROR")) ? (
                        <button
                            onClick={() => { setStatus(null); setupNotifications(); }}
                            disabled={isRegistering}
                            className="w-full py-3 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                        >
                            {isRegistering ? "Registering..." : "Try registration again"}
                        </button>
                    ) : null}
                </div>
            </div>
        );
    }

    return null;
}
