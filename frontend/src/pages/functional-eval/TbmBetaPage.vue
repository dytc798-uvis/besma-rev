<template>
  <div class="tbm-beta-page">
    <header class="tbm-beta-header">
      <h1>TBM(베타테스트)</h1>
      <p class="tbm-beta-subtitle">
        ERP 작업/안전일보의 표을 붙여넣어 다음날 TBM 일지 초안을 생성하고 출력까지 처리합니다.
        동일한 방식은 외부 베타테스터(참고용 계정 포함)도 동일하게 사용합니다.
      </p>
    </header>

    <section class="card tbm-guide">
      <h2>TBM Beta Guide</h2>
      <ol class="tbm-guide-list">
        <li>ERP 작업/안전일보에서 금일/명일 표를 복사해 붙여넣습니다.</li>
        <li>명일 섹션만 추출해 미리보기를 확인하고 행/내용을 점검합니다.</li>
        <li>위험성·대책은 규칙 기반으로 초안이 자동 생성되며, 행별로 직접 수정할 수 있습니다.</li>
        <li>행 추가/삭제, 중복 제거를 통해 최종 본문을 정리합니다.</li>
        <li>PDF/인쇄 버튼으로 출력물을 저장합니다.</li>
      </ol>
      <p class="tbm-guide-note">
        “어드민” 계정은 외부 검토용 공유 계정으로 메뉴 노출을 확인해 업무흐름 점검에 사용합니다.
      </p>
    </section>

    <section class="card">
      <label for="tbm-paste" class="tbm-label">ERP 붙여넣기</label>
      <textarea
        id="tbm-paste"
        v-model="rawInput"
        class="tbm-paste-input"
        rows="10"
        placeholder="ERP 표 또는 텍스트를 붙여넣으세요"
      />
      <div class="tbm-actions">
        <button type="button" class="tbm-btn tbm-btn--primary" @click="parseInput">파싱 미리보기</button>
        <button type="button" class="tbm-btn" :disabled="!parseResult" @click="applyRiskToAll">행 전체 자동 반영</button>
        <button type="button" class="tbm-btn" :disabled="draftRows.length === 0" @click="clearDraft">초기화</button>
      </div>
    </section>

    <section v-if="parseResult" class="card">
      <h2>TBM 미리보기</h2>
      <div class="tbm-meta-grid">
        <label>
          TBM일자
          <input v-model="nextDateInput" type="text" readonly />
        </label>
        <label>
          기준 출역일(ERP)
          <input v-model="sourceDateInput" type="text" readonly />
        </label>
        <label>
          현장명
          <input v-model="siteNameInput" type="text" />
        </label>
        <label>
          담당자
          <input v-model="managerInput" type="text" />
        </label>
        <label>
          작업장소
          <input v-model="workplaceInput" type="text" />
        </label>
      </div>

      <div class="tbm-meta-grid">
        <label>
          작업팀장 전달사항
          <textarea v-model="teamLeaderMessage" rows="2" />
        </label>
        <label class="tbm-check">
          <input v-model="removeDuplicateRows" type="checkbox" />
          중복 작업내용 제거
        </label>
      </div>

      <div class="tbm-meta-grid">
        <span class="tbm-count">총 {{ displayRows.length }}건</span>
        <button type="button" class="tbm-btn" :disabled="displayRows.length === 0" @click="addRow">행 추가</button>
      </div>

      <div v-if="displayRows.length === 0" class="tbm-empty">파싱 결과가 없습니다. ERP 텍스트에서 명일 작업 내용을 확인하세요.</div>

      <div v-for="(row, idx) in displayRows" :key="row.id" class="tbm-row">
        <div class="tbm-row-header">
          <span>{{ idx + 1 }}</span>
          <button type="button" class="tbm-btn tbm-btn--danger" @click="removeRow(idx)">삭제</button>
        </div>
        <div class="tbm-row-grid">
          <label>
            팀명
            <input v-model="row.teamName" type="text" />
          </label>
          <label>
            작업자
            <input v-model="row.workerName" type="text" />
          </label>
          <label class="tbm-row-description">
            작업내용
            <textarea v-model="row.workDescription" rows="3" />
          </label>
          <label class="tbm-row-risk">
            위험요인
            <textarea v-model="row.riskFactor" rows="3" />
          </label>
          <label class="tbm-row-measure">
            개선대책
            <textarea v-model="row.countermeasure" rows="3" />
          </label>
        </div>
        <button type="button" class="tbm-btn" @click="applyRisk(idx)">이 행 자동 추천</button>
      </div>
    </section>

    <section v-if="parseResult && displayRows.length > 0" class="card">
      <div class="no-print">
        <button type="button" class="tbm-btn tbm-btn--primary" @click="printNow">PDF/인쇄</button>
      </div>

      <div class="tbm-paper" id="tbm-paper">
        <h2>TBM 일지 출력 미리보기</h2>
        <div class="tbm-paper-meta">
          <div><strong>TBM일자:</strong> {{ nextDateInput || '-' }}</div>
          <div><strong>현장명:</strong> {{ siteNameInput || '-' }}</div>
          <div><strong>담당자:</strong> {{ managerInput || '-' }}</div>
          <div><strong>기준일(ERP 출역일):</strong> {{ sourceDateInput || '-' }}</div>
          <div><strong>작업장소:</strong> {{ workplaceInput || '-' }}</div>
        </div>

        <table class="tbm-paper-table">
          <thead>
            <tr>
              <th style="width: 8%">팀명</th>
              <th style="width: 10%">작업자</th>
              <th style="width: 20%">작업내용</th>
              <th style="width: 25%">위험요인</th>
              <th style="width: 25%">개선대책</th>
              <th style="width: 12%">작업장소</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in displayRows" :key="`print-${row.id}`">
              <td>{{ row.teamName || '-' }}</td>
              <td>{{ row.workerName || '-' }}</td>
              <td>{{ row.workDescription || '-' }}</td>
              <td>{{ row.riskFactor || '-' }}</td>
              <td>{{ row.countermeasure || '-' }}</td>
              <td>{{ workplaceInput || '-' }}</td>
            </tr>
          </tbody>
        </table>

        <div class="tbm-notice">
          <p><strong>서명지 안내:</strong> 도급사 TBM 서명지로 갈음 가능합니다.</p>
          <p><strong>보관 안내:</strong> 부현전기 TBM 또는 사진대지를 PDF/하드카피 중 하나로 보관합니다.</p>
          <p>
            부현전기 TBM일지는 전날 ERP 명일작업일보를 기준으로 작성합니다. 도급사 TBM 서명지는 당사 작업자가 포함되어야 하며
            부현전기 TBM일지와 동일 날짜이어야 합니다.
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { parseErpWorklogForNextDayTbm, type ParsedTbmSourceItem } from "@/utils/tbmErpPasteParser";

interface EditableTbmRow extends ParsedTbmSourceItem {
  id: number;
  riskFactor: string;
  countermeasure: string;
}

interface RiskRule {
  keywords: string[];
  risk: string;
  countermeasure: string;
}

const RAW_SAMPLE_HINT = "출역일: 2026-06-25\n현장명: [24025][1.대우건설] 청라C18BL 오피스텔\n담당자: 박명석\n금일 작업내용\n명일 작업내용\n";

const rules: RiskRule[] = [
  {
    keywords: ["앙카링", "창문", "드릴", "타공", "상부", "외부"],
    risk: "창문 상부 앙카링 작업 시 작업자 균형 상실 및 공구·부속 낙하로 추락/부상 위험이 있습니다.",
    countermeasure: "몸의 하중은 말비계 아래 또는 뒤쪽에 두고 상·하체 균형을 유지합니다. 드릴은 몸의 팔 힘으로만 조작하고 작업 상부는 작업반장 지시 하에 2인 이상으로 안전거리 유지",
  },
  {
    keywords: ["입선", "후렉시블", "케이블", "당김", "철거"],
    risk: "입선 및 후렉시블 취부 작업 중 케이블 당김, 협소 자세, 바닥 자재로 인한 근골격계 부담 및 전도 위험이 있습니다.",
    countermeasure: "작업 전 통로와 바닥 자재를 정리하고, 케이블 당김은 2인 이상 협업합니다. 허리 비틀림과 무리한 힘 사용을 금지합니다.",
  },
  {
    keywords: ["배관", "배관작업", "사다리", "작업발판"],
    risk: "배관 작업 중 사다리/말비계 사용 및 공구 작업에서 추락·낙하·전도 위험이 있습니다.",
    countermeasure: "작업발판을 안정적으로 설치하고 과도한 신체 신전은 금지합니다. 공구·자재는 고정 보관 후 이동 동선을 확보합니다.",
  },
  {
    keywords: ["임시전열", "전원", "전기", "누전", "케이블"],
    risk: "임시전열 설치 중 전원 연결 오류 또는 케이블 피복 손상으로 감전·화재 위험이 있습니다.",
    countermeasure: "작업 전 전원 차단과 누전차단기 상태를 확인합니다. 손상 케이블은 즉시 격리하고 노출 결선부는 봉인·보호 후 작업합니다.",
  },
];

const rawInput = ref(RAW_SAMPLE_HINT);
const parseResult = ref<ReturnType<typeof parseErpWorklogForNextDayTbm> | null>(null);
const draftRows = ref<EditableTbmRow[]>([]);
const sourceDateInput = ref("");
const nextDateInput = ref("");
const siteNameInput = ref("");
const managerInput = ref("");
const workplaceInput = ref("");
const teamLeaderMessage = ref("");
const removeDuplicateRows = ref(false);
let rowIdSeed = 1;

const rulesNormalized = rules.map((rule) => ({
  ...rule,
  keywordText: rule.keywords.join("|"),
}));

const getSuggestion = (workDescription: string) => {
  const target = workDescription.toLowerCase();
  const found = rulesNormalized.find((rule) => rule.keywords.some((keyword) => target.includes(keyword.toLowerCase())));
  if (found) {
    return {
      riskFactor: found.risk,
      countermeasure: found.countermeasure,
    };
  }
  return {
    riskFactor: "작업 특성에 따른 낙하, 협착, 전도 위험이 있습니다.",
    countermeasure: "작업반장 지시에 따라 작업 동선을 확보하고, 보호구 착용 및 안전거리 유지를 준수합니다.",
  };
};

const parseInput = () => {
  const parsed = parseErpWorklogForNextDayTbm(rawInput.value);
  parseResult.value = parsed;
  sourceDateInput.value = parsed.sourceDate ?? "";
  nextDateInput.value = parsed.nextDate ?? "";
  siteNameInput.value = parsed.siteName;
  managerInput.value = parsed.managerName;

  const rows = parsed.items
    .filter((item) => item.workDescription.trim().length > 0)
    .map((item) => {
      const suggested = getSuggestion(item.workDescription);
      return {
        ...item,
        id: rowIdSeed++,
        riskFactor: suggested.riskFactor,
        countermeasure: suggested.countermeasure,
      } as EditableTbmRow;
    });

  draftRows.value = rows;
};

const applyRiskToAll = () => {
  draftRows.value = draftRows.value.map((row) => {
    const suggestion = getSuggestion(row.workDescription);
    return {
      ...row,
      riskFactor: suggestion.riskFactor,
      countermeasure: suggestion.countermeasure,
    };
  });
};

const applyRisk = (index: number) => {
  const row = draftRows.value[index];
  if (!row) return;
  const suggestion = getSuggestion(row.workDescription);
  draftRows.value[index] = {
    ...row,
    riskFactor: suggestion.riskFactor,
    countermeasure: suggestion.countermeasure,
  };
};

const addRow = () => {
  draftRows.value.push({
    id: rowIdSeed++,
    teamName: "",
    workerName: "",
    workDescription: "",
    riskFactor: "",
    countermeasure: "",
  });
};

const removeRow = (index: number) => {
  draftRows.value.splice(index, 1);
};

const clearDraft = () => {
  parseResult.value = null;
  draftRows.value = [];
  sourceDateInput.value = "";
  nextDateInput.value = "";
  siteNameInput.value = "";
  managerInput.value = "";
  workplaceInput.value = "";
  teamLeaderMessage.value = "";
};

const dedupeByWorkDescription = (rows: EditableTbmRow[]) => {
  const seen = new Set<string>();
  const result: EditableTbmRow[] = [];
  for (const row of rows) {
    const key = row.workDescription.trim();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(row);
  }
  return result;
};

const displayRows = computed(() => {
  const rows = draftRows.value.filter((row) => row.workDescription.trim().length > 0);
  return removeDuplicateRows.value ? dedupeByWorkDescription(rows) : rows;
});

const printNow = () => {
  window.print();
};
</script>

<style scoped>
.tbm-beta-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
  display: grid;
  gap: 12px;
}

.tbm-beta-header,
.card {
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 12px;
  padding: 16px;
}

.tbm-beta-subtitle,
.tbm-guide-note,
.tbm-hint,
.tbm-count {
  color: #4b5563;
}

.tbm-guide-list,
.tbm-guide li,
.tbm-guide-note {
  margin: 0;
  padding-left: 18px;
}

.tbm-label {
  display: block;
  margin-bottom: 6px;
  font-weight: 700;
}

.tbm-paste-input {
  width: 100%;
  min-height: 190px;
  border: 1px solid #d8dde7;
  border-radius: 8px;
  padding: 10px;
}

.tbm-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.tbm-btn {
  padding: 8px 12px;
  border: 1px solid #d0d7e2;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.tbm-btn--primary {
  background: #0f172a;
  color: #fff;
  border-color: #0f172a;
}

.tbm-btn--danger {
  background: #fee2e2;
  border-color: #fecaca;
}

.tbm-meta-grid,
.tbm-row-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 10px;
}

.tbm-meta-grid .tbm-count {
  align-self: center;
}

.tbm-row-grid .tbm-row-description,
.tbm-row-grid .tbm-row-risk,
.tbm-row-grid .tbm-row-measure {
  grid-column: span 3;
}

.tbm-row {
  border: 1px solid #ecf0f4;
  border-radius: 10px;
  padding: 12px;
  margin-top: 10px;
  background: #f8fafc;
}

.tbm-row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

input,
textarea {
  width: 100%;
  border: 1px solid #d8dde7;
  border-radius: 6px;
  padding: 7px;
}

textarea {
  min-height: 60px;
}

.tbm-paper {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 14px;
  margin-top: 8px;
}

.tbm-paper-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  margin-top: 8px;
  font-size: 12px;
}

.tbm-paper-table th,
.tbm-paper-table td {
  border: 1px solid #d9e1eb;
  padding: 6px;
  vertical-align: top;
  word-break: break-word;
}

.tbm-paper-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.tbm-notice {
  margin-top: 10px;
  font-size: 12px;
  color: #334155;
  display: grid;
  gap: 4px;
}

.tbm-empty {
  border: 1px dashed #dbeafe;
  background: #eff6ff;
  padding: 12px;
  border-radius: 8px;
}

.tbm-check {
  grid-column: span 3;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

@media print {
  .no-print,
  .card:not(:has(.tbm-paper)),
  .tbm-beta-header,
  .tbm-guide,
  .tbm-paper {
    box-shadow: none !important;
  }

  .tbm-guide,
  .no-print,
  .tbm-actions,
  .tbm-empty,
  .tbm-meta-grid {
    display: none !important;
  }

  .tbm-paper {
    border: 0;
    padding: 0;
  }
}
</style>
