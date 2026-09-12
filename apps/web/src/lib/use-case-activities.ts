"use client";

import { useEffect, useState } from "react";

import type { ActivityEvent } from "@/contracts/activity-event";
import { caseActivitiesStreamUrl, getCaseActivities } from "@/lib/api";

/**
 * Load a case's activity history page by page, then follow the live stream from the
 * last cursor. EventSource resends Last-Event-ID on reconnect, and the API resumes
 * after it, so reconnects only deliver newer events; `event_id` still dedupes replays.
 */
export function useCaseActivities(caseRef: string) {
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let disposed = false;
    let source: EventSource | undefined;
    const seen = new Set<string>();

    function add(batch: ActivityEvent[]) {
      const fresh = batch.filter((activity) => !seen.has(activity.event_id));
      if (!fresh.length) return;
      for (const activity of fresh) seen.add(activity.event_id);
      setActivities((current) => [...current, ...fresh].sort((left, right) => left.seq - right.seq));
    }

    async function start() {
      let cursor = 0;
      for (;;) {
        const page = await getCaseActivities(caseRef, cursor);
        if (disposed) return;
        add(page.events);
        cursor = page.next_cursor;
        if (!page.has_more) break;
      }
      source = new EventSource(caseActivitiesStreamUrl(caseRef, cursor));
      source.onopen = () => setUnavailable(false);
      source.onerror = () => {
        if (!disposed) setUnavailable(true);
      };
      source.addEventListener("activity", (message) => {
        if (typeof message.data === "string") add([JSON.parse(message.data) as ActivityEvent]);
      });
    }

    // Activity is observational: when it cannot load, the stage says so and the case keeps working.
    start().catch(() => {
      if (!disposed) setUnavailable(true);
    });
    return () => {
      disposed = true;
      source?.close();
    };
  }, [caseRef]);

  return { activities, unavailable };
}
