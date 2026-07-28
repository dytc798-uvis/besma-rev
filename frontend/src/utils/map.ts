export type MapPreference = "NAVER" | "TMAP";

export interface MapDestination {
  name: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export function openMap(address: string, preference: MapPreference = "NAVER") {
  const encoded = encodeURIComponent((address || "").trim());
  if (!encoded) return;
  if (preference === "TMAP") {
    window.open(`https://apis.openapi.sk.com/tmap/app/routes?goalname=${encoded}`, "_blank", "noopener");
    return;
  }
  window.open(`https://map.naver.com/v5/search/${encoded}`, "_blank", "noopener");
}

export function openDirections(destination: MapDestination, preference: MapPreference = "NAVER") {
  const hasCoordinates = Number.isFinite(destination.latitude) && Number.isFinite(destination.longitude);
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  const destinationAddress = (destination.address || "").trim();

  if (preference === "NAVER" && hasCoordinates) {
    const params = new URLSearchParams({
      dlat: String(destination.latitude),
      dlng: String(destination.longitude),
      dname: destinationAddress || destination.name,
      appname: window.location.origin,
    });
    const routeUrl = `nmap://route/car?${params.toString()}`;
    if (isMobile) {
      window.location.href = routeUrl;
    } else {
      window.open(routeUrl, "_blank", "noopener");
    }
    return;
  }

  // 좌표가 없는 기존 현장은 네이버지도에서 현장 주소 자체를 검색한다.
  openMap(destinationAddress || destination.name, "NAVER");
}

