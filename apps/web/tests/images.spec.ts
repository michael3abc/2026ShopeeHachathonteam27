import { expect, test, type Page } from "@playwright/test";
import type { AttachmentView } from "../src/contracts/attachment-view";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=", "base64");
const selected = (name = "photo.png") => ({ name, mimeType: "image/png", buffer: png });
const record = (n: number): AttachmentView => ({
  attachment_id: n.toString(16).padStart(32, "0"), artifact_ref: "artifact://upload/" + n.toString(16).padStart(32, "0"),
  evidence_id: "EV-" + n, subject: "LI-1", media_type: "image/png", width: 1, height: 1,
  size_bytes: png.length, content_sha256: "a".repeat(64),
});
const options = {max_bytes: 10485760, max_images: 6, max_pixels: 25000000,
  media_types: ["image/png", "image/jpeg", "image/webp"], subjects: {ORDER: "外包裝", "LI-1": "收納盒"}};

async function baseRoutes(page: Page) {
  await page.route("**/backend/attachments/options?**", route => route.fulfill({json: options}));
  await page.route("**/backend/attachments/*/content", route => route.fulfill({contentType: "image/png", body: png}));
}

async function home(page: Page) {
  await baseRoutes(page);
  await page.goto("/");
  await page.getByLabel("訂單編號").fill("ORDER-1");
  await page.getByLabel("告訴退貨助理商品遇到的問題").fill("商品到貨有裂痕");
  await expect(page.getByRole("button", {name: "選擇圖片"})).toBeEnabled();
}

async function imageEvent(page: Page, kind: "drop" | "paste", name: string, label = "告訴退貨助理商品遇到的問題") {
  await page.getByLabel(label).evaluate((element, args) => {
    const data = new DataTransfer();
    data.items.add(new File([new Uint8Array(args.bytes)], args.name, {type: "image/png"}));
    element.dispatchEvent(args.kind === "drop" ? new DragEvent("drop", {dataTransfer: data, bubbles: true, cancelable: true}) :
      new ClipboardEvent("paste", {clipboardData: data, bubbles: true, cancelable: true}));
  }, {bytes: [...png], kind, name});
}

test("initial application accepts picker, drop and clipboard and preserves refs", async ({page}) => {
  await home(page);
  let count = 0;
  await page.route("**/backend/attachments", route => route.fulfill({status: 201, json: record(++count)}));
  await page.getByLabel("證據圖片", {exact: true}).setInputFiles(selected());
  await expect(page.getByText("已上傳", {exact:true})).toHaveCount(1);
  await page.getByRole("button", {name: "放大附件"}).click();
  await expect(page.getByRole("dialog", {name: "圖片預覽"})).toBeVisible();
  await page.getByRole("button", {name: "關閉圖片"}).click();
  await expect(page.getByRole("dialog", {name: "圖片預覽"})).toHaveCount(0);
  await imageEvent(page, "drop", "drop.png");
  await imageEvent(page, "paste", "paste.png");
  await expect(page.getByText("已上傳", {exact:true})).toHaveCount(3);
  await page.getByRole("button", {name: "移除 drop.png", exact:true}).click();
  await page.route("**/backend/cases", route => {
    expect(route.request().postDataJSON().attached_artifact_refs).toEqual([record(1).artifact_ref, record(3).artifact_ref]);
    return route.fulfill({status: 503, json: {detail: "Temporary create failure"}});
  });
  await page.getByRole("button", {name: "送出", exact:true}).click();
  await expect(page.getByRole("alert").filter({hasText:"Temporary create failure"})).toHaveText("Temporary create failure");
  await expect(page.getByText("已上傳", {exact:true})).toHaveCount(2);
  await expect(page.getByLabel("告訴退貨助理商品遇到的問題")).toHaveValue("商品到貨有裂痕");
});

test("partial upload failure blocks send until explicit retry", async ({page}) => {
  await home(page);
  let count = 0;
  await page.route("**/backend/attachments", route => {
    count++;
    return count === 2 ? route.fulfill({status:503, json:{detail:"Storage unavailable"}}) : route.fulfill({status:201, json:record(count)});
  });
  await page.getByLabel("證據圖片", {exact:true}).setInputFiles([selected("one.png"), selected("two.png")]);
  await expect(page.getByText("Storage unavailable")).toBeVisible();
  await expect(page.getByRole("button", {name:"送出", exact:true})).toBeDisabled();
  await page.getByRole("button", {name:"重試", exact:true}).click();
  await expect(page.getByText("已上傳", {exact:true})).toHaveCount(2);
  await expect(page.getByRole("button", {name:"送出", exact:true})).toBeEnabled();
  expect(count).toBe(3);
});

test("rejects invalid type/count and requires a subject for multi-item orders", async ({page}) => {
  await home(page);
  let calls = 0;
  await page.route("**/backend/attachments", route => {calls++; return route.fulfill({status:201,json:record(calls)});});
  await page.getByLabel("證據圖片", {exact:true}).setInputFiles({name:"a.svg",mimeType:"image/svg+xml",buffer:Buffer.from("<svg/>")});
  await expect(page.getByRole("alert").filter({hasText:"僅接受 JPEG"})).toContainText("僅接受 JPEG");
  await page.getByLabel("證據圖片", {exact:true}).setInputFiles(Array.from({length:7},(_,i)=>selected(i+".png")));
  await expect(page.getByRole("alert").filter({hasText:"每則最多 6"})).toContainText("每則最多 6");
  expect(calls).toBe(0);
  await page.route("**/backend/attachments/options?**", route=>route.fulfill({json:{...options,subjects:{...options.subjects,"LI-2":"另一商品"}}}));
  await page.getByLabel("訂單編號").fill("ORDER-2");
  await expect(page.getByRole("button",{name:"選擇圖片"})).toBeEnabled();
  await page.getByLabel("證據圖片",{exact:true}).setInputFiles(selected());
  await expect(page.getByRole("alert").filter({hasText:"請先選擇"})).toContainText("請先選擇");
  await page.getByLabel("圖片對應品項").selectOption("LI-2");
  await page.getByLabel("證據圖片",{exact:true}).setInputFiles(selected());
  await expect(page.getByText("已上傳",{exact:true})).toHaveCount(1);
});

test("image-only evidence resumes and survives refresh with preview", async ({page}) => {
  await baseRoutes(page);
  let detail = {case_ref:"CASE-IMAGE",order_ref:"ORDER-1",user_ref:"demo_customer",status:"AWAITING_EVIDENCE",
    created_at:"2026-09-12T00:00:00Z",updated_at:"2026-09-12T00:00:00Z"};
  const turns: object[] = [{seq:1,message:"商品有裂痕",created_at:detail.created_at,attached_artifact_refs:[],attachments:[]}];
  await page.route("**/backend/cases/CASE-IMAGE",route=>route.fulfill({json:detail}));
  await page.route("**/backend/cases/CASE-IMAGE/conversation",route=>route.fulfill({json:{turns}}));
  await page.route("**/backend/cases/CASE-IMAGE/events",route=>route.fulfill({contentType:"text/event-stream",body:": idle\n\n"}));
  await page.route("**/backend/cases/CASE-IMAGE/activities?**",route=>route.fulfill({json:{events:[],next_cursor:0,has_more:false}}));
  await page.route("**/backend/cases/CASE-IMAGE/activities/stream?**",route=>route.fulfill({contentType:"text/event-stream",body:": idle\n\n"}));
  let uploaded = 0;
  await page.route("**/backend/attachments",route=>route.fulfill({status:201,json:record(++uploaded)}));
  await page.route("**/backend/cases/CASE-IMAGE/messages",route=>{
    const payload=route.request().postDataJSON();
    expect(payload).toEqual({message:"已補交所需資料。",attached_artifact_refs:[1,2,3].map(n=>record(n).artifact_ref)});
    detail={...detail,status:"OBSERVING",updated_at:"2026-09-12T00:01:00Z"};
    turns.push({seq:2,message:payload.message,created_at:detail.updated_at,attached_artifact_refs:payload.attached_artifact_refs,attachments:[1,2,3].map(record)});
    return route.fulfill({json:detail});
  });
  await page.goto("/cases/CASE-IMAGE");
  await expect(page.getByRole("button",{name:"選擇圖片"})).toBeEnabled();
  await page.getByLabel("證據圖片",{exact:true}).setInputFiles(selected());
  await expect(page.getByText("已上傳",{exact:true})).toHaveCount(1);
  await imageEvent(page, "drop", "followup-drop.png", "補充案件說明");
  await imageEvent(page, "paste", "followup-paste.png", "補充案件說明");
  await expect(page.getByText("已上傳",{exact:true})).toHaveCount(3);
  await page.getByRole("button",{name:"送出",exact:true}).click();
  await expect(page.getByRole("button",{name:"放大附件"})).toHaveCount(3);
  await page.reload();
  await expect(page.getByText("商品有裂痕",{exact:true})).toBeVisible();
  await expect(page.getByText("已補交所需資料。",{exact:true})).toHaveCount(1);
  await page.getByRole("button",{name:"放大附件"}).first().click();
  await expect(page.getByRole("dialog",{name:"圖片預覽"})).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog",{name:"圖片預覽"})).toHaveCount(0);
});
