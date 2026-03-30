<template>
  <div class="info-page card">
    <h1 class="title">현장 정보 / 사용자 설정</h1>

    <section class="block">
      <h2>지도 앱 선택</h2>
      <label class="radio-row">
        <input type="radio" value="NAVER" v-model="mapPreference" @change="saveMapPreference" />
        네이버지도
      </label>
      <label class="radio-row">
        <input type="radio" value="TMAP" v-model="mapPreference" @change="saveMapPreference" />
        티맵
      </label>
    </section>

    <section class="block">
      <h2>내 현장</h2>
      <p class="site-name">{{ siteName || "-" }}</p>
      <p class="site-address">📍 {{ siteAddress || "주소 정보 없음" }}</p>
      <button type="button" class="primary large-btn" :disabled="!siteAddress" @click="openCurrentSiteMap">
        지도 보기
      </button>
    </section>

    <p v-if="message" class="message">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { openMap } from "@/utils/map";

const auth = useAuthStore();
const mapPreference = ref<"NAVER" | "TMAP">("NAVER");
const siteName = ref("");
const siteAddress = ref("");
const message = ref("");

async function loadSite() {
  const siteId = auth.effectiveSiteId;
  if (!siteId) return;
  const res = await api.get(`/sites/${siteId}`);
  siteName.value = res.data?.site_name ?? "";
  siteAddress.value = res.data?.address ?? "";
}

async function saveMapPreference() {
  message.value = "";
  const res = await api.patch("/users/me/map-preference", { map_preference: mapPreference.value });
  auth.user = res.data;
  message.value = "지도 앱 설정이 저장되었습니다.";
}

function openCurrentSiteMap() {
  if (!siteAddress.value) return;
  openMap(siteAddress.value, mapPreference.value);
}

onMounted(async () => {
  if (!auth.user) {
    await auth.loadMe();
  }
  mapPreference.value = auth.user?.map_preference === "TMAP" ? "TMAP" : "NAVER";
  await loadSite();
});
</script>

<style scoped>
.info-page {
  max-width: 640px;
}
.title {
  margin: 0 0 12px;
  font-size: 22px;
}
.block {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.block h2 {
  margin: 0 0 10px;
  font-size: 16px;
}
.radio-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}
.site-name {
  margin: 0 0 6px;
  font-weight: 700;
}
.site-address {
  margin: 0 0 10px;
  color: #475569;
}
.large-btn {
  width: 100%;
  min-height: 44px;
}
.message {
  margin-top: 8px;
  color: #2563eb;
  font-size: 13px;
}
</style>

