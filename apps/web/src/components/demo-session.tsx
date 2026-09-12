"use client";
import { createContext, useContext, useEffect, useState, type FormEvent } from "react";
import { authConfig, getIdentity, login, logout, type DemoIdentity } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const SessionContext = createContext<DemoIdentity | null>(null);
export const useDemoIdentity = () => useContext(SessionContext);

export function DemoSession({children}: {children: React.ReactNode}) {
  const [enabled,setEnabled] = useState<boolean>();
  const [identity,setIdentity] = useState<DemoIdentity | null>(null);
  const [user,setUser] = useState("");
  const [credential,setCredential] = useState("");
  const [error,setError] = useState("");
  const [pending,setPending] = useState(false);
  useEffect(() => {
    authConfig().then(async config => {
      if (config.enabled) {
        try { setIdentity(await getIdentity()); } catch { /* Sign-in form handles expired sessions. */ }
      }
      setEnabled(config.enabled);
    }).catch(() => setError("登入服務無法連線，請重新整理。"));
  },[]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setError("");
    try { setIdentity(await login(user,credential)); setCredential(""); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "登入失敗"); }
    finally { setPending(false); }
  }
  if (enabled === undefined) return <main className="p-8">{error || "載入登入設定中…"}</main>;
  if (!enabled) return children;
  if (!identity) return <main className="grid min-h-screen place-items-center bg-stone-50">
    <form onSubmit={submit} className="w-80 space-y-4 rounded-xl border bg-white p-6">
      <h1 className="text-lg font-bold">Demo 登入</h1>
      <label className="block">帳號<Input value={user} onChange={e => setUser(e.target.value)} autoComplete="username" required /></label>
      <label className="block">個人憑證<Input value={credential} onChange={e => setCredential(e.target.value)} type="password" autoComplete="current-password" required /></label>
      <Button disabled={pending} type="submit">登入</Button>
      {error && <p role="alert">{error}</p>}
    </form>
  </main>;
  return <SessionContext.Provider value={identity}>
    <div className="flex items-center justify-between border-b bg-white px-4 py-2 text-xs">
      <span>{identity.user_ref} · {{buyer:"買家",reviewer:"審核員",operator:"物流操作員"}[identity.role]}</span>
      <Button variant="outline" onClick={async () => { await logout(); location.reload(); }}>登出</Button>
    </div>
    {children}
  </SessionContext.Provider>;
}
