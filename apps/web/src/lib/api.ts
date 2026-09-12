import type { ActivityPage } from "@/contracts/activity-page";
import type { CaseDetail } from "@/contracts/case-detail";
import type { CreateCaseRequest } from "@/contracts/create-case-request";
import type { CreateCaseResponse } from "@/contracts/create-case-response";
import type { SendMessageRequest } from "@/contracts/send-message-request";
import type { ReviewDecision } from "@/contracts/review-decision";
import type { AttachmentView } from "@/contracts/attachment-view";
import type { UploadOptions } from "@/contracts/upload-options";
import type { ConversationPage } from "@/contracts/conversation-page";

export const DEMO_USER_REF = "demo_customer";
export const DEMO_REVIEWER_REF = "demo_reviewer";

export type DemoIdentity = { user_ref: string; role: "buyer" | "reviewer" | "operator" };
export const authConfig = () => request<{enabled: boolean}>("/auth/config");
export const getIdentity = () => request<DemoIdentity>("/auth/session");
export const login = (user_ref: string, credential: string) => request<DemoIdentity>("/auth/login", {
  method: "POST", body: JSON.stringify({user_ref, credential}),
});
export const logout = () => request("/auth/logout", {method:"POST"});

export function confirmPolicy(caseRef: string, requestRef: string, version: number, accept: boolean) {
  return request("/cases/" + encodeURIComponent(caseRef) + "/policy-confirmations", {
    method: "POST", body: JSON.stringify({request_ref:requestRef, selection_version:version, accept, idempotency_key:crypto.randomUUID()}),
  });
}

export function confirmReturn(caseRef: string, authorizationRef: string, requirementHash: string, accept: boolean) {
  return request("/cases/" + encodeURIComponent(caseRef) + "/return-confirmations", {
    method: "POST", body: JSON.stringify({authorization_ref:authorizationRef, return_requirement_hash:requirementHash, accept, idempotency_key:crypto.randomUUID()}),
  });
}

export function simulateReturn(caseRef: string, intent: "ARRIVED" | "PASS" | "DISPUTE" | "OVERDUE") {
  return request("/demo/cases/" + encodeURIComponent(caseRef) + "/return-simulation", {
    method: "POST", body: JSON.stringify({intent, idempotency_key:crypto.randomUUID()}),
  });
}

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
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(payload?.detail ?? `Request failed (${response.status})`, response.status);
  }
  return (await response.json()) as T;
}

export async function createCase(
  orderRef: string,
  initialMessage: string,
  userRef = DEMO_USER_REF,
  artifactRefs: string[] = [],
) {
  const payload: CreateCaseRequest = {
    order_ref: orderRef,
    user_ref: userRef,
    initial_message: initialMessage,
    attached_artifact_refs: artifactRefs,
  };
  return request<CreateCaseResponse>("/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getUploadOptions(orderRef: string) {
  return request<UploadOptions>(`/attachments/options?order_ref=${encodeURIComponent(orderRef)}`);
}

export function uploadImage(file: File, orderRef: string, subject: string, caseRef?: string) {
  const body = new FormData();
  body.set("file", file);
  body.set("order_ref", orderRef);
  body.set("subject", subject);
  if (caseRef) body.set("case_ref", caseRef);
  return request<AttachmentView>("/attachments", { method: "POST", body });
}

export function imageContentUrl(attachmentId: string) {
  return `${apiBaseUrl}/attachments/${encodeURIComponent(attachmentId)}/content`;
}

export function getConversation(caseRef: string) {
  return request<ConversationPage>(`/cases/${encodeURIComponent(caseRef)}/conversation`, { cache: "no-store" });
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
