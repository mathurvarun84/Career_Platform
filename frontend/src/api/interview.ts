import { IS_MOCK } from "../hooks/useMockData";
import { supabase } from "../lib/supabase";
import {
  MOCK_INTERVIEW_FEEDBACK,
  MOCK_FOLLOW_UP_Q1,
  MOCK_MODEL_ANSWER,
  MOCK_PAST_SESSIONS,
} from "../mocks/mockInterviewData";
import type {
  AntiPatternFired,
  DimensionScore,
  ExecutivePresenceLevel,
  FollowUpQuestion,
  LevelSignal,
  ModelAnswer,
  PastSessionSummary,
  PerQuestionFeedback,
  QuestionMode,
} from "../types";

const authHeaders = async (): Promise<Record<string, string>> => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
};

export const startSession = async (
  company: string,
  seniority: string,
  questionMode: QuestionMode,
  resumeText: string
) => {
  const headers = await authHeaders();
  return fetch("/api/interview/session/start", {
    method: "POST",
    headers,
    body: JSON.stringify({
      company,
      seniority,
      question_mode: questionMode,
      resume_text: resumeText,
    }),
  });
};

export const fetchInterviewSessions = async (): Promise<PastSessionSummary[]> => {
  if (IS_MOCK) {
    await new Promise((r) => setTimeout(r, 300));
    return MOCK_PAST_SESSIONS;
  }

  const headers = await authHeaders();
  const res = await fetch("/api/interview/sessions", { headers });
  if (!res.ok) {
    throw new Error("Could not load interview history");
  }
  const data = (await res.json()) as { sessions: PastSessionSummary[] };
  return data.sessions ?? [];
};

export const fetchModelAnswer = async (
  sessionId: string,
  questionId: string
): Promise<ModelAnswer> => {
  if (IS_MOCK) {
    await new Promise((r) => setTimeout(r, 600));
    return MOCK_MODEL_ANSWER;
  }

  const headers = await authHeaders();
  const res = await fetch(
    `/api/interview/session/${sessionId}/model-answer/${questionId}`,
    { method: "POST", headers }
  );
  if (!res.ok) {
    throw new Error("Could not load model answer");
  }
  return (await res.json()) as ModelAnswer;
};

export const fetchSessionSummary = async (sessionId: string) => {
  const headers = await authHeaders();
  return fetch(`/api/interview/session/${sessionId}/summary`, {
    method: "POST",
    headers,
  });
};

export const submitAnswerSync = (
  sessionId: string,
  questionId: string,
  answerText: string,
  isFollowUp: boolean,
  followUpId?: string
) =>
  authHeaders().then((headers) =>
    fetch(`/api/interview/session/${sessionId}/answer`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        question_id: questionId,
        answer_text: answerText,
        is_follow_up: isFollowUp,
        follow_up_id: followUpId ?? null,
      }),
    })
  );

export type FeedbackChunk =
  | { type: "verdict"; content: string }
  | { type: "best_line"; content: string }
  | { type: "level_signal"; content: LevelSignal }
  | {
      type: "presence";
      content: {
        executive_presence: ExecutivePresenceLevel;
        authenticity_note: string;
      };
    }
  | { type: "dimension"; content: DimensionScore }
  | { type: "missing"; content: string }
  | { type: "ap_fired"; content: AntiPatternFired }
  | { type: "coaching_close"; content: string }
  | { type: "done"; content: null }
  | { type: "error"; content: string };

export type StreamDoneMeta = {
  followUp: FollowUpQuestion | null;
};

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const emitMockChunks = async (
  feedback: PerQuestionFeedback,
  onChunk: (chunk: FeedbackChunk) => void
): Promise<void> => {
  await delay(400);
  onChunk({ type: "verdict", content: feedback.overall_verdict });
  await delay(350);
  onChunk({ type: "best_line", content: feedback.best_line });
  await delay(300);
  onChunk({ type: "level_signal", content: feedback.level_signal });
  await delay(300);
  onChunk({
    type: "presence",
    content: {
      executive_presence: feedback.executive_presence,
      authenticity_note: feedback.authenticity_note,
    },
  });
  await delay(350);
  onChunk({ type: "dimension", content: feedback.dimension_score });
  if (feedback.dimension_score.signal_strength !== "strong") {
    await delay(300);
    onChunk({ type: "missing", content: feedback.dimension_score.what_was_missing });
  }
  for (const ap of feedback.anti_patterns_fired) {
    await delay(250);
    onChunk({ type: "ap_fired", content: ap });
  }
  if (feedback.coaching_close) {
    await delay(300);
    onChunk({ type: "coaching_close", content: feedback.coaching_close });
  }
  await delay(200);
  onChunk({ type: "done", content: null });
};

const submitAnswerStreamMock = (
  _questionId: string,
  isFollowUp: boolean,
  questionIndex: number,
  onChunk: (chunk: FeedbackChunk) => void,
  onDone: (meta: StreamDoneMeta) => void,
  onError: (msg: string) => void
): (() => void) => {
  let cancelled = false;

  const run = async (): Promise<void> => {
    try {
      if (questionIndex === 0 && !isFollowUp) {
        await delay(800);
        if (cancelled) {
          return;
        }
        onChunk({ type: "done", content: null });
        onDone({ followUp: MOCK_FOLLOW_UP_Q1 });
        return;
      }

      const feedback =
        MOCK_INTERVIEW_FEEDBACK[questionIndex] ?? MOCK_INTERVIEW_FEEDBACK[0];
      await emitMockChunks(feedback, (chunk) => {
        if (!cancelled) {
          onChunk(chunk);
        }
      });
      if (!cancelled) {
        onDone({ followUp: null });
      }
    } catch (err) {
      if (!cancelled) {
        onError(err instanceof Error ? err.message : "Mock stream failed");
      }
    }
  };

  void run();

  return () => {
    cancelled = true;
  };
};

export const submitAnswerStream = (
  sessionId: string,
  questionId: string,
  answerText: string,
  isFollowUp: boolean,
  followUpId: string | undefined,
  onChunk: (chunk: FeedbackChunk) => void,
  onDone: (meta?: StreamDoneMeta) => void,
  onError: (msg: string) => void,
  questionIndex?: number,
  followUpCount?: number
): (() => void) => {
  if (IS_MOCK && questionIndex !== undefined) {
    return submitAnswerStreamMock(
      questionId,
      isFollowUp,
      questionIndex,
      onChunk,
      onDone,
      onError
    );
  }

  const controller = new AbortController();

  authHeaders()
    .then((headers) =>
      fetch(`/api/interview/session/${sessionId}/answer/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question_id: questionId,
          answer_text: answerText,
          is_follow_up: isFollowUp,
          follow_up_id: followUpId ?? null,
        }),
        signal: controller.signal,
      })
    )
    .then(async (res) => {
      if (!res) {
        return;
      }
      if (!res.ok) {
        onError(`Stream failed (${res.status})`);
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        onError("No response body");
        return;
      }
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) {
            continue;
          }
          const raw = line.slice(6).trim();
          if (!raw) {
            continue;
          }
          try {
            const chunk = JSON.parse(raw) as FeedbackChunk;
            if (chunk.type === "error") {
              onError(chunk.content as string);
              return;
            }
            if (chunk.type === "done") {
              if (!isFollowUp) {
                const headers = await authHeaders();
                const followUpRes = await fetch(
                  `/api/interview/follow-up?session_id=${encodeURIComponent(sessionId)}`,
                  {
                    method: "POST",
                    headers,
                    body: JSON.stringify({
                      question_id: questionId,
                      answer_text: answerText,
                      follow_up_count: followUpCount ?? 0,
                    }),
                  }
                );
                if (followUpRes.ok) {
                  const data = (await followUpRes.json()) as {
                    follow_up: FollowUpQuestion | null;
                  };
                  onDone({ followUp: data.follow_up });
                } else {
                  onDone({ followUp: null });
                }
              } else {
                onDone({ followUp: null });
              }
              return;
            }
            onChunk(chunk);
          } catch {
            /* malformed — skip */
          }
        }
      }
      onDone({ followUp: null });
    })
    .catch((err: Error) => {
      if (err.name !== "AbortError") {
        onError(err.message);
      }
    });

  return () => controller.abort();
};
