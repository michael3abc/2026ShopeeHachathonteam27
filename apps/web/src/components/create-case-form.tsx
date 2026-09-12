"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createCase } from "@/lib/api";
import { ImageAttachments, type ImageDraft } from "@/components/image-attachments";

export function CreateCaseForm() {
  const router = useRouter();
  const [orderRef, setOrderRef] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [images, setImages] = useState<ImageDraft[]>([]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(undefined);
    try {
      if (images.some(i => i.state !== "ready")) throw new Error("請先重試或移除尚未上傳的圖片。");
      const result = await createCase(orderRef.trim(), message.trim(), images.map(i => i.attachment!.artifact_ref));
      router.push(`/cases/${encodeURIComponent(result.case_ref)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "目前無法建立案件，請稍後再試。");
      setSubmitting(false);
    }
  }

  return (
    <div className="border-t border-stone-200 bg-white px-5 py-5 sm:px-8">
      <form className="mx-auto max-w-3xl" onSubmit={submit}>
        <div className="rounded-2xl border border-stone-300 bg-white p-2 shadow-[0_16px_45px_-32px_rgba(41,37,36,0.45)] focus-within:border-orange-400 focus-within:ring-3 focus-within:ring-orange-100">
          <div className="flex items-center gap-3 border-b border-stone-100 px-2 pb-2">
            <label className="shrink-0 text-xs font-semibold text-stone-500" htmlFor="order-ref">
              訂單編號
            </label>
            <Input
              className="h-8 border-0 px-0 font-mono text-xs shadow-none focus:ring-0"
              id="order-ref"
              value={orderRef}
              disabled={submitting}
              onChange={(event) => setOrderRef(event.target.value)}
              placeholder="訂單 reference（整合 demo 使用 ORDER-DEMO-*）"
              required
              autoComplete="off"
            />
          </div>
          <ImageAttachments orderRef={orderRef} images={images} onChange={setImages} disabled={submitting} />
          <div className="flex items-end gap-2 pt-2">
            <Textarea
              className="min-h-16 flex-1 resize-none border-0 py-2 shadow-none focus:ring-0"
              id="message"
              aria-label="告訴退貨助理商品遇到的問題"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="輸入商品問題⋯"
              required
              minLength={3}
            />
            <Button
              className="mb-1 size-10 shrink-0 rounded-xl p-0"
              type="submit"
              disabled={submitting || images.some(i => i.state !== "ready")}
              aria-label="送出"
            >
              {submitting ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
            </Button>
          </div>
        </div>
        {error ? <p role="alert" className="mt-2 text-sm text-red-600">{error}</p> : null}
        <p className="mt-2 text-center text-xs text-stone-400">
          Demo 使用固定測試帳號，不會執行真實退款
        </p>
      </form>
    </div>
  );
}
