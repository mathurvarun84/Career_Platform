import { useEffect, useRef, useState } from "react";

import { MOCK_SSE_EVENTS } from "../mocks/mockData";
import type { SSEProgressEvent } from "../types/index";
import { IS_MOCK } from "./useMockData";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const useSSE = (
  jobId: string | null
): { progress: SSEProgressEvent | null; error: string | null } => {
  const [progress, setProgress] = useState<SSEProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const statusRef = useRef<SSEProgressEvent["status"]>("running");

  useEffect(() => {
    const closeSource = (): void => {
      sourceRef.current?.close();
      sourceRef.current = null;
    };

    if (!jobId) {
      setProgress(null);
      setError(null);
      closeSource();
      return closeSource;
    }

    setError(null);
    statusRef.current = "running";

    if (IS_MOCK) {
      const timers = MOCK_SSE_EVENTS.map((event, index) =>
        window.setTimeout(() => {
          statusRef.current = event.status;
          setProgress(event);
        }, (index + 1) * 500)
      );

      timers.push(
        window.setTimeout(() => {
          const completeEvent: SSEProgressEvent = {
            status: "complete",
            pct: 100,
          };
          statusRef.current = "complete";
          setProgress(completeEvent);
        }, 3500)
      );

      return () => {
        timers.forEach((timer) => window.clearTimeout(timer));
      };
    }

    const connect = (): void => {
      closeSource();
      const source = new EventSource(`${API_BASE_URL}/api/stream/${jobId}`);
      sourceRef.current = source;

      source.onmessage = (event: MessageEvent<string>) => {
        const nextProgress = JSON.parse(event.data) as SSEProgressEvent;
        statusRef.current = nextProgress.status;
        setProgress(nextProgress);

        if (
          nextProgress.status === "complete" ||
          nextProgress.status === "error"
        ) {
          closeSource();
        }
      };

      source.onerror = () => {
        statusRef.current = "error";
        setError("Connection lost while tracking analysis progress.");
        closeSource();
      };
    };

    const handleVisibilityChange = (): void => {
      if (
        document.visibilityState === "visible" &&
        statusRef.current === "running"
      ) {
        connect();
      }
    };

    connect();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      closeSource();
    };
  }, [jobId]);

  return { progress, error };
};
