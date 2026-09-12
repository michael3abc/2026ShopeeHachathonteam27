import { Bot } from "lucide-react";

import { CreateCaseForm } from "@/components/create-case-form";

export default function Home() {
  return (
    <main className="flex min-h-screen bg-stone-50">
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[73px] items-center justify-between border-b border-stone-200 bg-white px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-xl bg-orange-600 font-black text-white">
              R
            </div>
            <div>
              <p className="font-bold text-stone-900">ReturnFlow 退貨助理</p>
              <p className="flex items-center gap-1.5 text-xs text-stone-400">
                <span className="size-1.5 rounded-full bg-emerald-500" /> 可以開始對話
              </p>
            </div>
          </div>
          <span className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-500">
            Demo 模式
          </span>
        </header>

        <div className="flex flex-1 flex-col">
          <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-5 py-8 sm:px-8 sm:py-12">
            <div className="flex items-start gap-3">
              <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-orange-600 text-white">
                <Bot className="size-4" />
              </div>
              <div className="max-w-xl rounded-2xl rounded-tl-sm border border-stone-200 bg-white px-4 py-3 shadow-sm">
                <p className="text-sm leading-6 text-stone-700">
                  您好，我是退貨助理。請輸入訂單編號，並告訴我商品遇到的問題。
                </p>
              </div>
            </div>
          </div>
          <CreateCaseForm />
        </div>
      </section>
    </main>
  );
}
