import { useEffect, useRef } from "react";
import { track } from "../utils/analytics";

export function useTabEngagement(tabName: string): void {
  const enteredAt = useRef<number>(Date.now());
  const interactionCount = useRef<number>(0);
  const scrolledPastFold = useRef<boolean>(false);

  // Track scroll depth
  useEffect(() => {
    const el = document.getElementById("tab-content-scroll");
    if (!el) return;
    const onScroll = () => {
      if (el.scrollTop > el.clientHeight * 0.6) {
        scrolledPastFold.current = true;
      }
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [tabName]);

  // Track any click as an interaction
  useEffect(() => {
    const onClick = () => {
      interactionCount.current += 1;
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  // Fire on tab exit (cleanup = unmount)
  useEffect(() => {
    enteredAt.current = Date.now();
    interactionCount.current = 0;
    scrolledPastFold.current = false;

    return () => {
      const dwellSeconds = Math.round((Date.now() - enteredAt.current) / 1000);
      track("tab_engagement", {
        properties: {
          tab: tabName,
          dwell_seconds: dwellSeconds,
          scrolled_past_fold: scrolledPastFold.current,
          interaction_count: interactionCount.current,
        },
      });
    };
  }, [tabName]);
}
