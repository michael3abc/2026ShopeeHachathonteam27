"use client";

import { useEffect, useRef, useState } from "react";
import type { AttachmentView } from "@/contracts/attachment-view";
import type { UploadOptions } from "@/contracts/upload-options";
import { getUploadOptions, imageContentUrl, uploadImage } from "@/lib/api";

export type ImageDraft = {
  id: string;
  file: File;
  preview: string;
  subject: string;
  state: "uploading" | "ready" | "failed";
  attachment?: AttachmentView;
  error?: string;
};

export function AttachmentImage({ attachment }: { attachment: AttachmentView }) {
  return <ImagePreview url={imageContentUrl(attachment.attachment_id)} alt="已提交的證據圖片" />;
}

function ImagePreview({url, alt}: {url: string; alt: string}) {
  const dialog = useRef<HTMLDialogElement>(null);
  return <>
    <button type="button" aria-label="放大附件" onClick={() => dialog.current?.showModal()}>
      {/* Native img supports API-owned protected media without an image proxy. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="h-24 w-24 rounded-lg border object-cover" src={url} alt={alt} />
    </button>
    <dialog ref={dialog} aria-label="圖片預覽" className="fixed inset-0 m-auto max-h-[90vh] max-w-[95vw] rounded-xl bg-stone-900 p-8 backdrop:bg-black/80" onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}>
      <button type="button" autoFocus className="absolute right-2 top-2 rounded bg-white p-2" onClick={() => dialog.current?.close()}>關閉圖片</button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="max-h-[75vh] max-w-full object-contain" src={url} alt="證據圖片原圖" />
    </dialog>
  </>;
}

export function ImageAttachments({ orderRef, caseRef, disabled, images, onChange }: {
  orderRef: string; caseRef?: string; disabled?: boolean;
  images: ImageDraft[]; onChange: (images: ImageDraft[]) => void;
}) {
  const [options, setOptions] = useState<UploadOptions>();
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string>();
  const [dragging, setDragging] = useState(false);
  const current = useRef(images);
  current.current = images;
  const urls = useRef(new Set<string>());
  const generation = useRef(0);
  const queue = useRef(Promise.resolve());
  const addFiles = useRef<(files: File[]) => void>(() => {});
  const input = useRef<HTMLInputElement>(null);
  const changed = useRef(onChange);
  changed.current = onChange;

  useEffect(() => {
    const epoch = generation;
    const version = ++generation.current;
    setOptions(undefined);
    setSubject("");
    setError(undefined);
    changed.current([]);
    for (const url of urls.current) URL.revokeObjectURL(url);
    urls.current.clear();
    if (orderRef.trim()) {
      const timer = setTimeout(() => {
        getUploadOptions(orderRef.trim()).then(value => {
          if (generation.current !== version) return;
          setOptions(value);
          const itemIds = Object.keys(value.subjects).filter(id => id !== "ORDER");
          setSubject(itemIds.length === 1 ? itemIds[0] : "");
        }).catch(cause => { if (generation.current === version) setError(String(cause.message)); });
      }, 350);
      return () => { clearTimeout(timer); epoch.current++; };
    }
  }, [orderRef, caseRef]);

  useEffect(() => { const allocated = urls.current; return () => { for (const url of allocated) URL.revokeObjectURL(url); }; }, []);

  useEffect(() => {
    const live = new Set(images.map(image => image.preview));
    for (const url of urls.current) if (!live.has(url)) {
      URL.revokeObjectURL(url);
      urls.current.delete(url);
    }
  }, [images]);

  useEffect(() => {
    const form = input.current?.closest("form");
    if (!form) return;
    function dropped(event: DragEvent) {
      event.preventDefault(); setDragging(false);
      addFiles.current(Array.from(event.dataTransfer?.files ?? []));
    }
    function pasted(event: ClipboardEvent) {
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) { event.preventDefault(); addFiles.current(files); }
    }
    function over(event: DragEvent) { event.preventDefault(); setDragging(true); }
    function leave() { setDragging(false); }
    form.addEventListener("drop", dropped);
    form.addEventListener("paste", pasted);
    form.addEventListener("dragover", over);
    form.addEventListener("dragleave", leave);
    return () => {
      form.removeEventListener("drop", dropped); form.removeEventListener("paste", pasted);
      form.removeEventListener("dragover", over); form.removeEventListener("dragleave", leave);
    };
  }, []);

  function publish(next: ImageDraft[]) { current.current = next; onChange(next); }
  async function upload(draft: ImageDraft, version: number) {
    if (version !== generation.current || !current.current.some(i => i.id === draft.id)) return;
    publish(current.current.map(i => i.id === draft.id ? { ...i, state: "uploading", error: undefined } : i));
    try {
      const attachment = await uploadImage(draft.file, orderRef.trim(), draft.subject, caseRef);
      if (version === generation.current) publish(current.current.map(i => i.id === draft.id ? { ...i, state: "ready", attachment } : i));
    } catch (cause) {
      if (version === generation.current) publish(current.current.map(i => i.id === draft.id ? { ...i, state: "failed", error: cause instanceof Error ? cause.message : "上傳失敗" } : i));
    }
  }
  function add(files: File[]) {
    if (disabled || !options || !files.length) return;
    if (!subject) { setError("請先選擇圖片對應的品項或外包裝。"); return; }
    if (files.length + current.current.length > options.max_images) { setError(`每則最多 ${options.max_images} 張圖片。`); return; }
    if (files.some(f => !options.media_types.includes(f.type) || f.size > options.max_bytes)) {
      setError(`僅接受 JPEG、PNG、WebP，每張最多 ${Math.floor(options.max_bytes / 1048576)} MiB。`); return;
    }
    setError(undefined);
    const drafts: ImageDraft[] = files.map(file => {
      const preview = URL.createObjectURL(file); urls.current.add(preview);
      return { id: crypto.randomUUID(), file, preview, subject, state: "uploading" };
    });
    publish([...current.current, ...drafts]);
    // Bound the upload queue: one request at a time, preserve selected order.
    const version = generation.current;
    for (const draft of drafts) queue.current = queue.current.then(() => upload(draft, version));
  }
  addFiles.current = add;
  return <div className={`my-2 rounded-xl border border-dashed p-3 text-xs ${dragging ? "border-orange-500 bg-orange-50" : "border-stone-300"}`}
    tabIndex={0} aria-label="拖曳或貼上證據圖片">
    <div className="flex flex-wrap items-center gap-2">
      <select aria-label="圖片對應品項" disabled={disabled || !options} value={subject} onChange={e => setSubject(e.target.value)} className="max-w-full rounded border p-1">
        <option value="">選擇品項</option>
        {options && Object.entries(options.subjects).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select>
      <button type="button" disabled={disabled || !options} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => input.current?.click()}>選擇圖片</button>
      <span>拖曳圖片到此處，或點此貼上圖片</span>
      <input ref={input} type="file" aria-label="證據圖片" className="sr-only" multiple accept="image/jpeg,image/png,image/webp" disabled={disabled || !options}
        onChange={e => { add(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
    </div>
    <div className="mt-2 flex flex-wrap gap-3">
      {images.map(draft => <div key={draft.id} className="w-28">
        <ImagePreview url={draft.preview} alt={draft.file.name} />
        <span className="block truncate">{draft.file.name}</span>
        <span className="block truncate text-stone-500" title={options?.subjects[draft.subject]}>{options?.subjects[draft.subject] ?? draft.subject}</span>
        <span className={draft.state === "failed" ? "block text-red-600" : "block text-stone-500"}>{draft.state === "uploading" ? "上傳中…" : draft.state === "ready" ? "已上傳" : draft.error}</span>
        <div className="mt-1 flex gap-2">
        {draft.state === "failed" && <button type="button" className="rounded border px-2 py-1" disabled={disabled} onClick={() => {
          const version = generation.current;
          publish(current.current.map(i => i.id === draft.id ? { ...i, state: "uploading" } : i));
          queue.current = queue.current.then(() => upload(draft, version));
        }}>重試</button>}
        <button type="button" className="rounded border px-2 py-1" disabled={disabled} aria-label={`移除 ${draft.file.name}`} onClick={() => { URL.revokeObjectURL(draft.preview); urls.current.delete(draft.preview); publish(current.current.filter(i => i.id !== draft.id)); }}>移除</button>
        </div>
      </div>)}
    </div>
    {error && <p role="alert" className="mt-2 text-red-600">{error}</p>}
  </div>;
}
