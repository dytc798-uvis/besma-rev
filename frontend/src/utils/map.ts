export type MapPreference = "NAVER" | "TMAP";

export function openMap(address: string, preference: MapPreference = "NAVER") {
  const encoded = encodeURIComponent((address || "").trim());
  if (!encoded) return;
  if (preference === "TMAP") {
    window.open(`https://apis.openapi.sk.com/tmap/app/routes?goalname=${encoded}`, "_blank", "noopener");
    return;
  }
  window.open(`https://map.naver.com/v5/search/${encoded}`, "_blank", "noopener");
}

