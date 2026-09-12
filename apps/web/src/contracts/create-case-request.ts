/* Generated from apps/contracts. Do not edit manually. */

export type AttachedArtifactRefs = string[];
export type InitialMessage = string;
export type OrderRef = string;
export type UserRef = string;

/**
 * Backend API payload; Backend creates the case and starts/resumes the graph.
 */
export interface CreateCaseRequest {
  attached_artifact_refs?: AttachedArtifactRefs;
  initial_message: InitialMessage;
  order_ref: OrderRef;
  user_ref: UserRef;
}
