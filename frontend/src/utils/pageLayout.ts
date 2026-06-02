import type { CSSProperties } from "react";

export const PAGE_MAX_WIDTH = "1200px";

/** Consistent page gutter — 16px on mobile, 40px on desktop. */
export function pagePadding(isMobile: boolean, bottomExtra = 0): string {
  const bottom = (isMobile ? 32 : 80) + bottomExtra;
  return isMobile ? `24px 16px ${bottom}px` : `40px 40px ${bottom}px`;
}

export function pageContainerStyle(
  isMobile: boolean,
  bottomExtra = 0
): CSSProperties {
  return {
    maxWidth: PAGE_MAX_WIDTH,
    margin: "0 auto",
    padding: pagePadding(isMobile, bottomExtra),
    width: "100%",
    boxSizing: "border-box",
  };
}

export function cardPadding(isMobile: boolean): string {
  return isMobile ? "20px 16px" : "40px";
}
