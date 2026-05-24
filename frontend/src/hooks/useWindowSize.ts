import { useEffect, useState } from "react";

interface WindowSizeFlags {
  width: number;
  isMobile: boolean;
  isTablet: boolean;
}

export function useWindowSize(): WindowSizeFlags {
  const compute = (): WindowSizeFlags => {
    const width = window.innerWidth;
    return {
      width,
      isMobile: width < 640,
      isTablet: width < 1024,
    };
  };

  const [flags, setFlags] = useState<WindowSizeFlags>(() => compute());

  useEffect(() => {
    const onResize = () => setFlags(compute());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return flags;
}
