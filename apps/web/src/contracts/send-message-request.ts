/* Generated from apps/contracts. Do not edit manually. */

export type AttachedArtifactRefs = string[];
export type Message = string;

export interface SendMessageRequest {
  attached_artifact_refs?: AttachedArtifactRefs;
  message: Message;
}
