import { onMounted, onUnmounted, ref } from "vue";

export const MOBILE_BREAKPOINT_PX = 768;

/** SITE·기능인제 등 현장 모바일 레이아웃 판별 (≤768px) */
export function useMobileViewport() {
  const isMobileViewport = ref(false);

  function syncViewport() {
    if (typeof window === "undefined") return;
    isMobileViewport.value = window.innerWidth <= MOBILE_BREAKPOINT_PX;
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
