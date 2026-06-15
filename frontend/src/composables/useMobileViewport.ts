import { onMounted, onUnmounted, ref } from "vue";

export const MOBILE_BREAKPOINT_PX = 768;

function readIsMobileViewport(): boolean {
  if (typeof window === "undefined") return false;
  return window.innerWidth <= MOBILE_BREAKPOINT_PX;
}

/** SITE·기능인제 등 현장 모바일 레이아웃 판별 (≤768px) */
export function useMobileViewport() {
  const isMobileViewport = ref(readIsMobileViewport());

  function syncViewport() {
    isMobileViewport.value = readIsMobileViewport();
  }

  onMounted(() => {
    syncViewport();
    window.addEventListener("resize", syncViewport);
  });

  onUnmounted(() => {
    window.removeEventListener("resize", syncViewport);
  });

  return { isMobileViewport, syncViewport };
}
