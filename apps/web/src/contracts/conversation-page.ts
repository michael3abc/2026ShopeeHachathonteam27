/* Generated from apps/contracts. Do not edit manually. */

export type AttachedArtifactRefs = string[];
export type ArtifactRef = string;
export type AttachmentId = string;
export type ContentSha256 = string;
export type EvidenceId = string;
export type Height = number;
export type MediaType = string;
export type SizeBytes = number;
export type Subject = string;
export type Width = number;
export type Attachments = AttachmentView[];
export type CreatedAt = string;
export type Message = string;
export type Seq = number;
export type Turns = ConversationTurn[];

export interface ConversationPage {
  turns: Turns;
}
export interface ConversationTurn {
  attached_artifact_refs: AttachedArtifactRefs;
  attachments: Attachments;
  created_at: CreatedAt;
  message: Message;
  seq: Seq;
}
export interface AttachmentView {
  artifact_ref: ArtifactRef;
  attachment_id: AttachmentId;
  content_sha256: ContentSha256;
  evidence_id: EvidenceId;
  height: Height;
  media_type: MediaType;
  size_bytes: SizeBytes;
  subject: Subject;
  width: Width;
}
