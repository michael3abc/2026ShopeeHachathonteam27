import type { ActivityPage } from "@/contracts/activity-page";
import type { CaseDetail } from "@/contracts/case-detail";
import type { CreateCaseRequest } from "@/contracts/create-case-request";
import type { CreateCaseResponse } from "@/contracts/create-case-response";
import type { SendMessageRequest } from "@/contracts/send-message-request";
import type { ReviewDecision } from "@/contracts/review-decision";

export const DEMO_USER_REF = "demo_customer";
export const DEMO_REVIEWER_REF = "demo_reviewer";

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(payload?.detail ?? `Request failed (${response.status})`, response.status);
  }
  return (await response.json()) as T;
}

export async function createCase(orderRef: string, initialMessage: string) {
  const payload: CreateCaseRequest = {
    order_ref: orderRef,
    user_ref: DEMO_USER_REF,
    initial_message: initialMessage,
  };
  return request<CreateCaseResponse>("/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCase(caseRef: string) {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseRef)}`, { cache: "no-store" });
}

export function sendCaseMessage(caseRef: string, payload: SendMessageRequest) {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseRef)}/messages`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function caseEventsUrl(caseRef: string) {
  return `${apiBaseUrl}/cases/${encodeURIComponent(caseRef)}/events`;
}

export function submitCaseReview(caseRef: string, payload: ReviewDecision) {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseRef)}/review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCaseActivities(caseRef: string, afterSeq: number) {
  return request<ActivityPage>(
    `/cases/${encodeURIComponent(caseRef)}/activities?after_seq=${afterSeq}&limit=500`,
    { cache: "no-store" },
  );
}

export function caseActivitiesStreamUrl(caseRef: string, afterSeq: number) {
  return `${apiBaseUrl}/cases/${encodeURIComponent(caseRef)}/activities/stream?after_seq=${afterSeq}`;
}
