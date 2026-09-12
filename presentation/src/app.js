/* Static explorer. No fetch, API keys, model calls, modules or external assets. */
(() => {
  "use strict";
  const D = window.EXPLORER_DATA;
  const entities = new Map(D.entities.map((e) => [e.id, e]));
  const edges = new Map(D.edges.map((e) => [e.id, e]));
  const $ = (s) => document.querySelector(s);
  const esc = (v) =>
    String(v ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const icons = {
    actor: "ACTOR",
    service: "SERVICE",
    runtime: "RUNTIME",
    database: "DATABASE",
    queue: "QUEUE",
    module: "MODULE",
    capability: "CAPABILITY",
    worker: "WORKER",
    external: "EXTERNAL",
    node: "GRAPH NODE",
    terminal: "BOUNDARY",
    endpoint: "API",
    table: "DB TABLE",
    llm: "LLM CALL",
    event: "CONTRACT",
  };
  const nav = [
    ["overview", "作品介紹"],
    ["trace", "走完一案"],
    ["architecture", "系統架構"],
    ["agent", "Agent × 資料"],
    ["evidence", "驗證與 Code"],
  ];
  let timer = null;
  let searchReturnFocus = null;
  let zoom = 1;
  let route = readRoute();

  function readRoute() {
    const raw = location.hash.slice(1).split("?");
    const q = new URLSearchParams(raw[1] || "");
    return {
      page: nav.some(([id]) => id === raw[0]) ? raw[0] : "overview",
      view: q.get("view") || "",
      entity: q.get("entity") || "",
      edge: q.get("edge") || "",
      scenario: q.get("scenario") || "normal",
      step: Math.max(0, Number.parseInt(q.get("step") || "0", 10) || 0),
      group: q.get("group") || "",
      filter: q.get("filter") || "all",
      display: q.get("display") || "graph",
    };
  }
  function link(page, values = {}) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(values))
      if (v !== "" && v !== undefined && v !== null) q.set(k, String(v));
    return `#${page}${q.size ? "?" + q : ""}`;
  }
  function current(values = {}) {
    const { page, ...rest } = route;
    return link(page, { ...rest, ...values });
  }
  function go(url, replace = false) {
    if (replace) {
      history.replaceState(null, "", url);
      route = readRoute();
      render();
    } else if (location.hash === url) render();
    else location.hash = url;
  }
  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }
  function scenario() {
    return D.scenarios.find((s) => s.id === route.scenario) || D.scenarios[0];
  }
  function selectedStep() {
    const s = scenario();
    return s.steps[Math.min(route.step, s.steps.length - 1)];
  }
  const badge = (text = "Source verified", cls = "") =>
    `<span class="pill ${cls}">${esc(text)}</span>`;
  const tags = (items) =>
    `<div class="field-list">${items.map((x) => `<code class="tag">${esc(x)}</code>`).join("")}</div>`;
  function sourceRefs(ids, limit = 99) {
    return [...new Set(ids)]
      .slice(0, limit)
      .map((id) => {
        const s = D.sources[id];
        return `<div class="source"><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">↗ ${esc(s.symbol)} <span class="muted">L${s.line}</span></a><small class="muted">${esc(s.path)}</small><details><summary>離線查看固定版本 source</summary><pre>${esc(s.excerpt)}</pre></details></div>`;
      })
      .join("");
  }
  const entityButton = (id) =>
    `<button class="entity-link" data-entity="${esc(id)}">${esc(entities.get(id)?.title || id)} <code>${esc(id)}</code> ↗</button>`;
  function pageHeading(kicker, title, description) {
    return `<div class="page-heading"><div><span class="eyebrow">${esc(kicker)}</span><h1>${title}</h1><p>${description}</p></div>${badge("SOURCE · " + D.baseline.commit.slice(0, 7))}</div>`;
  }
  function tabs(items, active) {
    return `<div class="tabs" aria-label="視圖">${items.map(([id, label]) => `<a class="tab ${active === id ? "active" : ""}" ${active === id ? 'aria-current="page"' : ""} href="${esc(current({ view: id, group: "", edge: "" }))}">${label}</a>`).join("")}</div>`;
  }
  function inspector() {
    if (route.edge && edges.has(route.edge)) {
      const e = edges.get(route.edge);
      return `<aside class="inspector" aria-label="關係細節">${badge(e.evidence)}<h2>這條連線做什麼？</h2>${entityButton(e.from)}<p>↓ ${esc(e.kind)}</p>${entityButton(e.to)}<p>${esc(e.label)}</p>${e.lines ? `<p class="muted">_route 寫入／helper 來源行：${e.lines.join(", ")}。Source 支持此分支，不代表所有案件都會走這條路。</p>` : ""}<h3>來源</h3>${sourceRefs(e.refs)}<a class="button" href="${esc(current({ edge: "" }))}">關閉關係</a></aside>`;
    }
    const e = entities.get(route.entity);
    if (!e)
      return `<aside class="inspector" aria-label="元件細節"><span class="eyebrow">COMPONENT INSPECTOR</span><div class="empty-inspector"><span class="big-symbol">↗</span><h2>從一個元件開始。</h2><p>點選圖中元件，查看責任、輸入輸出、上下游與原始碼。選取連線則能看見通訊方式與條件。</p><p>所有圖共用 stable IDs。用右上方搜尋也能直接找到 node、API、event 或 table。</p></div></aside>`;
    const incoming = D.edges.filter((x) => x.to === e.id),
      outgoing = D.edges.filter((x) => x.from === e.id);
    const llmCalls = (D.llmCalls || []).filter(
      (c) => c.node === e.id || c.id === e.id,
    );
    return `<aside class="inspector" aria-label="元件細節"><span class="eyebrow">${esc(icons[e.type] || e.type)}</span>${badge(e.evidence)}<h2>${esc(e.title)}</h2><code class="entity-id">${esc(e.id)}</code><p>${esc(e.summary)}</p><h3>WHY / 為什麼存在</h3><p>${esc(e.why)}</p><h3>OWNS / 負責</h3><p>${esc(e.owns)}</p><h3>BOUNDARY / 不負責</h3><p>${esc(e.excludes)}</p><h3>INPUT → OUTPUT</h3><p><code>${esc(e.inputs)}</code></p><p>↓</p><p><code>${esc(e.outputs)}</code></p>
      ${e.reads ? `<h3>STATE READS · 含 graph.py 內 helpers</h3>${tags(e.reads)}<h3>STATE PATCH · reviewed outputs</h3>${tags(e.writes)}<p class="muted">AgentState 為 total=False TypedDict，未宣告 Annotated reducer；node 回傳 patch 取代對應欄位，history 由程式先組合。這裡是契約，不是某次完整 state snapshot。</p>${e.interrupt ? `<p class="callout">此 node 使用 interrupt。Resume 重新進入 node；await_human_review 以保存的 review_ref 避免每次重提。</p>` : ""}` : ""}
      ${llmCalls.map((c) => `<h3>實際 LLM CALL</h3>${entityButton(c.id)}<p><code>${esc(c.task)}</code> → <code>${esc(c.schema)}</code></p>`).join("")}
      <h3>FAILURE / 處理界線</h3><p>${esc(e.failure)}</p>
      ${e.foreignKeys?.length ? `<h3>DB FOREIGN KEYS · 非推測關聯</h3>${e.foreignKeys.map((f) => `<p><code>${esc(f.column)} → ${esc(f.target)}</code></p>`).join("")}` : ""}
      <h3>UPSTREAM</h3>${incoming.length ? incoming.map((x) => entityButton(x.from)).join("") : "<p class=muted>此視圖未列出上游。</p>"}
      <h3>DOWNSTREAM / 路由條件</h3>${outgoing.map((x) => `<button class="entity-link" data-edge="${esc(x.id)}">${esc(entities.get(x.to).title)} →<br><small>${esc(x.label)}</small></button>`).join("") || "<p class=muted>沒有列出的下游。</p>"}
      <div class="actions"><a class="button" href="${esc(link(["node", "llm"].includes(e.type) ? "agent" : "architecture", { view: e.type === "node" ? "exact" : e.type === "llm" ? "llm" : "service", entity: e.id }))}">在架構中定位</a><a class="button" href="${esc(link("evidence", { entity: e.id }))}">Code Map</a></div><h3>固定版本來源</h3>${sourceRefs(e.refs)}
    </aside>`;
  }

  const contextPositions = {
    buyer: [40, 70],
    human: [40, 205],
    web: [310, 70],
    api: [565, 70],
    agent: [565, 205],
    model: [565, 340],
    runtime: [310, 205],
    memory: [310, 340],
  };
  const servicePositions = {
    web: [30, 45],
    api: [295, 45],
    api_db: [580, 45],
    outbox: [295, 175],
    redis: [30, 305],
    worker: [295, 305],
    agent: [30, 175],
    runtime: [580, 305],
    providers: [580, 175],
    checkpoint: [580, 435],
    agent_db: [295, 435],
    memory_worker: [30, 435],
    model: [825, 305],
    activity: [825, 45],
  };
  const graphPositions = {
    __start__: [30, 30],
    parse_request: [290, 30],
    request_clarification: [560, 30],
    load_case_context: [290, 145],
    retrieve_policy: [290, 260],
    prepare_memory_query: [290, 375],
    retrieve_memory: [30, 375],
    assess_case: [290, 490],
    request_evidence: [560, 490],
    propose_decision: [290, 605],
    external_verification: [30, 720],
    reviewer: [290, 720],
    record_revision_event: [560, 605],
    await_human_review: [560, 720],
    emit_resolution_handoff: [290, 835],
    enqueue_memory_distillation: [560, 835],
    terminate_automation: [825, 490],
    __end__: [290, 960],
  };
  function diagram(positions, kind = "service", height = 540, activeIds = []) {
    const ids = Object.keys(positions),
      width = Math.max(...Object.values(positions).map((p) => p[0])) + 240;
    let filtered = D.edges.filter(
      (e) =>
        ids.includes(e.from) &&
        ids.includes(e.to) &&
        (kind === "graph" ? e.kind === "graph" : e.kind !== "graph") &&
        (!e.contextOnly || ["context", "hero"].includes(kind)),
    );
    if (route.filter !== "all" && kind !== "hero")
      filtered = filtered.filter((e) =>
        route.filter === "failure"
          ? e.to === "terminate_automation"
          : e.kind === route.filter,
      );
    const neighbors = new Set(
      D.edges
        .filter((e) => e.from === route.entity || e.to === route.entity)
        .flatMap((e) => [e.from, e.to]),
    );
    const edgeHtml = filtered
      .map((e, i) => {
        const [x1, y1] = positions[e.from],
          [x2, y2] = positions[e.to];
        let d;
        if (e.from === e.to)
          d = `M${x1 + 185},${y1 + 15} C${x1 + 280},${y1 - 35} ${x1 + 280},${y1 + 115} ${x1 + 185},${y1 + 52}`;
        else if (Math.abs(x2 - x1) > 220) {
          const right = x2 > x1;
          const sx = right ? x1 + 205 : x1,
            tx = right ? x2 : x2 + 205;
          d = `M${sx},${y1 + 34} C${(sx + tx) / 2},${y1 + 34} ${(sx + tx) / 2},${y2 + 34} ${tx},${y2 + 34}`;
        } else {
          const down = y2 > y1,
            sx = x1 + 102,
            sy = down ? y1 + 68 : y1,
            tx = x2 + 102,
            ty = down ? y2 : y2 + 68;
          const offset = Math.abs(y2 - y1) > 140 ? 75 + (i % 3) * 16 : 0;
          d = offset
            ? `M${sx + 70},${sy} C${sx + 145 + offset},${sy} ${tx + 145 + offset},${ty} ${tx + 70},${ty}`
            : `M${sx},${sy} C${sx},${(sy + ty) / 2} ${tx},${(sy + ty) / 2} ${tx},${ty}`;
        }
        const hi =
          route.edge === e.id ||
          (route.entity && (e.from === route.entity || e.to === route.entity));
        return `<path class="diagram-edge ${e.kind} ${e.to === "terminate_automation" ? "failure" : ""} ${hi ? "highlight" : route.entity ? "dim" : ""}" d="${d}" marker-end="url(#arrow-${kind})" data-edge="${esc(e.id)}" tabindex="0" role="button" aria-label="${esc(e.from + " → " + e.to + "：" + e.label)}"><title>${esc(e.label)}</title></path>`;
      })
      .join("");
    const nodes = ids
      .map((id) => {
        const e = entities.get(id),
          [x, y] = positions[id],
          selected = route.entity === id,
          related = neighbors.has(id);
        return `<g class="diagram-node ${selected ? "selected" : related ? "related" : route.entity ? "dim" : ""} ${activeIds.includes(id) ? "active-trace" : ""}" transform="translate(${x} ${y})" tabindex="0" role="button" data-entity="${esc(id)}" aria-label="${esc(e.title + " · " + id)}"><title>${esc(e.summary)}</title><rect width="205" height="68" rx="9"/><text class="node-title" x="14" y="27">${esc(e.title)}</text><text class="node-id" x="14" y="48">${esc(id)}</text>${e.interrupt ? '<circle cx="189" cy="17" r="4" fill="#c74d2d"/>' : ""}</g>`;
      })
      .join("");
    return `<div class="diagram-viewport ${kind === "hero" ? "hero-diagram" : ""}" data-pan><svg viewBox="0 0 ${width} ${height}" aria-label="${esc(kind)} architecture diagram" role="group"><defs><marker id="arrow-${kind}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#849288"/></marker></defs>${kind === "graph" ? `<rect class="diagram-boundary" x="12" y="10" width="${width - 22}" height="${height - 20}"/><text x="825" y="40" class="edge-text">LangGraph boundary</text>` : ""}${edgeHtml}${nodes}</svg></div>`;
  }
  function legend() {
    return `<div class="legend"><span>同步呼叫 / Graph transition</span><span class="async">非同步 command / event</span><span class="db">DB 存取</span><span class="obs">觀察事件</span></div>`;
  }
  function controls(filters = true) {
    return `<div class="tools">${
      filters
        ? `<select id="edge-filter" aria-label="連線類型"><option value="all">所有連線</option>${[
            ["graph", "Graph"],
            ["http", "HTTP"],
            ["command", "Command"],
            ["event", "Event"],
            ["db", "DB"],
            ["observation", "Activity / SSE"],
            ["failure", "失敗路徑"],
          ]
            .map(
              ([v, l]) =>
                `<option value="${v}" ${route.filter === v ? "selected" : ""}>${l}</option>`,
            )
            .join("")}</select>`
        : ""
    }<button data-zoom="out" aria-label="縮小">−</button><button data-zoom="fit">Fit</button><button data-zoom="in" aria-label="放大">＋</button><a class="tab" href="${esc(current({ display: route.display === "list" ? "graph" : "list" }))}">${route.display === "list" ? "圖形" : "列表"}</a></div>`;
  }
  function entityList(ids) {
    return `<div class="list-grid">${ids
      .map((id) => {
        const e = entities.get(id);
        return `<button class="list-item ${route.entity === id ? "selected" : ""}" data-entity="${esc(id)}"><strong>${esc(e.title)}</strong><small><code>${esc(id)}</code><br>${esc(e.summary)}</small></button>`;
      })
      .join("")}</div>`;
  }
  function relationships(ids, graphOnly = false) {
    const es = D.edges.filter(
      (e) =>
        ids.includes(e.from) &&
        ids.includes(e.to) &&
        (!graphOnly || e.kind === "graph"),
    );
    return `<details class="edge-list"><summary>逐條查看 ${es.length} 個關係與條件</summary>${es.map((e) => `<div class="edge-row"><button data-edge="${esc(e.id)}">${esc(e.from)} → ${esc(e.to)}</button><small>${esc(e.kind)} · ${esc(e.label)}</small></div>`).join("")}</details>`;
  }

  function overview() {
    return `<section class="hero"><div><span class="eyebrow"><span class="dot"></span>TEAM 27 / SYSTEM ARCHITECTURE EXPLORER</span><h1>讓每一次退款，<br>都有<span class="accent">依據。</span></h1><p>從一句商品問題，到一份可追溯的決策。探索退貨 Agent 如何結合政策、證據與人工經驗，讓自動化知道何時處理、何時交接。</p><div class="actions"><a class="button primary" href="#overview?view=intro">2 分鐘認識作品 <span>↗</span></a><a class="button" href="#trace">10 分鐘工程導覽 <span>→</span></a></div><div class="hero-bottom"><span>● 固定版本 source</span><span>◇ 可離線探索</span><span>合成案例 · 模擬退款</span></div></div><div class="hero-visual"><div class="visual-caption"><span class="mono">01 / SYSTEM CONTEXT</span><span>點選元件探索 ↗</span></div>${diagram(contextPositions, "hero", 435)}<div class="visual-note">Frontend 呈現體驗 · API 擁有案件 · Agent 負責推進決策<br>外部模型提供結果，業務授權仍由系統驗證。</div></div></section>
      <div class="stats"><div class="stat"><strong>06</strong><span>架構視角，逐層理解系統</span></div><div class="stat"><strong>${D.graph ? Object.keys(D.graph.nodes).length : "16"}</strong><span>實際 LangGraph nodes</span></div><div class="stat"><strong>05</strong><span>可逐步探索的示意案例</span></div><div class="stat"><strong>${D.baseline.commit.slice(0, 7)}</strong><span>固定 source commit</span></div></div>
      <section class="section" id="introduction"><div class="section-head"><div><span class="eyebrow">A CASE, THREE PERSPECTIVES</span><h2>把複雜流程，變成可理解的決定。</h2></div><p>買家需要知道還缺什麼；審核者需要完整依據；工程師需要清楚的責任邊界。</p></div><div class="cards"><article class="card"><span class="number mono">01 / BUYER</span><h3>說明問題，補上關鍵證據。</h3><p>系統辨識申請範圍，將不足的資料轉成具體問題，透過同一案件持續補充。</p><a class="textlink" href="#trace?scenario=evidence">走一次補件流程 →</a></article><article class="card"><span class="number mono">02 / REVIEWER</span><h3>依據完整，才授權執行。</h3><p>Policy、Evidence、Verification 與 Reviewer 各有責任；必要時保存狀態，交由人工裁決。</p><a class="textlink" href="#trace?scenario=human">看看人工如何介入 →</a></article><article class="card"><span class="number mono">03 / ENGINEER</span><h3>從畫面一路找到原始碼。</h3><p>追蹤 request、command、Graph、checkpoint 與 SSE，理解一個操作如何穿過整套系統。</p><a class="textlink" href="#architecture">打開系統架構 →</a></article></div></section>
      <div class="feature-strip"><div><h3>人留下經驗，系統學會如何更好地取證。</h3><p>Correction 可以進入背景蒸餾；只有經治理核准的 Memory 才可被後續案件檢索。學習效果仍需實跑驗證。</p></div><a class="button" href="#trace?scenario=memory">探索 Memory →</a></div>
      <section class="section"><div class="section-head"><div><span class="eyebrow">WHAT EXISTS / WHAT IS SIMULATED</span><h2>從可查核的能力開始。</h2></div></div><div class="cards"><article class="card"><h3>Source 可確認</h3><p>LangGraph routing、interrupt / resume、transactional outbox、HTTP Providers、獨立 activity feed 與 Memory workers。</p>${sourceRefs([D.refs.compose], 1)}</article><article class="card"><h3>Demo 的實際界線</h3><p>基準使用 fixture orders / evidence 與模擬 refund application；不是正式平台政策或真實金流。</p>${sourceRefs([D.refs.readme], 1)}</article><article class="card"><h3>成果證據</h3><p>此站提供 source 與測試定義的對照。未載入 live execution、效能 benchmark 或 B→C 學習成功紀錄。</p><a class="textlink" href="#evidence">查看來源與限制 →</a></article></div></section>
      ${route.entity ? `<section class="section workspace"><div>${pageHeading("SELECTED COMPONENT", "你選取的元件", "繼續沿上游、下游或 code map 深入。")}</div>${inspector()}</section>` : ""}`;
  }
  function architecture() {
    const view = ["context", "service", "ownership"].includes(route.view)
      ? route.view
      : "service";
    let inner;
    if (view === "ownership") inner = ownership();
    else {
      const positions =
        view === "context" ? contextPositions : servicePositions;
      inner = `<div class="canvas-card"><div class="canvas-top"><h3>${view === "context" ? "System Context / 對外邊界" : "Service Architecture / 執行與通訊"}</h3>${controls()}</div>${route.display === "list" ? entityList(Object.keys(positions)) : diagram(positions, view, view === "context" ? 435 : 540)}${legend()}<div class="hint">${view === "context" ? "此圖說明使用者、系統入口與外部模型。深入 Service Architecture 查看實際 DB、queue 與 worker。" : "Agent Service 是 queue-driven worker service；API 是 canonical case owner。HTTP Provider 經 API 存取業務資料，Graph checkpoint 則存 Agent DB。Activity 連線是經 transport 的觀察路徑，非瀏覽器直接讀 Graph。"}</div>${relationships(Object.keys(positions))}</div>`;
    }
    return `${pageHeading("03 / SYSTEM ARCHITECTURE", "每個元件，都有清楚的邊界。", "從 Actors 走進 Services，再找到資料的 owner。點選元件或連線，查看實際實作與契約。")}${tabs(
      [
        ["context", "01 System Context"],
        ["service", "02 Services"],
        ["ownership", "03 Data Ownership"],
      ],
      view,
    )}<div class="workspace"><div>${inner}<div class="callout"><strong>部署條件</strong><br>${D.baseline.conditions.map(esc).join("<br>")}</div>${sourceRefs([D.refs.compose_file], 1)}</div>${inspector()}</div>`;
  }
  function ownership() {
    const tables = D.schema.tables;
    return `<div class="canvas-card"><div class="canvas-top"><h3>Data Ownership / 資料與讀寫責任</h3><small>LOGICAL OWNERS ≠ ONE SHARED DATABASE</small></div><div class="data-owners"><section class="owner-column"><h3>API PostgreSQL</h3><p class="muted"><small>API 為直接讀寫者；Agent 使用 HTTP Providers。下列實體表由固定版本 SQLAlchemy models 抽取。</small></p>${tables.map((t) => entityButton("table:" + t.name)).join("")}</section><section class="owner-column"><h3>Agent PostgreSQL</h3>${entityButton("checkpoint")}${entityButton("worker")}${entityButton("memory_worker")}<p><code>agent_command_journal</code></p><p class="muted"><small>AsyncPostgresSaver 管理的實體 schema 由依賴建立，此 repo 未定義完整欄位；不推測 foreign keys。</small></p>${sourceRefs([D.refs.journal], 1)}</section><section class="owner-column"><h3>Transport / UI</h3>${entityButton("redis")}${entityButton("activity")}${entityButton("web")}<p class="muted"><small>Redis 保存 stream / pending。Frontend selection、connection、playback 是 UI state。兩者都不是 canonical case database。</small></p><h3>關聯 ID</h3>${tags(["case_ref", "thread_id", "command_id", "event_id", "handoff_id"])}<p class="muted"><small>case_ref → thread_id 是 Backend-private logical execution mapping，不是跨 DB foreign key。</small></p></section></div><div class="hint">點選 table 查看實際 columns 與 DB foreign keys。業務 transaction 與 Redis publish 分開；outbox 使待發訊息可恢復，但不宣稱跨系統 exactly-once。</div></div>`;
  }
  function graphView() {
    let positions = graphPositions;
    if (route.group) {
      const group = D.groups.find((g) => g.id === route.group);
      if (group)
        positions = Object.fromEntries(
          group.nodes.map((n, i) => [
            n,
            [30 + (i % 2) * 320, 40 + Math.floor(i / 2) * 160],
          ]),
        );
    }
    const height = route.group ? 420 : 1065;
    return `<div class="canvas-card"><div class="canvas-top"><h3>LangGraph Exact View ${route.group ? "/ 階段展開" : ""}</h3>${controls()}</div>${route.group ? `<div class="hint">這是語意階段的 node 子集合，不是實作 subgraph。<a href="#agent?view=exact">回到完整 Graph →</a></div>` : ""}${route.display === "list" ? entityList(Object.keys(positions)) : diagram(positions, "graph", height)}${legend()}<div class="hint">橘點表示 interrupt node。註冊共用 destinations；本圖顯示逐 node 核對的 source-supported routes。曲線只表示轉移，不表示執行時間。API execute_refund 與 MemoryWorker 不屬於這個 Graph。</div>${relationships(Object.keys(positions), true)}</div>`;
  }
  function agentPage() {
    const view = ["overview", "exact", "sequence", "ui", "llm"].includes(
      route.view,
    )
      ? route.view
      : "overview";
    let inner = "";
    if (view === "overview")
      inner = `<div class="callout">High-level 是閱讀用的語意分組，可展開到真實 nodes。本版沒有宣告對應的 LangGraph subgraphs。</div><div class="group-cards">${D.groups.map((g, i) => `<article class="group-card"><span class="count mono">0${i + 1} / ${g.nodes.length} NODES</span><h3>${g.title}</h3>${g.nodes.map((n) => `<code>${esc(n)}</code>`).join("")}<a href="${esc(link("agent", { view: "exact", group: g.id, entity: g.nodes[0] }))}">展開這個階段 ↗</a></article>`).join("")}</div><div class="canvas-card"><div class="canvas-top"><h3>高階階段之間的實際關係</h3></div>${groupDiagram()}<div class="hint">主要路徑向前；補件與修正會回到前面的階段。交接包含 resolution 與 terminate，不等於退款已完成。</div></div><div class="workspace section"><div class="card"><h3>三種狀態，三個 owner。</h3><p>Graph 保存 execution state 與 counters；API 保存案件狀態與授權；Frontend 將 CaseDetail 與 activity 轉成可見畫面。</p><div class="actions"><a class="button" href="#agent?view=sequence">追蹤跨服務互動 →</a><a class="button" href="#agent?view=llm">看實際 LLM 呼叫 →</a></div></div>${inspector()}</div>`;
    if (view === "exact")
      inner = `<div class="workspace"><div>${graphView()}</div>${inspector()}</div>`;
    if (view === "sequence")
      inner = `${scenarioTabs()}<div class="workspace"><div class="canvas-card"><div class="canvas-top"><h3>Frontend × Agent × DB / Sequence</h3><small>ILLUSTRATIVE / 因果步驟示意</small></div>${sequence(scenario().steps)}<div class="hint">點擊 sequence 步驟，可進入對應案例回放。此時間線沒有宣稱跨服務全域時間或真實 latency。checkpoint commit 的精確時刻未記錄。</div></div>${inspector()}</div>`;
    if (view === "ui")
      inner = `<div class="workspace"><div class="canvas-card"><div class="canvas-top"><h3>Backend State → Frontend UI</h3><small>不是 Graph state 的直接鏡像</small></div><div class="table-scroll"><table><thead><tr><th>BACKEND STATUS</th><th>畫面 / COMPONENT</th><th>ACTION → RESUME</th></tr></thead><tbody>${D.uiMappings.map((m) => `<tr><td><code>${m.status}</code></td><td>${esc(m.screen)}<br><code>${esc(m.component)}</code></td><td>${esc(m.action)}<br><code>${esc(m.next)}</code>${sourceRefs(m.refs, 1)}</td></tr>`).join("")}</tbody></table></div><div class="hint">case events 的 projection event 觸發 CaseDetail refresh；useCaseActivities 使用自己的分頁與 SSE cursor。graphProgress 依 next_node，不能只靠 seq 推斷 edge。</div></div>${inspector()}</div>`;
    if (view === "llm") inner = llmView();
    return `${pageHeading("04 / AGENT × DATA", "看懂 Agent，如何真正運作。", "從高階階段展開到原始 node，再追蹤 LLM、API、checkpoint 與前端呈現。")}${tabs(
      [
        ["overview", "01 高階 Graph"],
        ["exact", "02 真實 Graph"],
        ["llm", "03 LLM Calls"],
        ["sequence", "04 跨服務 Sequence"],
        ["ui", "05 UI Mapping"],
      ],
      view,
    )}${inner}`;
  }
  function groupDiagram() {
    const groupFor = (n) => D.groups.find((g) => g.nodes.includes(n))?.id;
    const pairs = new Set(
      D.edges
        .filter((e) => e.kind === "graph")
        .map((e) => [groupFor(e.from), groupFor(e.to)])
        .filter(([a, b]) => a && b && a !== b)
        .map((p) => p.join(":")),
    );
    const coords = Object.fromEntries(
      D.groups.map((g, i) => [g.id, [25 + i * 225, 130]]),
    );
    return `<div class="diagram-viewport"><svg viewBox="0 0 1150 310" role="group" aria-label="High-level LangGraph"><defs><marker id="group-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#849288"/></marker></defs>${[
      ...pairs,
    ]
      .map((p) => {
        const [a, b] = p.split(":"),
          [x] = coords[a],
          [x2] = coords[b],
          adj = x2 - x === 225;
        return `<path class="diagram-edge graph" marker-end="url(#group-arrow)" d="${adj ? `M${x + 195},164 L${x2},164` : `M${x + 100},130 C${x + 100},${x > x2 ? 25 : 55} ${x2 + 100},${x > x2 ? 25 : 55} ${x2 + 100},130`}"/>`;
      })
      .join(
        "",
      )}${D.groups.map((g) => `<g class="diagram-node" tabindex="0" role="button" data-group="${g.id}" transform="translate(${coords[g.id].join(" ")})" aria-label="展開${g.title}"><rect width="195" height="68" rx="9"/><text class="node-title" x="14" y="28">${g.title}</text><text class="node-id" x="14" y="49">${g.nodes.length} actual nodes · expand ↗</text></g>`).join("")}</svg></div>`;
  }
  function scenarioTabs() {
    return `<div class="tabs" aria-label="案例場景">${D.scenarios.map((s) => `<a class="tab ${scenario().id === s.id ? "active" : ""}" href="${esc(current({ scenario: s.id, step: 0, entity: "", edge: "" }))}">${s.title}</a>`).join("")}</div>`;
  }
  function sequence(steps, compact = false) {
    const lanes = [
      "web",
      "api",
      "api_db",
      "redis",
      "worker",
      "runtime",
      "agent_db",
      "model",
    ];
    const laneFor = (id) => {
      if (lanes.includes(id)) return id;
      if (["buyer", "human"].includes(id)) return "web";
      if (
        [
          "outbox",
          "refund",
          "policy",
          "evidence",
          "verification",
          "activity",
          "memory",
          "governance",
        ].includes(id)
      )
        return "api";
      if (id === "checkpoint") return "agent_db";
      if (id === "providers") return "api";
      return "worker";
    };
    const visible = compact
      ? steps.slice(Math.max(0, route.step - 1), route.step + 2)
      : steps;
    const offset = compact ? Math.max(0, route.step - 1) : 0;
    const h = 75 + visible.length * 65;
    return `<div class="sequence"><svg viewBox="0 0 1000 ${h}" role="group" aria-label="跨服務 sequence"><defs><marker id="seq-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#c74d2d"/></marker></defs>${lanes.map((l, i) => `<text class="seq-label" x="${45 + i * 125}" y="20">${esc(l)}</text><line class="seq-line" x1="${65 + i * 125}" x2="${65 + i * 125}" y1="35" y2="${h}"/>`).join("")}${visible
      .map((s, i) => {
        const a = lanes.indexOf(laneFor(s.from)) * 125 + 65,
          b = lanes.indexOf(laneFor(s.to)) * 125 + 65,
          y = 70 + i * 65;
        return `<g class="seq-event ${i + offset === route.step ? "selected" : ""}" data-step="${i + offset}" role="button" tabindex="0" aria-label="步驟 ${i + offset + 1} ${esc(s.title)}"><rect x="5" y="${y - 29}" width="990" height="57" rx="5"/><text x="${Math.min(a, b)}" y="${y - 11}">${i + offset + 1}. ${esc(s.title)} · ${s.kind}</text><line x1="${a}" y1="${y + 8}" x2="${a === b ? b + 52 : b}" y2="${y + 8}" marker-end="url(#seq-arrow)" ${["event", "command", "observation"].includes(s.kind) ? 'stroke-dasharray="6 4"' : ""}/></g>`;
      })
      .join("")}</svg></div>`;
  }
  function tracePage() {
    const s = scenario(),
      index = Math.min(route.step, s.steps.length - 1),
      step = s.steps[index];
    const previous = {};
    for (const item of s.steps.slice(0, index))
      Object.assign(previous, item.patch);
    const after = { ...previous, ...step.patch };
    const llm = (D.llmCalls || []).filter((c) => c.node === step.node);
    return `${pageHeading("02 / FOLLOW A CASE", "一個案件，走過整套系統。", "選一條路徑，逐步觀察畫面、服務與資料如何改變。每個 highlight 都指向目前選中的教學步驟。")}${scenarioTabs()}<div class="trace-layout"><aside class="timeline" aria-label="案例步驟"><ol>${s.steps.map((t, i) => `<li><button data-step="${i}" class="${i === index ? "current" : i < index ? "visited" : ""}" ${i === index ? 'aria-current="step"' : ""}><span>${i + 1}</span>${esc(t.title)}</button></li>`).join("")}</ol></aside><div><div class="canvas-card"><div class="trace-head">${badge(s.provenance, "illustrative")} <small class="muted">不是 live execution · 精確耗時未記錄</small><h2>${esc(step.title)}</h2><p>${esc(step.detail)}</p></div><div class="trace-controls"><button class="button" data-play="prev" ${index === 0 ? "disabled" : ""}>← Previous</button><button class="button primary" data-play="toggle">${timer ? "Ⅱ Pause" : "▷ Play"}</button><button class="button" data-play="next" ${index === s.steps.length - 1 ? "disabled" : ""}>Next →</button><button class="button" data-play="restart">↺ Restart</button><span class="position mono">${String(index + 1).padStart(2, "0")} / ${s.steps.length}</span></div><div class="progress-track"><div class="progress-fill" style="width:${((index + 1) / s.steps.length) * 100}%"></div></div>
      <div class="trace-split"><div class="mini-ui"><div class="mini-ui-head"><strong>RETURN CASE</strong><span>UI 示意 · 非截圖</span></div><div class="mini-ui-body"><div class="bubble buyer">收到的藍牙喇叭有裂痕，我希望退貨退款。</div><div class="bubble">${esc(step.ui)}</div><div class="ui-status">${esc(step.status)}</div><small class="muted">畫面由 Backend status 與觀察事件形成，不直接讀 checkpoint。</small></div></div><div class="state-block"><h3>這一步的責任與資料</h3>${entityButton(step.from)}<p>↓ ${esc(step.kind)}</p>${entityButton(step.to)}<h3>DB / PERSISTENCE</h3><p>${esc(step.db)}</p><h3>GRAPH NODE</h3>${step.node ? entityButton(step.node) : "<p>此步驟在 Graph 之外。</p>"}${llm.map((c) => `<h3>LLM TASK · SOURCE</h3>${entityButton(c.id)}`).join("")}</div></div>
      <div class="canvas-top"><h3>服務定位 / 同步 highlight</h3><small>只標示目前步驟，不代表同時執行</small></div>${diagram(servicePositions, "trace", 530, step.entities)}${legend()}<div class="canvas-top"><h3>鄰近步驟 / 通訊順序</h3><a class="textlink" href="${esc(link("agent", { view: "sequence", scenario: s.id, step: index }))}">完整 Sequence ↗</a></div>${sequence(s.steps, true)}<div class="trace-split"><div><h3>Before · 部分示意 state</h3><pre>${esc(Object.keys(previous).length ? JSON.stringify(previous, null, 2) : "未記錄完整 state；本示意尚無列出的 patch。")}</pre></div><div><h3>Patch → After · 部分示意 state</h3><pre>${esc(JSON.stringify({ patch: step.patch, after }, null, 2))}</pre><small class="muted">未列出的欄位不是空值；沒有完整 execution snapshot。</small></div></div><div class="hint">${s.note}</div></div><section class="section workspace"><div><h3>這一步的來源</h3>${sourceRefs(step.refs)}<h3>對照的測試定義 · 本輪未執行業務測試</h3>${sourceRefs([s.test])}</div>${inspector()}</section></div></div>`;
  }
  function llmView() {
    const calls = D.llmCalls || [];
    const call = calls.find((c) => c.id === route.entity);
    const detail = call
      ? `<section class="section"><span class="eyebrow">SOURCE CALL INSPECTOR / ${esc(call.task)}</span><h2>${esc(call.title)}</h2><div class="card"><h3>01 呼叫者 → adapter → 驗證</h3>${entityButton(call.node)}<p><code>model.generate → with_structured_output → invoke → TypeAdapter.validate_python</code></p><h3>02 Payload 組裝 · 真實 source expression</h3><pre>${esc(call.payloadExpression)}</pre><h3>03 Request 結構 · 非 captured HTTP body</h3><pre>${esc(JSON.stringify(call.requestShape, null, 2))}</pre><h3>04 System Prompt · 固定版本原文</h3><details><summary>展開 ${esc(call.task)} prompt</summary><pre>${esc(call.promptText)}</pre></details><h3>05 Output Schema / 回應驗證</h3><p><code>${esc(call.schema)}</code></p><p>${esc(call.response)}</p>${sourceRefs(call.refs)}</div></section>`
      : "";
    return `<div class="callout">模型呼叫存在於 source，不等於本網站正在呼叫模型。此處展示實際 task、payload 組裝、schema 與 adapter；未記錄 live HTTP response、token usage 或 latency。</div><div class="workspace"><div><div class="canvas-card"><div class="canvas-top"><h3>Node → ModelTask → Adapter → Structured Output</h3><small>LLM / EMBEDDING / BACKGROUND 分開呈現</small></div><div class="list-grid">${calls.map((c) => `<button class="list-item ${route.entity === c.id ? "selected" : ""}" data-entity="${c.id}"><strong>${esc(c.title)}</strong><small>${esc(c.scope)}<br><code>${esc(c.task)}</code><br>${esc(c.schema)}</small></button>`).join("")}</div><div class="hint">單一高階 node 不一定呼叫模型。Verification、gate、resume、DB projection 等使用 Python 與 providers。即使多個 task 共用 adapter，也不代表它們共用相同 prompt 或 output schema。</div></div>${detail}<div class="section"><h3>實際呼叫協定</h3><p class="muted">${esc(D.llmTransport?.summary || "")}</p>${sourceRefs(D.llmTransport?.refs || [])}<h3>失敗與驗證</h3><p class="muted">${esc(D.llmTransport?.failure || "")}</p></div></div>${inspector()}</div>`;
  }
  function evidencePage() {
    const mapIds = [
      "web",
      "api",
      "runtime",
      "policy",
      "evidence",
      "verification",
      "refund",
      "memory",
      "worker",
      "checkpoint",
      "activity",
      "model",
    ];
    return `${pageHeading("05 / EVIDENCE & CODE MAP", "每一個說明，都能找到來源。", "這裡區分 source、測試定義與實跑結果。網站建置驗證不會被當成業務系統的 E2E 驗收。")}<div class="validation-grid"><div class="card"><h3>內容基準</h3><p><code>${esc(D.baseline.commit)}</code></p><p>${esc(D.baseline.branch)} · 分析 ${esc(D.baseline.analyzedAt)}<br>API ${esc(D.baseline.profiles.api)}<br>Agent ${esc(D.baseline.profiles.agent)}</p>${badge("Source verified")} <p class="muted">${Object.keys(D.sources).length} 份 source references；${D.entities.length} 個可探索 entities。每個來源連結固定於同一 commit。</p></div><div class="card"><h3>驗證結果的界線</h3><p>所有情境：${badge("Illustrative", "illustrative")}</p><p>已有 test definitions 可查；沒有載入 Recorded execution。沒有宣稱 benchmark、B→C 學習改善或 10 分鐘讀者測試已通過。</p><p class="muted">網站 build / browser 驗證結果見交付目錄 VERIFICATION.md 與 verification-artifacts。</p></div></div>
      <section class="section"><span class="eyebrow">IF YOU WANT TO CHANGE SOMETHING</span><h2>從責任，找到修改入口。</h2><div class="codemap">${mapIds
        .map((id) => {
          const e = entities.get(id),
            s = D.sources[e.refs[0]];
          return `<button data-entity="${id}"><strong>${esc(e.title)} ↗</strong><small>${esc(s.path)}<br>${esc(s.symbol)}</small></button>`;
        })
        .join("")}</div></section>
      <section class="section workspace"><div><h2>取捨、差異與未知。</h2>${D.discrepancies.map((d) => `<article class="discrepancy"><h3>${esc(d.title)}</h3><p>${esc(d.detail)}</p><details><summary>查看證據</summary>${sourceRefs(d.refs)}</details></article>`).join("")}<article class="discrepancy"><h3>視覺參考</h3><p>${esc(D.designNote)}</p>${D.designReferences.map((r) => `<a class="button" href="${r.url}" rel="noopener noreferrer" target="_blank">${r.title} ↗</a>`).join(" ")}</article><div class="callout">更新內容：先指定新的 baseline SHA，再重新分析 source、review routing 與 scenario，最後重建並跑驗證。不能只把版本字串換成最新。</div></div>${inspector()}</section>`;
  }
  function render() {
    const focus = document.activeElement?.dataset?.play;
    $("#header").innerHTML =
      `<a class="brand" href="#overview" aria-label="Return Resolve 首頁"><span class="brandmark">↗</span><span>return / resolve<small>TEAM 27 · ENGINEERING EXPLORER</small></span></a><nav class="nav" aria-label="主要導覽">${nav.map(([id, label]) => `<a href="#${id}" ${route.page === id ? 'aria-current="page"' : ""}>${label}</a>`).join("")}</nav><button class="icon-button" data-search>⌕ 搜尋 <span class="mono">/</span></button>`;
    const crumb = `<div class="breadcrumb"><a href="#overview">Explorer</a><span>/</span><span>${nav.find(([id]) => id === route.page)[1]}</span>${route.view ? `<span>/</span><span>${esc(route.view)}</span>` : ""}${route.group ? `<span>/</span><span>${esc(route.group)}</span>` : ""}${route.entity ? `<span>/</span><span>${esc(entities.get(route.entity)?.title || route.entity)}</span>` : ""}${route.page !== "overview" ? '<button class="icon-button" data-back>← 返回</button>' : ""}</div>`;
    const content = {
      overview,
      trace: tracePage,
      architecture,
      agent: agentPage,
      evidence: evidencePage,
    }[route.page]();
    $("#main").innerHTML = `<div class="page">${crumb}${content}</div>`;
    $("#main").dataset.route = location.hash;
    $("#footer").innerHTML =
      `<span>RETURN / RESOLVE · TEAM 27<br>系統與教學案例依固定 source 編寫，使用合成資料與模擬退款。</span><span class="mono">${D.baseline.commit.slice(0, 7)} · ${D.baseline.profiles.api} / ${D.baseline.profiles.agent}<br><a href="${D.baseline.repository}/tree/${D.baseline.commit}" target="_blank" rel="noopener noreferrer">View source snapshot ↗</a></span>`;
    document.title = `${nav.find(([id]) => id === route.page)[1]} — Return / Resolve`;
    if (focus)
      document
        .querySelector(`[data-play="${focus}"]`)
        ?.focus({ preventScroll: true });
    attachPan();
    if (route.page === "overview" && route.view === "intro")
      $("#introduction")?.scrollIntoView({ block: "start" });
  }
  function pickEntity(id) {
    stop();
    if (!entities.has(id)) return;
    go(current({ entity: id, edge: "" }));
    setTimeout(() => {
      const el = $(".inspector");
      if (el && innerWidth < 801) el.scrollIntoView({ block: "start" });
    }, 40);
  }
  function advance(delta) {
    const s = scenario();
    const next = Math.max(0, Math.min(s.steps.length - 1, route.step + delta));
    go(current({ step: next, entity: "", edge: "" }), true);
    if (next === s.steps.length - 1) {
      stop();
      render();
    }
  }
  function togglePlay() {
    if (timer) {
      stop();
      render();
      return;
    }
    if (route.step >= scenario().steps.length - 1)
      go(current({ step: 0 }), true);
    timer = setInterval(() => advance(1), 2200);
    render();
  }
  function openSearch() {
    stop();
    searchReturnFocus = document.activeElement;
    $("#search-dialog").innerHTML =
      `<div class="search-head"><h2 id="search-title">搜尋架構與原始碼</h2><button class="icon-button" data-close-search>關閉 Esc</button></div><label class="eyebrow" for="search-input">COMPONENT / API / EVENT / NODE / FILE</label><input id="search-input" placeholder="例如 reviewer、SSE、policy_documents…" autocomplete="off"><div id="search-results" aria-live="polite"></div>`;
    $("#search-dialog").showModal();
    searchResults("");
    $("#search-input").focus();
  }
  function closeSearch() {
    $("#search-dialog").close();
    searchReturnFocus?.focus();
  }
  function searchResults(query) {
    const q = query.toLowerCase().trim();
    const matches = D.entities.filter((e) =>
      [e.id, e.title, e.summary, e.inputs, e.outputs, ...e.refs]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
    $("#search-results").innerHTML = matches.length
      ? `<p class="muted"><small>${matches.length} 個結果</small></p>${matches
          .slice(0, 60)
          .map(
            (e) =>
              `<button class="search-result" data-search-entity="${esc(e.id)}"><strong>${esc(e.title)} <span class="pill">${icons[e.type] || e.type}</span></strong><small>${esc(e.id)} · ${esc(e.summary)}</small></button>`,
          )
          .join("")}`
      : '<p class="muted">找不到符合的元件。可改用 node ID、API 路徑或 module 名稱。</p>';
  }
  function attachPan() {
    document.querySelectorAll("[data-pan]").forEach((el) => {
      let start;
      el.addEventListener("pointerdown", (ev) => {
        if (ev.target.closest("[data-entity],[data-edge],[data-group]")) return;
        start = [ev.clientX, ev.clientY, el.scrollLeft, el.scrollTop];
        el.setPointerCapture(ev.pointerId);
        el.classList.add("dragging");
      });
      el.addEventListener("pointermove", (ev) => {
        if (start) {
          el.scrollLeft = start[2] - (ev.clientX - start[0]);
          el.scrollTop = start[3] - (ev.clientY - start[1]);
        }
      });
      const end = () => {
        start = null;
        el.classList.remove("dragging");
      };
      el.addEventListener("pointerup", end);
      el.addEventListener("pointercancel", end);
    });
  }
  document.addEventListener("click", (ev) => {
    const t = ev.target.closest(
      "[data-entity],[data-edge],[data-group],[data-step],[data-play],[data-search],[data-close-search],[data-search-entity],[data-back],[data-zoom]",
    );
    if (!t) return;
    if (t.dataset.entity !== undefined) return pickEntity(t.dataset.entity);
    if (t.dataset.edge !== undefined) {
      stop();
      return go(current({ edge: t.dataset.edge, entity: "" }));
    }
    if (t.dataset.group !== undefined)
      return go(link("agent", { view: "exact", group: t.dataset.group }));
    if (t.dataset.step !== undefined) {
      stop();
      return go(
        link("trace", { scenario: scenario().id, step: t.dataset.step }),
        route.page === "trace",
      );
    }
    if (t.dataset.play) {
      if (t.dataset.play === "toggle") return togglePlay();
      stop();
      if (t.dataset.play === "restart")
        return go(current({ step: 0, entity: "", edge: "" }), true);
      return advance(t.dataset.play === "next" ? 1 : -1);
    }
    if (t.hasAttribute("data-search")) return openSearch();
    if (t.hasAttribute("data-close-search")) return closeSearch();
    if (t.dataset.searchEntity !== undefined) {
      const e = entities.get(t.dataset.searchEntity);
      closeSearch();
      return go(
        link(e.type === "node" || e.type === "llm" ? "agent" : "architecture", {
          view:
            e.type === "node" ? "exact" : e.type === "llm" ? "llm" : "service",
          entity: e.id,
        }),
      );
    }
    if (t.hasAttribute("data-back")) {
      if (history.length > 1) history.back();
      else go("#overview");
      return;
    }
    if (t.dataset.zoom) {
      zoom =
        t.dataset.zoom === "fit"
          ? 1
          : Math.min(
              2.5,
              Math.max(0.6, zoom + (t.dataset.zoom === "in" ? 0.2 : -0.2)),
            );
      document.querySelectorAll(".diagram-viewport svg").forEach((svg) => {
        svg.style.width = `${zoom * 100}%`;
        if (t.dataset.zoom === "fit") svg.parentElement.scrollTo(0, 0);
      });
    }
  });
  document.addEventListener("input", (ev) => {
    if (ev.target.id === "search-input") searchResults(ev.target.value);
  });
  document.addEventListener("change", (ev) => {
    if (ev.target.id === "edge-filter")
      go(current({ filter: ev.target.value }));
  });
  document.addEventListener("keydown", (ev) => {
    if (
      (ev.key === "/" || (ev.ctrlKey && ev.key === "k")) &&
      !/INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)
    ) {
      ev.preventDefault();
      openSearch();
    }
    if (
      (ev.key === "Enter" || ev.key === " ") &&
      ev.target.matches("svg [role=button]")
    ) {
      ev.preventDefault();
      ev.target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }
  });
  window.addEventListener("hashchange", () => {
    stop();
    zoom = 1;
    const before = route;
    route = readRoute();
    render();
    if (before.page !== route.page) window.scrollTo(0, 0);
  });
  render();
})();
