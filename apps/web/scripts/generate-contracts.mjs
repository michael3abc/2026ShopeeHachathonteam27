import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { compileFromFile } from "json-schema-to-typescript";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const schemaRoot = path.resolve(webRoot, "../contracts/schemas/ui/v1");
const outputRoot = path.resolve(webRoot, "src/contracts");

const contracts = [
  ["AttachmentView.schema.json", "attachment-view.ts"],
  ["ConversationPage.schema.json", "conversation-page.ts"],
  ["UploadOptions.schema.json", "upload-options.ts"],
  ["ActivityEvent.schema.json", "activity-event.ts"],
  ["ActivityPage.schema.json", "activity-page.ts"],
  ["AgentEvent.schema.json", "agent-event.ts"],
  ["CaseDetail.schema.json", "case-detail.ts"],
  ["CreateCaseRequest.schema.json", "create-case-request.ts"],
  ["CreateCaseResponse.schema.json", "create-case-response.ts"],
  ["SendMessageRequest.schema.json", "send-message-request.ts"],
  ["ReviewDecision.schema.json", "review-decision.ts"],
];

await mkdir(outputRoot, { recursive: true });
await Promise.all(
  contracts.map(async ([schema, output]) => {
    const source = await compileFromFile(path.join(schemaRoot, schema), {
      bannerComment: "/* Generated from apps/contracts. Do not edit manually. */",
      style: { singleQuote: false },
    });
    await writeFile(path.join(outputRoot, output), source);
  }),
);
