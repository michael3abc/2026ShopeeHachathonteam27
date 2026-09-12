/* Generated from apps/contracts. Do not edit manually. */

export type ArtifactRef = string;
export type AttachmentId = string;
export type ContentSha256 = string;
export type EvidenceId = string;
export type Height = number;
export type MediaType = string;
export type SizeBytes = number;
export type Subject = string;
export type Width = number;

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
