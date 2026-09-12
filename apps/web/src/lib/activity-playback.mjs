/**
 * Playback reveals the activity stream in beats so fast runs stay readable. A beat
 * ends right after a node starts, or right after one of its tool or model calls
 * starts or finishes. During every pause one node is visibly running, and its calls
 * appear while it runs rather than only once it has finished.
 *
 * @typedef {import("../contracts/activity-event").ActivityEvent} ActivityEvent
 */

import { isStageActivity } from "./case-graph.mjs";

// Narration's own model call is not drawn on the graph, so pausing on it shows nothing.
const NARRATION_TASK = "ACTIVITY_NARRATION";

/** @param {ActivityEvent} activity */
function isNodeStart(activity) {
  return isStageActivity(activity) && activity.payload.type === "node" && activity.payload.phase === "STARTED";
}

/** @param {ActivityEvent} activity */
function isCallEvent(activity) {
  const { payload } = activity;
  return (
    isStageActivity(activity) &&
    (payload.type === "tool" || payload.type === "model") &&
    payload.name !== NARRATION_TASK
  );
}

/**
 * Exclusive end index of the beat that begins at `revealed`: just past the next node
 * start or call event, or the end of the stream.
 * @param {ActivityEvent[]} activities
 * @param {number} revealed number of activities already shown
 * @returns {number}
 */
export function nextStepEnd(activities, revealed) {
  for (let index = revealed; index < activities.length; index += 1) {
    if (isNodeStart(activities[index]) || isCallEvent(activities[index])) return index + 1;
  }
  return activities.length;
}

/**
 * How long to hold the beat that ended with `activity`, relative to a node step:
 * a call starting or finishing is a half beat inside its node.
 * @param {ActivityEvent | undefined} activity
 * @returns {number}
 */
export function beatWeight(activity) {
  return activity && isCallEvent(activity) ? 0.5 : 1;
}

/**
 * Node steps not yet shown; calls inside a node are not counted separately.
 * @param {ActivityEvent[]} activities
 * @param {number} revealed
 * @returns {number}
 */
export function pendingSteps(activities, revealed) {
  let steps = 0;
  for (let index = revealed; index < activities.length; index += 1) {
    if (isNodeStart(activities[index])) steps += 1;
  }
  return steps;
}
