"use client";

import { useEffect, useMemo, useState } from "react";

import type { ActivityEvent } from "@/contracts/activity-event";
import { beatWeight, nextStepEnd, pendingSteps } from "@/lib/activity-playback.mjs";

export type PlaybackSpeed = "live" | "normal" | "slow";

const stepDwellMs: Record<Exclude<PlaybackSpeed, "live">, number> = { normal: 900, slow: 1800 };

/**
 * Replay activity beat by beat (a node starting, then each of its calls) so fast runs
 * stay readable. The graph may
 * trail the real case state while it catches up; case status and review never wait on it.
 */
export function useActivityPlayback(activities: ActivityEvent[]) {
  const [speed, setSpeed] = useState<PlaybackSpeed>("normal");
  const [revealed, setRevealed] = useState(0);
  const shown = speed === "live" ? activities.length : Math.min(revealed, activities.length);

  useEffect(() => {
    if (speed === "live" || shown >= activities.length) return;
    const timer = window.setTimeout(
      () => setRevealed(nextStepEnd(activities, shown)),
      shown === 0 ? 0 : stepDwellMs[speed] * beatWeight(activities[shown - 1]),
    );
    return () => window.clearTimeout(timer);
  }, [activities, shown, speed]);

  const visible = useMemo(
    () => (shown === activities.length ? activities : activities.slice(0, shown)),
    [activities, shown],
  );

  return {
    speed,
    visible,
    remainingSteps: pendingSteps(activities, shown),
    changeSpeed(next: PlaybackSpeed) {
      // Leaving live view continues from what is on screen instead of replaying it.
      if (speed === "live") setRevealed(activities.length);
      setSpeed(next);
    },
    skipToLatest() {
      setRevealed(activities.length);
    },
  };
}
