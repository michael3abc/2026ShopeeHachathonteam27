"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Bot,
  Check,
  FileImage,
  LoaderCircle,
  Paperclip,
  Send,
  UserRound,
} from "lucide-react";

import { GraphStage } from "@/components/graph-stage";
import { NodeInspector } from "@/components/node-inspector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { AgentEvent } from "@/contracts/agent-event";
import type { CaseDetail, CaseStatus } from "@/contracts/case-detail";
import { caseEventsUrl, DEMO_REVIEWER_REF, getCase, sendCaseMessage, submitCaseReview } from "@/lib/api";
import { graphProgress, withRefundWait } from "@/lib/graph-progress.mjs";
import { parseAgentEvent, presentEvent, statusLabel } from "@/lib/present-event.mjs";
import { useActivityPlayback } from "@/lib/use-activity-playback";
import { useCaseActivities } from "@/lib/use-case-activities";
import { cn } from "@/lib/utils";
import { useDemoIdentity } from "@/components/demo-session";
import { confirmPolicy, confirmReturn, simulateReturn } from "@/lib/api";
import { AttachmentImage, ImageAttachments, type ImageDraft } from "@/components/image-attachments";
import type { ConversationPage } from "@/contracts/conversation-page";
import type { AttachmentView } from "@/contracts/attachment-view";
import { getConversation } from "@/lib/api";

const eventTypes = [
  "node_enter",
  "node_exit",
  "tool_call",
  "tool_result",
  "token",
  "memory_retrieval",
  "interrupt",
  "state_change",
  "done",
  "error",
] as const;

const terminalStatuses = new Set<CaseStatus>(["RESOLVED", "ESCALATED"]);
const projectionEventTypes = new Set<AgentEvent["type"]>([
  "interrupt",
  "state_change",
  "done",
  "error",
]);

type LocalMessage = {
  id: number;
  artifactRef?: string;
  text: string;
  ts: string;
};

type ConversationItem = {
  attachments?: AttachmentView[];
  artifactRef?: string;
  id: string;
  role: "agent" | "user";
  text: string;
  ts: string;
};

function formatClock(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusStyle(status: CaseStatus) {
  if (status === "RESOLVED") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "ESCALATED") return "border-red-200 bg-red-50 text-red-700";
  if (status.startsWith("AWAITING")) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-orange-200 bg-orange-50 text-orange-700";
}

function connectionLabel(connection: "connecting" | "live" | "reconnecting" | "closed") {
  if (connection === "live") return "LIVE";
  if (connection === "closed") return "DONE";
  if (connection === "reconnecting") return "RECONNECTING";
  return "CONNECTING";
}

export function CaseWorkspace({ caseRef }: { caseRef: string }) {
  const identity = useDemoIdentity();
  const [detail, setDetail] = useState<CaseDetail>();
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [localMessages, setLocalMessages] = useState<LocalMessage[]>([]);
  const [selectedNode, setSelectedNode] = useState<string>();
  const [sidePanel, setSidePanel] = useState<"inspector" | "review">();
  const [connection, setConnection] = useState<"connecting" | "live" | "reconnecting" | "closed">(
    "connecting",
  );
  const [loadError, setLoadError] = useState<string>();
  const activityFeed = useCaseActivities(caseRef);
  const playback = useActivityPlayback(activityFeed.activities);
  const progress = useMemo(() => graphProgress(playback.visible), [playback.visible]);

  // Projection reads run concurrently (one per event), so a slow older response
  // must never overwrite a newer one and rewind the case on screen.
  const issuedReads = useRef(0);
  const appliedRead = useRef(0);

  const refresh = useCallback(async () => {
    const ticket = ++issuedReads.current;
    const next = await getCase(caseRef);
    if (ticket >= appliedRead.current) {
      appliedRead.current = ticket;
      setDetail(next);
    }
    return next;
  }, [caseRef]);

  useEffect(() => {
    let disposed = false;
    let source: EventSource | undefined;

    async function start() {
      try {
        await refresh();
        if (disposed) return;
        source = new EventSource(caseEventsUrl(caseRef), {withCredentials:true});
        source.onopen = () => setConnection("live");
        source.onerror = () => {
          if (!disposed) setConnection("reconnecting");
        };
        for (const type of eventTypes) {
          source.addEventListener(type, (message) => {
            const event = parseAgentEvent(message);
            if (!event) return;
            setEvents((current) => {
              if (current.some((item) => item.seq === event.seq)) return current;
              return [...current, event].sort((left, right) => left.seq - right.seq);
            });
            if (projectionEventTypes.has(event.type)) {
              void refresh().catch(() => setConnection("reconnecting"));
            }
            if (event.type === "done") {
              source?.close();
              setConnection("closed");
            }
          });
        }
      } catch (caught) {
        if (!disposed) {
          setLoadError(caught instanceof Error ? caught.message : "無法讀取案件");
          setConnection("closed");
        }
      }
    }

    void start();
    return () => {
      disposed = true;
      source?.close();
    };
  }, [caseRef, refresh]);

  if (loadError) {
    return (
      <main className="grid min-h-screen place-items-center bg-stone-50 p-6">
        <Card className="max-w-md p-8 text-center">
          <AlertCircle className="mx-auto size-10 text-red-500" />
          <h1 className="mt-4 text-xl font-bold text-stone-950">找不到這個案件</h1>
          <p className="mt-2 text-sm text-stone-500">{loadError}</p>
          <Button asChild className="mt-6" variant="outline">
            <Link href="/">回到首頁</Link>
          </Button>
        </Card>
      </main>
    );
  }

  if (!detail) {
    return (
      <main className="grid min-h-screen place-items-center bg-stone-50 text-stone-500">
        <div className="flex items-center gap-3 text-sm font-medium">
          <LoaderCircle className="size-5 animate-spin text-orange-600" /> 載入案件中
        </div>
      </main>
    );
  }

  // Explain a stalled refund only once playback has caught up with the case.
  const caughtUp = playback.visible.length === activityFeed.activities.length;
  const stageProgress = caughtUp ? withRefundWait(progress, detail.status) : progress;
  // The inspector follows the running node until a node is picked on the stage.
  const inspectedNode = selectedNode ?? stageProgress.activeNode ?? stageProgress.lastNode ?? "parse_request";
  const canReview = !identity || identity.role === "reviewer";
  const activePanel = canReview ? sidePanel ?? (detail.human_review ? "review" : "inspector") : "inspector";

  return (
    <main className="flex min-h-screen flex-col bg-stone-100 xl:h-screen">
      <CaseHeader detail={detail} connection={connection} />
      <div className="flex flex-col gap-3 p-3 xl:min-h-0 xl:flex-1">
        <GraphStage
          policyVersion={detail.policy_schema_version}
          onSelectNode={(node) => {
            setSelectedNode(node);
            setSidePanel("inspector");
          }}
          playback={{
            speed: playback.speed,
            remainingSteps: playback.remainingSteps,
            onSpeedChange: playback.changeSpeed,
            onSkipToLatest: playback.skipToLatest,
          }}
          progress={stageProgress}
          selectedNode={inspectedNode}
          unavailable={activityFeed.unavailable}
        />
        <FulfillmentPanel detail={detail} onUpdated={refresh} />
        <div className="grid gap-3 xl:min-h-[420px] xl:flex-1 xl:grid-cols-[minmax(420px,1fr)_minmax(480px,1.15fr)]">
          <ConversationPanel
            detail={detail}
            events={events}
            localMessages={localMessages}
            onMessageSent={(message) => setLocalMessages((current) => [...current, message])}
            onUpdated={refresh}
          />
          <div className="flex min-h-[560px] flex-col gap-2 xl:min-h-0">
            <div aria-label="案件側欄" className="flex gap-1 rounded-xl bg-stone-200/70 p-1" role="tablist">
              <SidePanelTab active={activePanel === "inspector"} onSelect={() => setSidePanel("inspector")}>
                節點檢視
              </SidePanelTab>
              {canReview && <SidePanelTab
                active={activePanel === "review"}
                attention={detail.status === "AWAITING_HUMAN_REVIEW"}
                onSelect={() => setSidePanel("review")}
              >
                人工審核
              </SidePanelTab>}
            </div>
            {activePanel === "inspector" ? (
              <NodeInspector
                events={events}
                node={inspectedNode}
                onFollowCurrent={selectedNode ? () => setSelectedNode(undefined) : undefined}
                progress={stageProgress}
              />
            ) : (
              <div className="flex min-h-0 flex-1 flex-col [&>*]:flex-1">
                <ReviewerPanel key={`${detail.case_ref}:${detail.human_review?.handoff_id}`} detail={detail} onUpdated={refresh} />
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

function SidePanelTab({
  active,
  attention = false,
  children,
  onSelect,
}: {
  active: boolean;
  attention?: boolean;
  children: ReactNode;
  onSelect: () => void;
}) {
  return (
    <button
      aria-selected={active}
      className={cn(
        "flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500",
        active ? "bg-white text-stone-950 shadow-sm" : "text-stone-500 hover:text-stone-800",
      )}
      onClick={onSelect}
      role="tab"
      type="button"
    >
      <span className="text-xs font-semibold">{children}</span>
      {attention ? <span aria-label="需要處理" className="size-2 rounded-full bg-orange-500" role="img" /> : null}
    </button>
  );
}

function CaseHeader({
  detail,
  connection,
}: {
  detail: CaseDetail;
  connection: "connecting" | "live" | "reconnecting" | "closed";
}) {
  return (
    <header className="flex h-[66px] shrink-0 items-center justify-between gap-4 border-b border-stone-200 bg-white px-4 sm:px-6">
      <Link className="flex items-center gap-3" href="/" aria-label="回到案件首頁">
        <span className="grid size-9 place-items-center rounded-xl bg-orange-600 font-black text-white">
          R
        </span>
        <span className="hidden sm:block">
          <strong className="block text-sm text-stone-950">ReturnFlow</strong>
          <span className="block text-[11px] text-stone-400">退貨處理中心</span>
        </span>
      </Link>
      <div className="flex min-w-0 items-center gap-3">
        <span className="size-2 shrink-0 rounded-full bg-emerald-500 shadow-[0_0_0_5px_rgba(34,197,94,0.12)]" />
        <span className="min-w-0">
          <strong className="block truncate font-mono text-sm text-stone-900">{detail.case_ref}</strong>
          <span className="block truncate text-[11px] text-stone-400">
            {detail.order_ref} · {statusLabel(detail.status)}
          </span>
        </span>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <Badge className={cn("hidden sm:inline-flex", statusStyle(detail.status))}>
          {connectionLabel(connection)}
        </Badge>
        <span className="grid size-8 place-items-center rounded-full bg-stone-900 text-[10px] font-bold text-white">
          DC
        </span>
        <span className="hidden text-xs font-medium text-stone-500 md:inline">{detail.user_ref}</span>
      </div>
    </header>
  );
}

function ConversationPanel({
  detail,
  events,
  localMessages,
  onMessageSent,
  onUpdated,
}: {
  detail: CaseDetail;
  events: AgentEvent[];
  localMessages: LocalMessage[];
  onMessageSent: (message: LocalMessage) => void;
  onUpdated: () => Promise<CaseDetail>;
}) {
  const identity = useDemoIdentity();
  const [message, setMessage] = useState("");
  const [artifactRef, setArtifactRef] = useState("");
  const [images, setImages] = useState<ImageDraft[]>([]);
  const [history, setHistory] = useState<ConversationPage>();
  const [historyError, setHistoryError] = useState<string>();
  const [submittedVersion, setSubmittedVersion] = useState<string>();
  const projectionVersion = detail.status + ":" + detail.updated_at;
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const needsInput =
    (!identity || identity.role === "buyer") &&
    submittedVersion !== projectionVersion &&
    (detail.status === "AWAITING_CLARIFICATION" || detail.status === "AWAITING_EVIDENCE");
  const isEvidence = detail.status === "AWAITING_EVIDENCE";
  const isAgentWorking = detail.status === "OBSERVING";

  useEffect(() => {
    let alive = true;
    getConversation(detail.case_ref).then(value => {
      if (alive) { setHistory(value); setHistoryError(undefined); }
    }).catch(cause => { if (alive) setHistoryError(cause instanceof Error ? cause.message : "對話讀取失敗"); });
    return () => { alive = false; };
  }, [detail.case_ref, detail.updated_at, localMessages.length]);

  const conversation = useMemo<ConversationItem[]>(() => {
    const startedAt = new Date(detail.created_at).getTime();
    const items: ConversationItem[] = [
      {
        id: "agent-started",
        role: "agent",
        text: "我已收到案件，正在檢查訂單、政策與佐證資料。",
        ts: new Date(Math.max(startedAt, history?.turns[0] ? Date.parse(history.turns[0].created_at) : startedAt) + 1).toISOString(),
      },
    ];

    for (const event of events) {
      if (!["interrupt", "state_change", "done", "error"].includes(event.type)) continue;
      const presented = presentEvent(event);
      let text = `${presented.title}：${presented.detail}`;
      if (event.type === "interrupt") {
        if (event.payload.interrupt_kind === "CLARIFICATION") {
          text = event.payload.request.clarification_question;
        } else if (event.payload.interrupt_kind === "EVIDENCE_REQUEST") {
          text = event.payload.request.user_message;
        } else {
          text = "我已完成必要檢查，這筆建議正在等待 reviewer 確認。";
        }
      }
      items.push({ id: `event-${event.seq}`, role: "agent", text, ts: event.ts });
    }

    if (history) {
      for (const turn of new Map(history.turns.map(turn => [turn.seq, turn])).values()) items.push({
        id: `turn-${turn.seq}`, role: "user", text: turn.message, ts: turn.created_at,
        attachments: turn.attachments,
        artifactRef: turn.attached_artifact_refs.filter(ref => !ref.startsWith("artifact://upload/")).join(", ") || undefined,
      });
    }
    for (const local of history ? [] : localMessages) {
      items.push({
        artifactRef: local.artifactRef,
        id: `local-${local.id}`,
        role: "user",
        text: local.text,
        ts: local.ts,
      });
    }
    return items.sort((left, right) => Date.parse(left.ts) - Date.parse(right.ts));
  }, [detail.created_at, events, localMessages, history]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(undefined);
    const sentText = message.trim() || "已補交所需資料。";
    const sentArtifactRef = artifactRef.trim() || undefined;
    try {
      if (images.some(i => i.state !== "ready")) throw new Error("請先重試或移除尚未上傳的圖片。");
      const refs = [...images.map(i => i.attachment!.artifact_ref), ...(sentArtifactRef ? [sentArtifactRef] : [])];
      await sendCaseMessage(detail.case_ref, {
        message: sentText,
        attached_artifact_refs: refs,
      });
      setSubmittedVersion(projectionVersion);
      onMessageSent({
        id: Date.now(),
        artifactRef: sentArtifactRef,
        text: sentText,
        ts: new Date().toISOString(),
      });
      setMessage("");
      setArtifactRef("");
      setImages([]);
      try {
        const [freshHistory] = await Promise.all([getConversation(detail.case_ref), onUpdated()]);
        setHistory(freshHistory);
        setHistoryError(undefined);
      } catch {
        setHistoryError("訊息已送出，但畫面更新失敗。請重新整理，不需重送。");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "送出失敗，請稍後再試。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="flex min-h-[680px] flex-col overflow-hidden xl:min-h-0">
      <div className="flex min-h-[68px] items-center justify-between gap-4 border-b border-stone-200 px-5 py-3">
        <div>
          <h1 className="text-sm font-bold text-stone-950">使用者對話</h1>
          <p className="mt-1 text-[11px] text-stone-400">案件內容與補件都在同一個 conversation</p>
        </div>
        <Badge className="border-orange-100 bg-orange-50 text-orange-700">固定使用者</Badge>
      </div>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-gradient-to-b from-white to-stone-50/70 p-5">
        {!history && !historyError && <p role="status" className="text-sm text-stone-500">正在載入對話…</p>}
        {history && history.turns.length === 0 && <p role="status" className="text-sm text-stone-500">未保存初始申請內容</p>}
        {conversation.map((item) => (
          <ConversationBubble key={item.id} item={item} />
        ))}
        {isAgentWorking ? (
          <div className="flex items-center gap-2 pl-11 text-xs text-stone-400">
            <LoaderCircle className="size-3.5 animate-spin text-orange-500" /> Agent 正在處理下一步
          </div>
        ) : null}
      </div>
      <form className="border-t border-stone-200 bg-white p-4" onSubmit={submit}>
        <div className="rounded-2xl border border-stone-300 bg-white p-2 shadow-[0_12px_30px_-24px_rgba(41,37,36,0.5)] focus-within:border-orange-400 focus-within:ring-3 focus-within:ring-orange-100">
          <div className="flex items-center gap-2 border-b border-stone-100 px-2 pb-2 text-[10px] text-stone-400">
            案件 <strong className="font-mono text-stone-700">{detail.case_ref}</strong>
            {isEvidence ? <span className="ml-auto text-orange-600">需要補交證據</span> : null}
          </div>
          <ImageAttachments orderRef={detail.order_ref} caseRef={detail.case_ref} images={images} onChange={setImages} disabled={!needsInput || submitting} />
          {isEvidence ? (
            <details><summary className="text-xs text-stone-500">進階 Demo：使用既有證據編號</summary>
            <label className="mt-2 flex items-center gap-2 rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-500">
              <Paperclip className="size-3.5" />
              <span className="sr-only">證據檔案編號</span>
              <Input
                aria-label="證據檔案編號"
                className="h-7 border-0 bg-transparent px-0 shadow-none focus:ring-0"
                onChange={(event) => setArtifactRef(event.target.value)}
                placeholder="artifact://demo/EV-DEMO-ARRIVAL-PACKAGING-AND-DAMAGE"
                disabled={submitting}
                value={artifactRef}
              />
            </label>
            </details>
          ) : null}
          <div className="flex items-end gap-2 pt-2">
            <Textarea
              aria-label="補充案件說明"
              className="max-h-24 min-h-12 resize-none border-0 px-2 py-2 shadow-none focus:ring-0"
              disabled={!needsInput || submitting}
              onChange={(event) => setMessage(event.target.value)}
              placeholder={needsInput ? "輸入要補充的內容⋯" : statusLabel(detail.status)}
              required={!isEvidence && needsInput && images.length === 0}
              value={message}
            />
            <Button className="size-10 shrink-0 px-0" disabled={!needsInput || submitting || images.some(i => i.state !== "ready")} aria-label="送出">
              {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
            </Button>
          </div>
        </div>
        {error ? <p className="mt-2 text-xs text-red-600" role="alert">{error}</p> : null}
        {historyError ? <p className="mt-2 text-xs text-red-600" role="alert">對話還原失敗：{historyError}</p> : null}
      </form>
    </Card>
  );
}

function ConversationBubble({ item }: { item: ConversationItem }) {
  const isUser = item.role === "user";
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      <span
        className={cn(
          "grid size-8 shrink-0 place-items-center text-[10px] font-bold text-white",
          isUser ? "rounded-full bg-stone-900" : "rounded-xl bg-orange-600",
        )}
      >
        {isUser ? "DC" : <Bot className="size-4" />}
      </span>
      <div
        className={cn(
          "max-w-[82%] rounded-2xl border px-4 py-3 text-sm leading-6 shadow-sm",
          isUser
            ? "rounded-tr-sm border-stone-900 bg-stone-900 text-white"
            : "rounded-tl-sm border-stone-200 bg-white text-stone-700",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{item.text}</p>
        {item.attachments?.length ? <div className="mt-2 flex flex-wrap gap-2">{item.attachments.map(a => <AttachmentImage key={a.attachment_id} attachment={a} />)}</div> : null}
        {item.artifactRef ? (
          <div className="mt-3 flex items-center gap-3 rounded-xl bg-white/95 p-2.5 text-stone-700">
            <span className="grid size-9 place-items-center rounded-lg bg-orange-100 text-orange-600">
              <FileImage className="size-4" />
            </span>
            <span className="min-w-0">
              <strong className="block truncate text-[11px]">已附加證據</strong>
              <span className="block truncate font-mono text-[9px] text-stone-400">{item.artifactRef}</span>
            </span>
          </div>
        ) : null}
        <time className="mt-1 block text-[9px] text-stone-400">{formatClock(item.ts)}</time>
      </div>
    </div>
  );
}

function FulfillmentPanel({detail,onUpdated}: {detail:CaseDetail;onUpdated:() => Promise<CaseDetail>}) {
  const identity = useDemoIdentity();
  const [pending,setPending] = useState(false);
  const [error,setError] = useState("");
  const confirmation = detail.policy_confirmation_request;
  const fulfillment = detail.fulfillment;
  const path = fulfillment?.selected_path_id ?? detail.policy_evaluation?.selection.selected_path_id;
  async function perform(action: () => Promise<unknown>) {
    setPending(true); setError("");
    try { await action(); await onUpdated(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "無法更新狀態"); }
    finally { setPending(false); }
  }
  if (detail.policy_schema_version !== "v2") return null;
  const paths: Record<string,string> = {COOLING_OFF:"一般退貨",DAMAGED_ON_ARRIVAL:"到貨實體損壞",WRONG_ITEM:"寄錯商品",UNDELIVERED_ITEM:"獨立品項未交付"};
  return <Card className="space-y-2 p-4 text-sm" aria-label="退回與退款進度">
    <p>途徑：{path ? paths[path] : "判定中"} · {statusLabel(detail.status)}</p>
    {fulfillment && <p>{fulfillment.return_required ? "退回驗收後付款" : "免退授權"} · 付款：{fulfillment.payment_status === "SUCCEEDED" ? "已完成" : fulfillment.payment_status === "REJECTED" ? "未執行，交專責處理" : "尚未完成"}</p>}
    {confirmation && <div>
      <p>請確認以「{paths[confirmation.path_id]}」處理本次申請，{confirmation.return_required ? "需退回商品並通過驗收" : "不需退回商品"}。</p>
      {identity?.role === "buyer" && <div className="mt-2 flex gap-2">
        <Button disabled={pending} onClick={() => perform(() => confirmPolicy(detail.case_ref,confirmation.request_ref,confirmation.selection_version,true))}>同意此途徑</Button>
        <Button disabled={pending} variant="outline" onClick={() => perform(() => confirmPolicy(detail.case_ref,confirmation.request_ref,confirmation.selection_version,false))}>不同意</Button>
      </div>}
    </div>}
    {fulfillment?.state === "AWAITING_RETURN_CONFIRMATION" && identity?.role === "buyer" && <div className="flex gap-2">
      <Button disabled={pending} onClick={() => perform(() => confirmReturn(detail.case_ref,fulfillment.authorization_ref,fulfillment.return_requirement_hash,true))}>同意退回並等待驗收</Button>
      <Button disabled={pending} variant="outline" onClick={() => perform(() => confirmReturn(detail.case_ref,fulfillment.authorization_ref,fulfillment.return_requirement_hash,false))}>交專責協助</Button>
    </div>}
    {identity?.role === "operator" && fulfillment && <div className="flex gap-2">
      {fulfillment.state === "AWAITING_RETURN" && <Button disabled={pending} onClick={() => perform(() => simulateReturn(detail.case_ref,"ARRIVED"))}>模擬退回送達</Button>}
      {fulfillment.state === "AWAITING_RETURN_INSPECTION" && <>
        <Button disabled={pending} onClick={() => perform(() => simulateReturn(detail.case_ref,"PASS"))}>模擬驗收通過</Button>
        <Button disabled={pending} variant="outline" onClick={() => perform(() => simulateReturn(detail.case_ref,"DISPUTE"))}>模擬驗收爭議</Button>
      </>}
      {["AWAITING_RETURN","AWAITING_RETURN_INSPECTION"].includes(fulfillment.state) && <Button disabled={pending} variant="outline" onClick={() => perform(() => simulateReturn(detail.case_ref,"OVERDUE"))}>模擬逾期</Button>}
    </div>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
  </Card>;
}

function ReviewerPanel({ detail, onUpdated }: { detail: CaseDetail; onUpdated: () => Promise<CaseDetail> }) {
  const identity = useDemoIdentity();
  const [findingStatuses,setFindingStatuses] = useState<Record<string,"SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED">>({});
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [selectedItems, setSelectedItems] = useState<string[] | null>(null);
  const [requireReturn, setRequireReturn] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();

  async function submit(decision: "APPROVE" | "REJECT" | "EDIT") {
    if (!note.trim() || submitting) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const common = { review_note: note.trim(), reviewer_id: identity?.user_ref ?? DEMO_REVIEWER_REF, handoff_id: review?.handoff_id };
      if (decision === "EDIT") {
        if (!review?.dossier) throw new Error("缺少原申請範圍與完整審核資料");
        const items = selectedItems ?? review.refund_scope.line_item_ids ?? [];
        if (!items.length) throw new Error("請至少選擇一個退款品項；不退款請選拒絕");
        await submitCaseReview(detail.case_ref, {
          ...common, decision: "EDIT", correction_reason_code: "OTHER",
          corrected_decision: {
            ...(detail.policy_schema_version === "v2" ? {policy_findings:(review.review_result.reviewer_claim_findings ?? []).map(f => ({...f,status:findingStatuses[f.claim_id] ?? f.status}))} : {}),
            action: "FULL_REFUND", refund_scope: { line_item_ids: items as [string, ...string[]] },
            return_decision: {
              source: "HUMAN_REVIEW",
              requirement: effectiveReturn
                ? { required: true, reason_code: "RETURN_REQUIRED_FOR_INSPECTION" }
                : { required: false, reason_code: "EVIDENCE_SUFFICIENT_WITHOUT_RETURN" },
            },
          },
        });
      } else {
        await submitCaseReview(detail.case_ref, { ...common, decision });
      }
      setEditing(false);
      setSelectedItems(null);
      await onUpdated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "無法送出人工審核");
    } finally {
      setSubmitting(false);
    }
  }
  const review = detail.human_review;
  const dossier = review?.dossier;
  const monetaryReview = review?.routing_reason === "HIGH_VALUE_ITEM" || review?.routing_reason === "CURRENCY_THRESHOLD_UNCONFIGURED";
  const riskReview = review?.routing_reason === "HIGH_USER_RISK" || review?.routing_reason === "USER_RISK_UNAVAILABLE";
  const gatedReview = monetaryReview || riskReview;
  const returnPolicies = dossier?.policy_bundle.clauses?.filter(clause => dossier.policy_bundle.schema_version !== "v2" || clause.path_id === dossier.policy_bundle.selected_path_id).map((clause) => clause.return_policy) ?? [];
  const fixedReturn = returnPolicies.includes("REQUIRED") ? true : returnPolicies.includes("NOT_REQUIRED") ? false : undefined;
  const effectiveReturn = fixedReturn ?? requireReturn;
  const isReviewing = detail.status === "AWAITING_HUMAN_REVIEW" && Boolean(review);
  const lineItemCount = review?.refund_scope.line_item_ids?.length ?? 0;
  const returnLabel =
    review && "return_decision" in review
      ? review.return_decision.requirement.required
        ? "需要退回商品"
        : "免退回商品"
      : "不需退回商品";

  return (
    <Card className={cn("flex min-h-0 flex-col overflow-hidden", isReviewing && "border-orange-200")}>
      <div className={cn("flex min-h-[62px] items-center justify-between gap-4 border-b px-5 py-3", isReviewing ? "border-orange-100 bg-orange-50/60" : "border-stone-200")}>
        <div>
          <h2 className="text-sm font-bold text-stone-950">人工最終裁決</h2>
          <p className="mt-1 text-[10px] text-stone-400">{monetaryReview ? "金額規則命中 · 提案已核准，等待人工授權" : riskReview ? "使用者風險授權 · 提案已核准，等待人工授權" : "Agent 無法收斂 · 由人工依現有證據裁決"}</p>
        </div>
        <Badge className={isReviewing ? "border-orange-100 bg-orange-100 text-orange-800" : ""}>
          {identity?.user_ref ?? DEMO_REVIEWER_REF}
        </Badge>
      </div>
      {review ? (
        <div className="grid min-h-0 flex-1 gap-5 overflow-y-auto p-5 sm:grid-cols-[minmax(0,1fr)_210px]">
          <div className="min-w-0">
            <p className="text-[9px] font-black tracking-[0.12em] text-orange-600 uppercase">
              Agent 建議 · {review.action === "FULL_REFUND" ? "Full refund" : "Decline"}
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <strong className="text-2xl tracking-tight text-stone-950">{review.currency} {review.amount}</strong>
              <span className="text-[11px] text-stone-400">{lineItemCount} 件商品</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-stone-600">{review.rationale_summary}</p>
            {dossier?.user_risk_gate && <section aria-label="使用者風險授權" className="mt-3 rounded border p-3 text-xs">
              <strong>使用者風險授權：{dossier.user_risk_gate.status}</strong>
              <p>等級：{dossier.user_risk_gate.risk_level} · 分數：{dossier.user_risk_gate.score ?? "未知"}</p>
              <p>標記：{dossier.user_risk_gate.tags?.join("、") || "無"}</p>
              <p>快照：{dossier.user_risk_snapshot?.snapshot_ref ?? "無法取得"}</p>
              <p>截至：{dossier.user_risk_snapshot?.as_of ?? "未知"}</p>
              <p>帳號天數：{dossier.user_risk_snapshot?.account_age_days ?? "未知"}；訂單：{dossier.user_risk_snapshot?.orders_90d ?? "未知"}；同原因申請：{dossier.user_risk_snapshot?.same_reason_claims_90d ?? "未知"}；退款訂單：{dossier.user_risk_snapshot?.refunded_orders_90d ?? "未知"}</p>
              <p>人工核准後仍須符合退回與驗收條件。</p>
            </section>}
            {editing && detail.policy_schema_version === "v2" && <section aria-label="人工政策 findings" className="mt-3 space-y-2 text-xs">
              {review.review_result.reviewer_claim_findings.map(f => <label key={f.claim_id} className="block">
                {f.claim_id} · {f.subject}
                <select className="ml-2 border p-1" value={findingStatuses[f.claim_id] ?? f.status} onChange={e => setFindingStatuses({...findingStatuses,[f.claim_id]:e.target.value as "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED"})}>
                  <option value="SUPPORTED">有證據支持</option><option value="UNSUPPORTED">資料不足</option><option value="CONTRADICTED">有反證</option>
                </select>
                <span className="block">{(f.supporting_evidence_refs ?? []).join("、")} · {f.explanation}</span>
              </label>)}
            </section>}
            <ul className="mt-3 space-y-2 text-xs text-red-800" aria-label="Reviewer 未解決異議">
              {review.review_result.revision_reasons?.map((reason, index) => (
                <li key={index}>
                  <strong>{reason.subject} · {reason.code}</strong>
                  <p>{reason.message}</p>
                  <p>所需修正：{reason.required_change}</p>
                  <p>政策：{(reason.policy_refs ?? []).join("、") || "未引用"}；證據：{(reason.evidence_refs ?? []).join("、") || "未引用"}</p>
                </li>
              ))}
            </ul>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge>{gatedReview ? "Reviewer 已核准 · 等待人工授權" : "修正次數已用盡 · Reviewer 尚未核准"}</Badge>
              <Badge>{review.evidence_refs?.length ?? 0} 份證據</Badge>
              <Badge>{returnLabel}</Badge>
            </div>
            {monetaryReview && dossier?.review_gate ? <section aria-label="金額 gate" className="mt-3 rounded bg-orange-50 p-3 text-xs">
              <p>{dossier.review_gate.reason === "HIGH_VALUE_ITEM" ? "退款金額超過自動授權門檻" : "此幣別尚未設定自動授權門檻"}</p>
              <p>{dossier.review_gate.currency} {dossier.review_gate.amount} · 門檻 {dossier.review_gate.threshold ?? "未設定"}</p>
              <p>規則版本：{dossier.review_gate.config_version}</p>
            </section> : null}
            <section aria-label="完整審核歷程" className="mt-5 space-y-3 text-xs">
              <h3 className="font-bold">審核歷程</h3>
              {!dossier ? <p>歷史資料不完整，無法開放重新裁決。</p> : dossier.proposal_history.map((proposal, index) => (
                <details key={proposal.handoff_id} open={index === dossier.proposal_history.length - 1} className="rounded border p-3">
                  <summary>第 {index + 1} 輪 · {proposal.proposed_decision.action === "FULL_REFUND" ? "退款" : "不退款"} · {dossier.review_history[index]?.verdict}</summary>
                  <p className="mt-2">{proposal.rationale_summary}</p>
                  <p>品項：{proposal.proposed_decision.refund_scope.line_item_ids?.join("、") || "無"}；{proposal.proposed_decision.currency} {proposal.proposed_decision.amount}</p>
                  <p>審核時間：{dossier.review_history[index]?.reviewed_at}</p>
                  {dossier.review_history[index]?.revision_reasons?.map((reason, reasonIndex) => <div key={reasonIndex} className="mt-2 text-red-800">
                    <p>{reason.subject} · {reason.message}</p><p>所需修正：{reason.required_change}</p>
                    <p>政策：{reason.policy_refs?.join("、")}；證據：{reason.evidence_refs?.join("、")}</p>
                  </div>)}
                  {dossier.proposal_history[index + 1] ? <p className="mt-2">下一輪提案：{dossier.proposal_history[index + 1].rationale_summary}</p> : <p className="mt-2">{gatedReview ? "提案通過 Reviewer，依授權規則交由人工核准。" : "最後未解決異議，交由人工裁決。"}</p>}
                </details>
              ))}
            </section>
            <section aria-label="裁決依據" className="mt-5 space-y-2 text-xs">
              <h3 className="font-bold">訂單、Policy 與證據</h3>
              {dossier ? <div className="rounded bg-stone-50 p-2">
                <p>原申請品項：{dossier.claimed_line_item_ids.join("、")}</p>
                <p>訂單：{dossier.order_snapshot.order_ref} · 送達：{dossier.order_snapshot.delivered_at}</p>
                <p>交接時可退上限：{dossier.order_snapshot.currency} {dossier.order_snapshot.refundable_amount_max}（送出及執行時重新驗證）</p>
              </div> : null}
              {dossier?.policy_bundle.clauses?.map((clause) => <p key={clause.clause_id}>{clause.clause_id} · {clause.text}</p>)}
              {review.evidence_refs?.map((evidence) => <p key={evidence.evidence_id}>{evidence.evidence_id} · {evidence.subject} · {evidence.caption}</p>)}
            </section>
            {detail.human_review_result ? <section aria-label="人工裁決紀錄" className="mt-5 rounded bg-emerald-50 p-3 text-xs">
              <h3 className="font-bold">人工裁決已提交</h3>
              <p>{detail.human_review_result.decision === "EDIT" ? detail.human_review_result.corrected_decision.action === "FULL_REFUND" ? "退款" : "不退款" : detail.human_review_result.decision === "REJECT" ? "不退款" : "採用原建議"}</p>
              <p>{detail.human_review_result.review_note}</p>
              <p>{detail.human_review_result.reviewer_id} · {detail.human_review_result.reviewed_at}</p>
            </section> : null}
          </div>
          {isReviewing ? <div className="flex flex-col gap-2 self-start rounded border border-orange-100 bg-white p-3 sm:sticky sm:top-0">
            <h3 className="text-sm font-semibold">最後決定</h3>
            <p className="text-xs text-stone-500">只依現有資料裁決。無法判定時保持待人工，這版不提供再次補件。</p>
            <Textarea aria-label="人工審核理由" placeholder="請填寫審核理由" value={note} onChange={(event) => setNote(event.target.value)} disabled={submitting} />
            <Button disabled={submitting || !note.trim() || !dossier} onClick={() => void submit("APPROVE")} size="sm">採用原建議</Button>
            <Button disabled={submitting || !dossier} onClick={() => setEditing(!editing)} size="sm" variant="outline">決定退款</Button>
            {editing && dossier ? (
              <fieldset disabled={submitting} className="space-y-2 text-xs">
                <legend>修改退款範圍與退貨要求</legend>
                {dossier.claimed_line_item_ids.map((id) => (
                  <label key={id} className="flex items-center gap-2">
                    <input type="checkbox" checked={(selectedItems ?? review.refund_scope.line_item_ids ?? []).includes(id)} onChange={(event) => {
                      const current = selectedItems ?? review.refund_scope.line_item_ids ?? [];
                      setSelectedItems(event.target.checked ? [...current, id] : current.filter((item) => item !== id));
                    }} />{dossier.order_snapshot.line_items.find((item) => item.line_item_id === id)?.title ?? id} ({id})
                  </label>
                ))}
                <label className="flex items-center gap-2">
                  <input type="checkbox" disabled={fixedReturn !== undefined} checked={effectiveReturn} onChange={(event) => setRequireReturn(event.target.checked)} />需要退回檢查
                </label>
                <p>{effectiveReturn ? "退回以進行檢查" : "免退回商品"}；金額由系統按品項計算，請在整體理由說明依據。</p>
                <Button disabled={!note.trim() || !(selectedItems ?? review.refund_scope.line_item_ids ?? []).length} onClick={() => void submit("EDIT")} size="sm">確認退款裁決</Button>
              </fieldset>
            ) : null}
            <Button className="border-red-100 bg-red-50 text-red-700" disabled={submitting || !note.trim() || !dossier} onClick={() => void submit("REJECT")} size="sm" variant="outline">決定不退款</Button>
            {error ? <p role="alert" className="text-xs text-red-600">{error}</p> : null}
          </div> : null}
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 place-items-center p-6 text-center">
          <div>
            {terminalStatuses.has(detail.status) ? (
              <Check className="mx-auto size-6 text-emerald-500" />
            ) : (
              <UserRound className="mx-auto size-6 text-stone-300" />
            )}
            <p className="mt-3 text-sm font-semibold text-stone-600">
              {terminalStatuses.has(detail.status) ? "案件不再等待審核" : "等待 Agent 送出建議"}
            </p>
            <p className="mt-1 text-[11px] text-stone-400">
              {terminalStatuses.has(detail.status) ? statusLabel(detail.status) : "收到 HUMAN_REVIEW event 後會顯示完整內容"}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
