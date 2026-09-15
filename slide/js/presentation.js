(() => {
  'use strict';
  const slides = [...document.querySelectorAll('.slide')];
  const $ = (selector) => document.querySelector(selector);
  let current = 0, reveal = 0;
  const notes = [
    ['00:00–00:30 · 30 秒', '退貨的困難不只是理解一句話。使用者提供的資訊不完整，證據需要判讀，政策限制可選的處置，而最後還有金額授權與人工例外。這需要能跨多步推進的 Agent，也需要可靠的邊界。Return Atlas 讓 reasoning 自主進行，但把權限留在 deterministic workflow。', '指向右圖的 authority boundary，接著翻到系統全貌。'],
    ['00:30–01:15 · 45 秒', '先看上半部：Web 顯示案件，API 擁有 canonical case state 與業務權限。按下一步：API 交易寫入 Outbox，Redis 將 typed command 送進 Agent Service；Service 處理 worker、journal 與 checkpoint，再呼叫純 LangGraph Runtime。再按下一步：結果以 typed event 回到 Redis，由 API 投影後透過 SSE 更新前端。三個 owner 的分工，讓 LangGraph 專注在 decision workflow。', '本頁共三個展開階段；→ / Space 展開，全部展開後才換頁。API 與 Agent 不共用資料庫。'],
    ['01:15–02:05 · 50 秒', 'LLM 可以正規化申請、判讀缺口、提出處置與獨立審核。每個輸出都有 schema；Policy evaluator、routing 與 monetary / User Risk gates 由程式控制。證據不足就 interrupt，補件後 resume；Reviewer 要求修訂則進有界迴圈。金額與幣別由可信資料 deterministic 組裝，handoff ID 與 counters 由 Graph 掌握。LLM proposes，系統決定下一步是否被允許。', '圖為分組流程，依序讀 01–09，非完整 raw graph。Gates 是 reviewer 節點中的 deterministic code，不是額外命名的 Graph node。通過 gate 可直接 handoff；需要人工時才 interrupt。'],
    ['02:05–02:40 · 35 秒', 'Adaptive 不是讓 Agent 改 Policy。結案的 whole-case trace 在背景蒸餾，可以 SKIP，也可以產生 candidate。只有經外部治理核准、符合 scope 的 APPROVED Memory，才會被後續案件檢索。它改善取證策略與提案脈絡，不能放寬 eligibility 或略過 verification。v2 FULL_REFUND 的 correction 與 APPLIED 必須完成 durable join，才能觸發對應 learning job。', '不要宣稱每案都會建立 Memory，也不要宣稱已量測學習改善。Reviewer 不讀 Memory；來源版本下 v2 FULL_REFUND 有 correction / APPLIED join 條件。'],
    ['02:40–03:15 · 35 秒', 'Agent 不直接跑在 API request 裡。API 先把意圖與 Outbox 一起提交，worker 對 command 建立 journal，LangGraph 使用 durable checkpoint。結果回投也先完成 transaction 再 ACK。這讓重送、重啟與重複執行可以被處理。UI、canonical case 與 Graph working state 分屬不同 owner，不把瀏覽器畫面當成業務事實。', '可靠性指已實作的工程機制，不宣稱正式金流 production-ready。訊息為 at-least-once，依賴穩定 ID 與各操作冪等。'],
    ['03:15–04:40 · 85 秒', '切換至另外準備的真實 Demo。聚焦損壞商品：缺件 → interrupt → 補件 → 同一 workflow resume → Verification / Reviewer → UI resolution。讓評審對照實際 UI state、node 與 backend event。', '此頁不執行、不模擬 Demo。Live Demo 由團隊另行處理。既有 v2 案例包含等待，不能承諾新案在 85 秒內結束；可另備真實已暫停案件，但需明說起始狀態。演示後返回並按 →。'],
    ['04:40–05:05 · 25 秒', '剛才看到 resolution，但 resolution 不等於 execution。Agent 交出 ResolutionHandoff，API 接續授權；需要退回時先退回驗收，再重新驗證 snapshot、reservation，最後才執行退款並寫入 ledger。這是 domain 的核心：reasoning 不能直接取得金錢 mutation 的權限。', 'APPLIED 才是 Demo refund application 已套用。Graph END、Resolution、退款完成、Memory 完成是不同生命週期。Demo adapter 不是真實 Shopee 金流。'],
    ['05:05–05:25 · 20 秒', '我們希望評審記住三件事：Controlled Autonomy，讓 reasoning 有界；Governed Adaptation，讓經驗改善未來但不增加權限；Production Reliability，讓流程 typed、durable、recoverable、auditable。這些決策結合起來，讓 AI 能可靠自主處理真實 Domain Workflow。', '到 05:25 結束，保留 35 秒操作 buffer。Codex 開發頁依使用者要求略過。']
  ];
  const repo = 'https://github.com/michael3abc/2026ShopeeHachathonteam27/blob/8c0c49068d3b46f79232198ef9167b228cf16403/';
  const sources = {
    architecture: ['API owns canonical state；Agent Service owns execution infrastructure；Runtime owns Nodes / State / Routing。', ['README.md', 'apps/contracts/README.md', 'apps/agent_service/README.md', 'packages/agent_runtime/README.md']],
    autonomy: ['節點名稱與 reviewer 後的 gates 依目前 Graph。圖以概念群組呈現，沒有將 Gate 畫成額外註冊的 node；省略澄清、Policy path confirmation 與 terminal 細節。', ['packages/agent_runtime/src/return_agent_runtime/graph.py', 'packages/agent_runtime/src/return_agent_runtime/policy.py', 'docs/spec/01-agent-graph.md', 'docs/spec/09-policy-v2-integration.md']],
    memory: ['v2 FULL_REFUND 的 enqueue 條件包含 correction 與 durable APPLIED join；其他 outcome 依版本及 trace admission 決定。Memory 候選不等於核准，亦不證明已改善下一案。', ['docs/spec/04-operational-memory.md', 'apps/agent_service/src/return_agent_service/memory_completion.py', 'apps/agent_service/src/return_agent_service/memory_enqueue_worker.py', 'apps/api/src/return_agent/capabilities/operational_memory.py']],
    reliability: ['架構圖陳述已實作機制，不將歷史 test 統計當作本次重新執行結果。Redis 是 at-least-once；commit 後 ACK 與各操作 idempotency 共同處理重送。', ['apps/agent_service/src/return_agent_service/worker.py', 'apps/agent_service/src/return_agent_service/journal.py', 'docs/spec/08-external-interfaces.md', 'docs/progress.md']],
    execution: ['退款由 API capabilities 負責，含 authorization、revalidation、reservation 與 ledger；當前 refund application 是 deterministic Demo adapter。', ['apps/api/src/return_agent/capabilities/refund.py', 'docs/spec/09-policy-v2-integration.md', 'README.md']],
    overview: ['Source baseline：main@8c0c490（2026-09-12 已核對遠端 ref）。本簡報是 source-backed technical narrative；不包含新的 live E2E 驗收、學習效益 benchmark 或 production 金流證明。Codex 頁略過；Live Demo 獨立準備。', ['README.md', 'docs/spec/README.md', 'docs/progress.md', 'presentation/README.md']]
  };
  function displayNotes() {
    const [time, script, cue] = notes[current];
    const container = $('#notes-content'); container.replaceChildren();
    const title = document.createElement('h3'); title.textContent = slides[current].dataset.title;
    const timing = document.createElement('p'); timing.className = 'note-time'; timing.textContent = time;
    const text = document.createElement('p'); text.textContent = script;
    const direction = document.createElement('p'); direction.className = 'cue'; direction.textContent = cue;
    container.append(title, timing, text, direction);
  }
  function render() {
    slides.forEach((slide, index) => {
      slide.hidden = index !== current;
      slide.classList.toggle('active', index === current);
      slide.querySelectorAll('.reveal').forEach(el => {
        const concealed = Number(el.dataset.step) > reveal;
        el.classList.toggle('unrevealed', concealed);
        el.setAttribute('aria-hidden', String(concealed));
      });
    });
    $('#slide-number').textContent = String(current + 1).padStart(2, '0');
    $('#slide-name').textContent = slides[current].dataset.title;
    $('#progress-fill').style.width = `${(current + 1) / slides.length * 100}%`;
    $('#prev').disabled = current === 0 && reveal === 0;
    $('#next').disabled = current === slides.length - 1;
    $('#reveal-count').textContent = `${reveal + 1} / 3`;
    document.querySelectorAll('.overview-card').forEach((el, index) => el.setAttribute('aria-current', String(index === current)));
    $('#announcement').textContent = `第 ${current + 1} 頁，共 ${slides.length} 頁。${slides[current].dataset.title}`;
    document.title = `${current + 1}. ${slides[current].dataset.title} — Return Atlas`;
    displayNotes();
  }
  function go(index, step = 0) {
    current = Math.max(0, Math.min(slides.length - 1, index)); reveal = step;
    if (location.hash !== `#${current + 1}`) location.hash = String(current + 1);
    render(); window.scrollTo(0, 0);
  }
  function next() {
    const max = Number(slides[current].dataset.reveals || 0);
    if (reveal < max) { reveal++; render(); } else if (current < slides.length - 1) go(current + 1);
  }
  function previous() {
    if (reveal > 0) { reveal--; render(); } else if (current > 0) go(current - 1, Number(slides[current - 1].dataset.reveals || 0));
  }
  function fromHash() {
    const parsed = Number(location.hash.slice(1));
    const index = Number.isInteger(parsed) && parsed >= 1 && parsed <= slides.length ? parsed - 1 : 0;
    if (index !== current) { current = index; reveal = 0; }
    render();
  }
  function openDialog(id) { const dialog = $(id); if (!dialog.open) dialog.showModal(); }
  $('#next').addEventListener('click', next); $('#prev').addEventListener('click', previous);
  $('#overview-button').addEventListener('click', () => openDialog('#overview-dialog'));
  $('#notes-button').addEventListener('click', () => openDialog('#notes-dialog'));
  slides.forEach((slide, index) => {
    const button = document.createElement('button'); button.className = 'overview-card';
    const number = document.createElement('span'); number.textContent = String(index + 1).padStart(2, '0');
    const title = document.createElement('b'); title.textContent = slide.dataset.title;
    const time = document.createElement('small'); time.textContent = `${slide.dataset.time} SEC${index === 5 ? ' · DEMO BREAK' : ''}`;
    button.append(number, title, time);
    button.addEventListener('click', () => { $('#overview-dialog').close(); go(index); $('#deck').focus({preventScroll:true}); });
    $('#overview-grid').append(button);
  });
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  }));
  document.querySelectorAll('[data-source]').forEach(button => button.addEventListener('click', () => {
    const [description, paths] = sources[button.dataset.source];
    const content = $('#source-content'); content.replaceChildren();
    const text = document.createElement('p'); text.textContent = description; content.append(text);
    paths.forEach(path => { const link = document.createElement('a'); link.href = repo + path; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = `${path} ↗`; content.append(link); });
    const note = document.createElement('p'); note.className = 'muted'; note.textContent = '來源連結需要網路；簡報內容與操作可完全離線使用。'; content.append(note);
    openDialog('#source-dialog');
  }));
  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
      else $('#announcement').textContent = '此瀏覽器不支援 Fullscreen API，請使用瀏覽器的全螢幕功能。';
    } catch { $('#announcement').textContent = '全螢幕未成功，請使用瀏覽器的全螢幕功能。'; }
  }
  $('#fullscreen-button').addEventListener('click', fullscreen);
  document.addEventListener('fullscreenchange', () => $('#fullscreen-button').setAttribute('aria-label', document.fullscreenElement ? '離開全螢幕' : '切換全螢幕'));
  let elapsed = 0, startedAt = null;
  const now = () => performance.now();
  function tick() {
    const seconds = Math.floor((elapsed + (startedAt === null ? 0 : now() - startedAt)) / 1000);
    $('#timer').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    $('#timer-button').classList.toggle('running', startedAt !== null);
    $('#timer-button').classList.toggle('over-budget', seconds > 325);
    $('#timer-button').setAttribute('aria-label', `${startedAt === null ? '開始' : '暫停'}計時，已用 ${seconds} 秒`);
  }
  function toggleTimer() { if (startedAt === null) startedAt = now(); else { elapsed += now() - startedAt; startedAt = null; } tick(); }
  $('#timer-button').addEventListener('click', toggleTimer);
  setInterval(tick, 250);
  document.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable) return;
    if (document.querySelector('dialog[open]')) return;
    const key = event.key.toLowerCase();
    if ((event.target.closest('button,a') && [' ', 'enter'].includes(key))) return;
    if (['arrowright','pagedown',' '].includes(key)) { event.preventDefault(); next(); }
    else if (['arrowleft','pageup'].includes(key)) { event.preventDefault(); previous(); }
    else if (key === 'home') { event.preventDefault(); go(0); }
    else if (key === 'end') { event.preventDefault(); go(slides.length - 1); }
    else if (key === 'o') openDialog('#overview-dialog');
    else if (key === 'n') openDialog('#notes-dialog');
    else if (key === 'f') fullscreen();
    else if (key === 't') toggleTimer();
    else if (key === 'r') { elapsed = 0; startedAt = null; tick(); }
  });
  window.addEventListener('hashchange', fromHash);
  fromHash(); tick();
})();
