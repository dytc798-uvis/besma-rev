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

function googleDirectionsUrl(destination: MapDestination) {
  const target = destination.latitude != null && destination.longitude != null
    ? `${destination.latitude},${destination.longitude}`
    : [destination.name, destination.address].filter(Boolean).join(" ");
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(target)}&travelmode=driving&dir_action=navigate`;
}

export function openDirections(destination: MapDestination, preference: MapPreference = "NAVER") {
  const hasCoordinates = Number.isFinite(destination.latitude) && Number.isFinite(destination.longitude);
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

  if (preference === "NAVER" && isMobile && hasCoordinates) {
    const params = new URLSearchParams({
      dlat: String(destination.latitude),
      dlng: String(destination.longitude),
      dname: destination.name,
      appname: window.location.origin,
    });
    window.location.href = `nmap://route/car?${params.toString()}`;
    return;
  }

  // 주소만 있는 현장도 출발지를 현재 위치로 둔 길찾기 화면이 반드시 열리도록
  // 범용 Maps URL을 사용한다. 앱이 없으면 동일한 길찾기가 웹에서 열린다.
  window.open(googleDirectionsUrl(destination), "_blank", "noopener");
}

