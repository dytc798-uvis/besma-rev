<template>
  <section class="ledger-page">
    <header class="hero">
      <div>
        <p class="eyebrow">{{ pageEyebrow }}</p>
        <h2>{{ pageTitle }}</h2>
        <p>{{ pageDescription }}</p>
      </div>
      <div class="session-note">로그인 세션 7일 유지</div>
    </header>

    <div class="tabs" role="tablist">
      <button :class="{ active: tab === 'card' }" @click="switchTab('card')">🧾 법인카드</button>
      <button :class="{ active: tab === 'vehicle' }" @click="switchTab('vehicle')">🚙 차량 운행</button>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <template v-if="tab === 'vehicle'">
      <div class="summary-card">
        <div>
          <span>차량</span>
          <strong>{{ vehicle.vehicle_name || "투싼" }} · {{ vehicle.plate_number || "181하8339" }}</strong>
        </div>
        <div>
          <span>운전자</span>
          <strong>{{ vehicle.drivers.join(" · ") || "정상익 · 박영선" }}</strong>
        </div>
        <button class="download" @click="downloadExcel('vehicle')">운행기록부 다운로드</button>
      </div>
      <details class="driver-manager">
        <summary>운전자 관리 (최대 4명)</summary>
        <div class="driver-slots">
          <input v-for="index in 4" :key="index" v-model="driverDraft[index - 1]" :placeholder="`운전자 ${index}`" />
          <button class="confirm" @click="saveDrivers">운전자 저장</button>
        </div>
      </details>

      <form class="capture-card" @submit.prevent="submitVehicle">
        <h3>계기판 촬영 및 운행 등록</h3>
        <label class="photo-picker">
          <input
            ref="vehiclePhotoInput"
            type="file"
            accept="image/*"
            capture="environment"
            required
            @change="vehiclePhoto = fileFromEvent($event)"
          />
          <b>{{ vehiclePhoto ? vehiclePhoto.name : "계기판 사진 촬영 / 선택" }}</b>
          <span>투싼 계기판 맨 아래의 누적 주행거리(ODO)가 선명하게 보이도록 촬영하세요.</span>
        </label>
        <div class="form-grid">
          <label>운행일<input v-model="vehicleForm.driven_on" type="date" required /></label>
          <label>
            운전자
            <select v-model="vehicleForm.driver_name" required>
              <option value="" disabled>선택</option>
              <option v-for="driver in vehicle.drivers" :key="driver" :value="driver">{{ driver }}</option>
            </select>
          </label>
          <label>누적 km (선택)<input v-model.number="vehicleForm.odometer_km" type="number" min="0" inputmode="numeric" /></label>
          <label>주행 km (선택)<input v-model.number="vehicleForm.trip_km" type="number" min="0" step="0.1" inputmode="decimal" /></label>
          <label class="wide">방문지·업무 목적<input v-model="vehicleForm.purpose" maxlength="500" placeholder="예: 청라 C18 현장 점검" /></label>
        </div>
        <button class="primary" :disabled="submitting || !vehiclePhoto">{{ submitting ? "저장 중…" : "사진과 운행기록 저장" }}</button>
        <p class="hint">{{ visionHint }}</p>
      </form>

      <div class="records">
        <div class="records-heading"><h3>운행기록</h3><button @click="loadData">새로고침</button></div>
        <p v-if="!vehicleLogs.length" class="empty">아직 등록된 운행기록이 없습니다.</p>
        <article v-for="row in vehicleLogs" :key="row.id" class="record">
          <div class="record-title">
            <strong>{{ row.driven_on }} · {{ row.driver_name }}</strong>
            <span :class="statusClass(row.extraction_status)">{{ statusLabel(row.extraction_status) }}</span>
          </div>
          <div class="form-grid compact">
            <label>운행일<input v-model="row.driven_on" type="date" /></label>
            <label>
              운전자
              <select v-model="row.driver_name"><option v-for="driver in vehicle.drivers" :key="driver" :value="driver">{{ driver }}</option></select>
            </label>
            <label>누적 km<input v-model.number="row.odometer_km" type="number" min="0" /></label>
            <label>주행 km<input v-model.number="row.trip_km" type="number" min="0" step="0.1" /></label>
            <label class="wide">방문지·업무 목적<input v-model="row.purpose" /></label>
          </div>
          <button class="confirm" @click="saveVehicleReview(row)">수정값 확인·확정</button>
        </article>
      </div>
    </template>

    <template v-else>
      <div class="summary-card card-summary">
        <div>
          <span>처리 방식</span>
          <strong>사진 보존 → 자동/수동 추출 → 사용자 확정</strong>
        </div>
        <button class="download" @click="downloadExcel('card')">법인카드 정산서 다운로드</button>
      </div>

      <form class="capture-card" @submit.prevent="submitCard">
        <h3>영수증 촬영 및 사용내역 등록</h3>
        <label class="photo-picker">
          <input
            ref="receiptInput"
            type="file"
            accept="image/*"
            capture="environment"
            required
            @change="receiptPhoto = fileFromEvent($event)"
          />
          <b>{{ receiptPhoto ? receiptPhoto.name : "영수증 사진 촬영 / 선택" }}</b>
          <span>승인일시, 가맹점, 금액, 카드번호 일부가 보이도록 촬영하세요.</span>
        </label>
        <div class="form-grid">
          <label>사용일시 (선택)<input v-model="cardForm.used_at" type="datetime-local" /></label>
          <label>사용처 (선택)<input v-model="cardForm.merchant" /></label>
          <label>금액 (선택)<input v-model.number="cardForm.amount" type="number" min="0" inputmode="numeric" /></label>
          <label>카드 끝 4자리 (선택)<input v-model="cardForm.card_last4" inputmode="numeric" maxlength="4" /></label>
          <label>현장명 (선택)<input v-model="cardForm.site_name" /></label>
          <label>내용 (선택)<input v-model="cardForm.description" placeholder="예: 주유비, 중식비" /></label>
        </div>
        <button class="primary" :disabled="submitting || !receiptPhoto">{{ submitting ? "저장 중…" : "사진과 사용내역 저장" }}</button>
        <p class="hint">{{ visionHint }}</p>
      </form>

      <div class="records">
        <div class="records-heading"><h3>법인카드 사용내역</h3><button @click="loadData">새로고침</button></div>
        <p v-if="!cardExpenses.length" class="empty">아직 등록된 영수증이 없습니다.</p>
        <article v-for="row in cardExpenses" :key="row.id" class="record">
          <div class="record-title">
            <strong>{{ formatUsedAt(row.used_at) }} · {{ row.merchant || "사용처 미확인" }}</strong>
            <span :class="statusClass(row.extraction_status)">{{ statusLabel(row.extraction_status) }}</span>
          </div>
          <div class="form-grid compact">
            <label>사용일시<input v-model="row.used_at" type="datetime-local" /></label>
            <label>사용처<input v-model="row.merchant" /></label>
            <label>금액<input v-model.number="row.amount" type="number" min="0" /></label>
            <label>카드 끝 4자리<input v-model="row.card_last4" maxlength="4" /></label>
            <label>현장명<input v-model="row.site_name" /></label>
            <label>내용<input v-model="row.description" /></label>
          </div>
          <button class="confirm" @click="saveCardReview(row)">수정값 확인·확정</button>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";

type Tab = "vehicle" | "card";
interface VehicleInfo {
  id?: number;
  vehicle_name: string;
  plate_number: string;
  department: string;
  drivers: string[];
  max_drivers?: number;
}
interface VehicleLog {
  id: number;
  driven_on: string;
  driver_name: string;
  use_type: string;
  odometer_km: number | null;
  trip_km: number | null;
  purpose: string | null;
  extraction_status: string;
}
interface CardExpense {
  id: number;
  used_at: string | null;
  site_name: string | null;
  merchant: string | null;
  amount: number | null;
  description: string | null;
  card_last4: string | null;
  note: string | null;
  extraction_status: string;
}

const today = new Date().toISOString().slice(0, 10);
const route = useRoute();
const router = useRouter();
const routeTab = (): Tab => route.meta.ledgerTab === "vehicle" ? "vehicle" : "card";
const tab = ref<Tab>(routeTab());
const pageTitle = computed(() => tab.value === "card" ? "법인카드 사용내역" : "차량 운행기록부");
const pageEyebrow = computed(() => tab.value === "card" ? "영수증 모바일 촬영" : "계기판 모바일 촬영");
const pageDescription = computed(() =>
  tab.value === "card"
    ? "영수증 원본을 보존하고 사용일시·사용처·금액·카드번호 일부를 확인한 뒤 회사 양식으로 내려받습니다."
    : "계기판 사진 원본을 보존하고 누적 주행거리와 운행정보를 확인한 뒤 운행기록부로 내려받습니다.",
);
const vehicle = reactive<VehicleInfo>({
  vehicle_name: "투싼",
  plate_number: "181하8339",
  department: "안전보건실",
  drivers: ["정상익", "박영선"],
});
const vehicleLogs = ref<VehicleLog[]>([]);
const cardExpenses = ref<CardExpense[]>([]);
const driverDraft = ref<string[]>(["정상익", "박영선", "", ""]);
const visionEnabled = ref(false);
const submitting = ref(false);
const notice = ref("");
const error = ref("");
const vehiclePhoto = ref<File | null>(null);
const receiptPhoto = ref<File | null>(null);
const vehiclePhotoInput = ref<HTMLInputElement | null>(null);
const receiptInput = ref<HTMLInputElement | null>(null);
const vehicleForm = reactive({ driven_on: today, driver_name: "", odometer_km: null as number | null, trip_km: null as number | null, purpose: "" });
const cardForm = reactive({ used_at: "", site_name: "", merchant: "", amount: null as number | null, description: "", card_last4: "" });
const visionHint = computed(() =>
  visionEnabled.value
    ? "사진 인식값은 자동으로 채워지지만 반드시 목록에서 확인·확정해 주세요."
    : "현재 자동 인식 API가 연결되지 않아 사진 보존 후 수동 확인 방식으로 동작합니다.",
);

onMounted(loadData);
watch(() => route.meta.ledgerTab, () => {
  tab.value = routeTab();
});

function switchTab(next: Tab) {
  router.push({ name: next === "card" ? "hq-safe-card-expenses" : "hq-safe-vehicle-logs" });
}

async function loadData() {
  error.value = "";
  try {
    const { data } = await api.get("/safety-ledgers/bootstrap");
    Object.assign(vehicle, data.vehicle || {});
    driverDraft.value = [...vehicle.drivers, "", "", "", ""].slice(0, 4);
    vehicleLogs.value = Array.isArray(data.vehicle_logs) ? data.vehicle_logs : [];
    cardExpenses.value = (Array.isArray(data.card_expenses) ? data.card_expenses : []).map(toEditableCard);
    visionEnabled.value = data.vision_enabled === true;
    if (!vehicleForm.driver_name && vehicle.drivers.length) vehicleForm.driver_name = vehicle.drivers[0];
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "자료를 불러오지 못했습니다.";
  }
}

function fileFromEvent(event: Event): File | null {
  return (event.target as HTMLInputElement).files?.[0] || null;
}

function appendIf(form: FormData, key: string, value: unknown) {
  if (value !== null && value !== undefined && String(value).trim() !== "") form.append(key, String(value));
}

async function submitVehicle() {
  if (!vehiclePhoto.value) return;
  const form = new FormData();
  form.append("photo", vehiclePhoto.value);
  form.append("driven_on", vehicleForm.driven_on);
  form.append("driver_name", vehicleForm.driver_name);
  appendIf(form, "odometer_km", vehicleForm.odometer_km);
  appendIf(form, "trip_km", vehicleForm.trip_km);
  appendIf(form, "purpose", vehicleForm.purpose);
  await submitForm("/safety-ledgers/vehicle-logs", form, "운행기록을 저장했습니다.");
  vehiclePhoto.value = null;
  if (vehiclePhotoInput.value) vehiclePhotoInput.value.value = "";
}

async function submitCard() {
  if (!receiptPhoto.value) return;
  const form = new FormData();
  form.append("receipt", receiptPhoto.value);
  for (const [key, value] of Object.entries(cardForm)) appendIf(form, key, value);
  await submitForm("/safety-ledgers/card-expenses", form, "영수증과 사용내역을 저장했습니다.");
  receiptPhoto.value = null;
  if (receiptInput.value) receiptInput.value.value = "";
}

async function submitForm(url: string, form: FormData, success: string) {
  submitting.value = true;
  notice.value = "";
  error.value = "";
  try {
    await api.post(url, form, { timeout: 90_000 });
    notice.value = success;
    await loadData();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "저장하지 못했습니다.";
  } finally {
    submitting.value = false;
  }
}

async function saveVehicleReview(row: VehicleLog) {
  await saveReview(`/safety-ledgers/vehicle-logs/${row.id}`, { ...row, confirm: true }, "운행기록을 확정했습니다.");
}

async function saveDrivers() {
  const names = driverDraft.value.map((name) => name.trim()).filter(Boolean);
  notice.value = "";
  error.value = "";
  try {
    await api.put(`/safety-ledgers/vehicles/${vehicle.id}/drivers`, { driver_names: names });
    notice.value = "운전자 목록을 저장했습니다.";
    await loadData();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "운전자 목록을 저장하지 못했습니다.";
  }
}

async function saveCardReview(row: CardExpense) {
  await saveReview(`/safety-ledgers/card-expenses/${row.id}`, { ...row, used_at: row.used_at || null, confirm: true }, "법인카드 내역을 확정했습니다.");
}

async function saveReview(url: string, payload: object, success: string) {
  notice.value = "";
  error.value = "";
  try {
    await api.patch(url, payload);
    notice.value = success;
    await loadData();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "확정하지 못했습니다.";
  }
}

function toEditableCard(row: CardExpense): CardExpense {
  return { ...row, used_at: row.used_at ? row.used_at.slice(0, 16) : null };
}

function formatUsedAt(value: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "일시 미확인";
}

function statusLabel(value: string) {
  return ({ CONFIRMED: "확정", AUTO_EXTRACTED: "자동 추출·검토 필요", NEEDS_REVIEW: "수동 입력 필요", EXTRACTION_FAILED: "인식 실패·검토 필요" } as Record<string, string>)[value] || value;
}

function statusClass(value: string) {
  return value === "CONFIRMED" ? "status confirmed" : "status pending";
}

async function downloadExcel(kind: "vehicle" | "card") {
  const filename = kind === "vehicle" ? "안전실_업무용승용차 운행기록부.xlsx" : "안전실_법인카드 정산서.xlsx";
  const { data } = await api.get(`/safety-ledgers/exports/${kind}`, { responseType: "blob", timeout: 90_000 });
  const href = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(href);
}
</script>

<style scoped>
.ledger-page { max-width: 1100px; margin: 0 auto; color: #142033; }
.hero { display: flex; justify-content: space-between; gap: 24px; padding: 26px; border-radius: 20px; background: linear-gradient(135deg, #0b3b56, #0f6b6d); color: white; box-shadow: 0 16px 36px rgba(15, 62, 83, .18); }
.hero h2 { margin: 4px 0 8px; font-size: clamp(25px, 4vw, 38px); }
.hero p { margin: 0; line-height: 1.55; }
.eyebrow { color: #a7f3d0; font-weight: 800; }
.session-note { align-self: flex-start; white-space: nowrap; padding: 8px 12px; border: 1px solid rgba(255,255,255,.3); border-radius: 999px; background: rgba(255,255,255,.1); font-weight: 700; }
.tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0; }
.tabs button { padding: 14px; border: 1px solid #cbd5e1; border-radius: 14px; background: white; font-weight: 800; font-size: 16px; cursor: pointer; }
.tabs button.active { border-color: #0f6b6d; background: #e8f7f4; color: #0f5c5e; box-shadow: inset 0 0 0 1px #0f6b6d; }
.summary-card, .capture-card, .records { margin-bottom: 18px; padding: 20px; border: 1px solid #dce5ea; border-radius: 18px; background: white; box-shadow: 0 8px 25px rgba(31, 53, 71, .06); }
.driver-manager { margin: -6px 0 18px; padding: 14px 18px; border: 1px solid #dce5ea; border-radius: 14px; background: white; }
.driver-manager summary { color: #0f5c5e; font-weight: 800; cursor: pointer; }
.driver-slots { display: grid; grid-template-columns: repeat(4, 1fr) auto; gap: 8px; margin-top: 12px; }
.driver-slots .confirm { margin-top: 0; }
.summary-card { display: flex; align-items: center; gap: 28px; }
.summary-card div { display: grid; gap: 3px; }
.summary-card span, .hint { color: #657383; font-size: 13px; }
.download { margin-left: auto; padding: 10px 14px; border: 0; border-radius: 10px; color: white; background: #0f6b6d; font-weight: 800; cursor: pointer; }
.capture-card h3, .records h3 { margin: 0 0 16px; }
.photo-picker { display: grid; place-items: center; gap: 6px; min-height: 135px; margin-bottom: 18px; padding: 20px; border: 2px dashed #4f8790; border-radius: 15px; text-align: center; background: #f3fbfa; cursor: pointer; }
.photo-picker input { position: absolute; opacity: 0; width: 1px; height: 1px; }
.photo-picker b { color: #0f5c5e; font-size: 18px; }
.photo-picker span { color: #64748b; font-size: 14px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.form-grid label { display: grid; gap: 6px; color: #334155; font-size: 13px; font-weight: 700; }
.form-grid .wide { grid-column: 1 / -1; }
input, select { box-sizing: border-box; width: 100%; min-height: 44px; padding: 10px 11px; border: 1px solid #cbd5e1; border-radius: 10px; background: white; color: #172033; font: inherit; }
.primary, .confirm { margin-top: 16px; padding: 12px 18px; border: 0; border-radius: 11px; background: #e36b2c; color: white; font-weight: 800; cursor: pointer; }
.primary:disabled { opacity: .55; cursor: wait; }
.notice, .error { margin-bottom: 14px; padding: 12px 15px; border-radius: 10px; font-weight: 700; }
.notice { background: #e8f7f0; color: #176b4b; }
.error { background: #fff0ed; color: #a43d2d; }
.records-heading { display: flex; align-items: center; justify-content: space-between; }
.records-heading button { border: 0; background: transparent; color: #0f6b6d; font-weight: 800; cursor: pointer; }
.record { padding: 16px 0; border-top: 1px solid #e7edf0; }
.record-title { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.status { padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 800; }
.status.confirmed { background: #dcfce7; color: #166534; }
.status.pending { background: #fff3cd; color: #8a5a00; }
.compact { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.confirm { background: #334155; }
.empty { color: #64748b; text-align: center; padding: 24px; }

@media (max-width: 720px) {
  .ledger-page { padding: 0 4px 20px; }
  .hero { display: block; padding: 20px; border-radius: 16px; }
  .session-note { display: inline-block; margin-top: 14px; }
  .tabs { position: sticky; top: 0; z-index: 4; padding: 8px 0; background: #f7fafb; }
  .tabs button { min-height: 52px; }
  .summary-card { align-items: stretch; flex-direction: column; gap: 12px; }
  .download { min-height: 48px; margin-left: 0; }
  .form-grid, .compact { grid-template-columns: 1fr; }
  .driver-slots { grid-template-columns: 1fr 1fr; }
  .form-grid .wide { grid-column: auto; }
  .record-title { align-items: flex-start; flex-direction: column; }
  .photo-picker { min-height: 180px; padding: 24px 16px; }
  input, select { min-height: 50px; font-size: 16px; }
  .primary { width: 100%; min-height: 54px; font-size: 16px; }
}
</style>
