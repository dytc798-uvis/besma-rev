<template>
  <div class="tbm-beta-page">
    <header class="tbm-beta-header">
      <h1>TBM(?뺢퀣伊????裕??</h1>
      <p class="tbm-beta-subtitle">
        ERP ??얜??????깆쓧??怨뺢텠???釉먮듌??影?눫????援???읐??곗굚???껊???諭諭??リ옇????怨쀬Ŧ ?熬곣뫕??TBM(?熬곥굥??繹먮봾利멩뤆?쎛/TBM)????얜?????TBM ?貫?녽뇡????諛댁뎽??????瑜곸젧 ???怨쀫츊???琉얠돪??
      </p>
    </header>

    <section class="card tbm-guide">
      <h2>TBM Beta Guide</h2>
      <ol class="tbm-guide-list">
        <li><strong>1) Prepare source</strong>: Copy the ERP table area (golden day / next day, description, worker, team) from the work log.</li>
        <li><strong>2) Parse preview</strong>: Paste into this field and run parse preview. Confirm only <strong>next-day</strong> rows are extracted.</li>
        <li><strong>3) Check generated fields</strong>: Verify TBM date, site, manager and work description are auto-filled.</li>
        <li>
          <strong>4) Edit risk and measure</strong>: Risk and countermeasure are auto-suggested, and both fields can be modified manually for each row.
        </li>
        <li><strong>5) Adjust rows</strong>: Use duplicate-remove, add row, and delete row as needed.</li>
        <li><strong>6) Print</strong>: Create PDF or print output for archive use.</li>
      </ol>
      <p class="tbm-guide-note">
        The same flow must be used by all beta testers (including external testers). The <strong>"admin"</strong> reference account is also bound to this same TBM Beta flow for verification and cannot have a separate process.
      </p>
    </section>
    <section class="card">
      <label for="tbm-paste" class="tbm-label">ERP ??얜??????깆쓧??怨뺢텠 ?釉먮듌??影?끸뵛</label>
      <textarea
        id="tbm-paste"
        v-model="rawInput"
        class="tbm-paste-input"
        rows="10"
        placeholder="ERP ??? ??類ㅼ굥???곌랜踰딀쾮?????⑸츩?????裕?HTML ?釉먮듌??影?끸뵛"
      />
      <div class="tbm-actions">
        <button type="button" class="tbm-btn tbm-btn--primary" @click="parseInput">
          ?釉먮듌??影?끸뵛 ??怨몃뮔 ???堉?亦껋꼶梨?怨?돦??⒱뵛 ??諛댁뎽)
        </button>
        <button type="button" class="tbm-btn" :disabled="!parseResult" @click="applyRiskToAll">
          ?熬곥굥???븐슦逾???嶺??熬곣뫕?????吏?怨뺣뾼??
        </button>
        <button type="button" class="tbm-btn" :disabled="draftRows.length === 0" @click="clearDraft">
          ???놁졑?貫?껆뵳??        </button>
      </div>
      <p class="tbm-hint">
        嶺뚣끉裕????諛댁뎽 ????蹂㏓땴??苑력???뚮뜆??? ??戮곕뇶???겶???類ㅺ뎄??苑력???뚮뜆?®춯?TBM ????⑤챷紐드슖??꾩룇瑗???紐껊퉵??
      </p>
    </section>

    <section v-if="parseResult" class="card">
      <h2>TBM 미리보기</h2>
      <div class="tbm-meta-grid">
        <label>
          TBM??源놁겱
          <input v-model="nextDateInput" type="text" readonly />
        </label>
        <label>
          ??얜????リ옇?????怨쀫츋???
          <input v-model="sourceDateInput" type="text" readonly />
        </label>
        <label>
          ?熬곣뫗?®춯?          <input v-model="siteNameInput" type="text" />
        </label>
        <label>
          ??????          <input v-model="managerInput" type="text" />
        </label>
        <label>
          ??얜??????
          <input v-model="workplaceInput" type="text" />
        </label>
      </div>
      <div class="tbm-meta-grid">
        <label>
          ??얜???????熬곣뫀堉????
          <textarea v-model="teamLeaderMessage" rows="2" />
        </label>
        <label class="tbm-check">
          <input v-model="removeDuplicateRows" type="checkbox" />
          ???됰뎄 ??얜????怨몃뮔 繞벿살탮????蹂ㅽ깴 ????諛댁뎽
        </label>
      </div>
      <div class="tbm-meta-grid">
        <span class="tbm-count">총 {{ displayRows.length }}건</span>
        <button type="button" class="tbm-btn" :disabled="displayRows.length === 0" @click="addRow">
          ???怨뺣뼺?
        </button>
      </div>

      <div v-if="displayRows.length === 0" class="tbm-empty">
        ???堉??롪퍒?????????類ㅺ뎄??苑력???얜????怨몃뮔????怨룸????덈펲.
      </div>

      <div v-for="(row, idx) in displayRows" :key="row.id" class="tbm-row">
        <div class="tbm-row-header">
          <span>??{{ idx + 1 }}</span>
          <button type="button" class="tbm-btn tbm-btn--danger" @click="removeRow(idx)">
            ??????
          </button>
        </div>
        <div class="tbm-row-grid">
          <label>
            ??嶺?            <input v-model="row.teamName" type="text" />
          </label>
          <label>
            ??얜????            <input v-model="row.workerName" type="text" />
          </label>
          <label class="tbm-row-description">
            ??얜????怨몃뮔
            <textarea v-model="row.workDescription" rows="3" />
          </label>
          <label class="tbm-row-risk">
            ?熬곥굥???븐슦逾?
            <textarea v-model="row.riskFactor" rows="3" />
          </label>
          <label class="tbm-row-measure">
            ?띠룇裕뉓땻??嶺?            <textarea v-model="row.countermeasure" rows="3" />
          </label>
        </div>
        <button type="button" class="tbm-btn" @click="applyRisk(idx)">
          ?????熬곥굥???븐슦逾???嶺????吏?怨뺣뾼??
        </button>
      </div>
    </section>

    <section v-if="parseResult && displayRows.length > 0" class="card">
      <div class="no-print">
        <button type="button" class="tbm-btn tbm-btn--primary" @click="printNow">
          PDF/?筌뤾쑬????븐뻼???怨쀫츊??
        </button>
      </div>

      <div class="tbm-paper" id="tbm-paper">
        <h2>TBM ???(亦껋꼶梨?怨?돦??⒱뵛)</h2>
        <div class="tbm-paper-meta">
          <div><strong>TBM??源놁겱:</strong> {{ nextDateInput }}</div>
          <div><strong>?熬곣뫗?®춯?</strong> {{ siteNameInput || "-" }}</div>
          <div><strong>??????</strong> {{ managerInput || "-" }}</div>
          <div><strong>??얜??먪뼨轅명????怨쀫츋???:</strong> {{ sourceDateInput || "-" }}</div>
        </div>

        <table class="tbm-paper-table">
          <thead>
            <tr>
              <th style="width: 8%">팀명</th>
              <th style="width: 10%">작업자</th>
              <th style="width: 20%">??얜????怨몃뮔</th>
              <th style="width: 22%">위험요인</th>
              <th style="width: 22%">개선대책</th>
              <th style="width: 18%">?獄?????얜????怨몃뮔</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in displayRows" :key="`print-${row.id}`">
              <td>{{ row.teamName || "-" }}</td>
              <td>{{ row.workerName || "-" }}</td>
              <td>{{ row.workDescription || "-" }}</td>
              <td>{{ row.riskFactor || "-" }}</td>
              <td>{{ row.countermeasure || "-" }}</td>
              <td>{{ row.workDescription || "-" }}</td>
            </tr>
          </tbody>
        </table>

        <div class="tbm-notice">
          <p><strong>??얜??????</strong> {{ workplaceInput || "-" }}</p>
          <p><strong>??얜???????熬곣뫀堉????</strong> {{ teamLeaderMessage || "-" }}</p>
          <ol>
            <li>?熬곣뫕??TBM(?熬곥굥??繹먮봾利멩뤆?쎛/TBM)???熬곣몿??ERP 嶺뚮ㅏ援???얜????怨뺢텠???リ옇????怨쀬Ŧ ??얜?????? ?잙??뽨빳??嶺뚣볦굣?????リ옇?▽빳??돦?怨Β?嶺뚮ㅄ維?????얜?????TBM ?貫?녽뇡???낅퉵??</li>
            <li>?熬곥룊???TBM ??類ㅺ뎄嶺뚯솘????熬곥룊???TBM??????띠룆?????????곕????덈펲.</li>
            <li>?? ?熬곥룊???TBM ??類ㅺ뎄嶺뚯솘????裕??獄?亦???얜????? ?????琉우꽑?????? ?遊붋?熬곣뫗?덄뼨?TBM????? ???됰뎄????ル‘????リ옇?▽빳??怨룹꽑????紐껊퉵??</li>
            <li>?熬곥굥??繹먮봾利멩뤆?쎛 ?롪퍒????熬곥굥????熬곥굥由??遊붋?熬곣뫗?덄뼨?TBM????? ??壤??嶺뚯솘???PDF ???裕???濡リ덧?곸궠?얗?繞???濡る룎???곌랜????紐껊퉵??</li>
          </ol>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
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

const RAW_SAMPLE_HINT = `?怨쀫츋??? 2026-06-25
?熬곣뫗?®춯? [24025][1.????⑤슡??? 嶺??李?8BL ???덈룛???댟?
?????? ?꾩룆踰좑㎖??;

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

const rules: RiskRule[] = [
  {
    keywords: ["嶺뚢돦?ζ룇", "???異?, "???덉땋", "嶺뚢돦??", "???", "??μ쪠??, "?怨뺣???, "????, "??類싲뎅"],
    risk: "??ㅻ쾴??믨껀? 嶺뚢돦?ζ룇 ??? ???덉땋嶺???얜????????????우벟 嶺뚳퐢?삣ㅇ?????곗꽑 ????ㅻ쾹???? ??類싲뎅 ??ル‘踰???袁㏉돮??繞벿살탳?????용맪???怨뺣?????熬곥굥??,
    countermeasure: "?꾩룇瑗띈キ??嶺뚮ㅏ梨????瑜곥돡?? 嶺뚮씭큔?????熬곣뫁?????裕????덇국??????? ???沅???븐슦踰???瑜곷さ?β돦裕녶퐲?????ㅻ쾹??熬곣뫁夷???흮???類ｋ펲. ??얜??????? ???????얜??????⑤챿????㉱?洹먮뜆鍮???뽯┰??",
  },
  {
    keywords: ["???얩맖", "?熬곣뫁???類λ떆", "?꾩룄?ｈ땻?, "??댟?????, "?????", "?롪퍒???, "?獄?", "??怨몃쾳", "??⑤슡??],
    risk: "???얩맖 ???熬곣뫁???類λ떆 ????? ??얜???繞???댟??????獄?, ??얜?爰????얜??????? ?꾩룆???????뷴슖??筌뤿굝???잙???琉룹물?猷뼘??遊붋?????熬곣뫀利??熬곥굥??,
    countermeasure: "??얜????????夷?? ?꾩룆??????????筌먲퐘遊???겶? ???????獄? ??얜???? 2????怨대쭜 ??얜????類ｋ펲. ??얜???繞????용뉴 ?????源녿닁????????????????ル?????겶???얜??????????얜???????? ???夷???⑤객臾???筌먦끉逾??類ｋ펲.",
  },
  {
    keywords: ["?꾩룄??", "???逾??, "??ㅻ???, "???濡㏓뎨?, "嶺뚮씭큔????, "??얜??쒐뛾?녿츎??],
    risk: "??? ???裕??뺢퀣?⑴뙼??꾩룄?? ??얜???繞????濡㏓뎨??룸챷異????????? ??ㅻ??????? ????????????λ닔???????怨뺣???ъ????곕┃鸚?熬곣뫀利??熬곥굥??,
    countermeasure: "嶺뚮씭큔???????裕???얜??쒐뛾?녿츎??????깆젧??⑤챷紐드슖????노뭵???겶? ??? ??얜?????嶺뚮ㅏ梨????λ닑????우벟 嶺뚮쵐?? ???낅츎?? ??ㅻ???? ?????????곕┃??? ???낆┣???筌먲퐘遊???겶? ???????夷???筌먲퐢沅??????얜????類ｋ펲.",
  },
  {
    keywords: ["?熬곣뫖?", "?熬곥룗??, "?熬곣뫗??, "??댟?????, "?熬?", "??怨뺢텢", "?熬곣뫖六?熬곣뫖?", "?熬곣뫖六??熬곣뫖?", "?熬곣뫗??],
    risk: "?熬곣뫖六?熬곣뫖? ???노뭵 繞??熬곣뫗????⑤슡?? ??댟???????怨뺢텢 ???留? ?熬곣뫗?덄춯?노??誘ㅻЬ?亦껋꼶梨??筌뤾쑴紐드슖??筌뤿굝由??띠룆흮??????븐슦???熬곥굥??,
    countermeasure: "??얜??????熬곣뫗??嶺뚢뼰維??????? ?熬곣뫗?덄춯?노??誘ㅻЬ???얜Ŧ吏??⑤객臾???筌먦끉逾??類ｋ펲. ???留????댟?????? ?????? ??袁ぢ? ?롪퍒?ｈ땻臾뚭껀????筌뤾쑵???? ???낆┣???브퀗????????얜????類ｋ펲.",
  },
  {
    keywords: ["??諭??, "??諭?붺뼨?, "???덉넮??, "?????, "?リ옇???, "??μ쪠??],
    risk: "??ㅻ????브퀗???繞???얜?????踰???λ닔??? ?熬곥룗?????곕┃, ???곕┃?????熬곣뫀利??熬곥굥????꾩룇裕뉑틦???????덈펲",
    countermeasure: "??μ쪠????釉띾쐞?????ㅻ????嶺뚯빖留????흮????겶? ????繞??熬곥룗??????곕┃??嶺뚮씭留?뵳??熬곥굥???꾩룇瑗??룹춹?猷멸땁 ?곌랜????? 嶺뚯솘??筌먐삳┰?? ??얜?????뚮봾????裕???얜∥???????????곕뻣??類ｋ펲.",
  },
];

function defaultRisk(workDescription: string) {
  const target = workDescription.toLowerCase();
  const rule = rules.find((item) => item.keywords.some((keyword) => target.includes(keyword)));
  if (rule) {
    return {
      risk: rule.risk,
      countermeasure: rule.countermeasure,
    };
  }
  return {
    risk:
      "??얜???繞??怨뺣??? ??源녿엮, ???곕┃?????잙???琉룹물?猷뼘??遊붋?????곌랜踰뤻뜮? ???깆쓧?熬곥굥????꾩룇裕뉑틦???????깅さ亦껋깢????熬곣뫗?®솻??熬곥굥??繹먮봾利멩뤆?쎛 ?リ옇????怨쀬Ŧ ?????????熬곣뫗???紐껊퉵??",
    countermeasure: "??얜??쒐뛾?녾섭??嶺뚯솘???戮?뱺 ??⑤벡逾??곌랜???묐쨨?嶺뚢뼰維??????얜??????뉙맖?????琉룹물????겶? ??얜?????戮?맋???釉뚯뫅????リ옇????怨쀬Ŧ ?筌?鸚???????嶺뚯쉳?듸쭛??類ｋ펲.",
  };
}

function normalizeText(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

const parsedSourceRows = computed(() => {
  if (!parseResult.value) return [];
  if (!removeDuplicateRows.value) return parseResult.value.items;
  const seen = new Set<string>();
  const next: ParsedTbmSourceItem[] = [];
  for (const item of parseResult.value.items) {
    const key = normalizeText(item.workDescription);
    if (seen.has(key)) continue;
    seen.add(key);
    next.push(item);
  }
  return next;
});

const displayRows = computed<EditableTbmRow[]>(() =>
  draftRows.value.map((row) => ({ ...row, id: row.id })) as EditableTbmRow[],
);

watch(
  [parsedSourceRows, removeDuplicateRows],
  () => {
    draftRows.value = parsedSourceRows.value.map((row) => {
      const existing = draftRows.value.find((current) => current.workDescription === row.workDescription);
      const predicted = defaultRisk(row.workDescription);
      if (existing) {
        return {
          ...existing,
          teamName: row.teamName || existing.teamName,
          workerName: row.workerName || existing.workerName,
          workDescription: row.workDescription || existing.workDescription,
        };
      }
      return {
        id: rowIdSeed++,
        teamName: row.teamName,
        workerName: row.workerName,
        workDescription: row.workDescription,
        riskFactor: existing?.riskFactor || predicted.risk,
        countermeasure: existing?.countermeasure || predicted.countermeasure,
      };
    });
  },
  { immediate: true },
);

function parseInput() {
  parseResult.value = parseErpWorklogForNextDayTbm(rawInput.value);
  sourceDateInput.value = parseResult.value.sourceDate ?? "";
  nextDateInput.value = parseResult.value.nextDate ?? "";
  siteNameInput.value = parseResult.value.siteName ?? "";
  managerInput.value = parseResult.value.managerName ?? "";
  workplaceInput.value = parseResult.value.siteName ?? "";
  rowIdSeed = 1;
  draftRows.value = [];
  for (const row of parseResult.value.items) {
    const predicted = defaultRisk(row.workDescription);
    draftRows.value.push({
      id: rowIdSeed++,
      teamName: row.teamName,
      workerName: row.workerName,
      workDescription: row.workDescription,
      riskFactor: predicted.risk,
      countermeasure: predicted.countermeasure,
    });
  }
}

function applyRisk(index: number) {
  const row = draftRows.value[index];
  if (!row) return;
  const suggestion = defaultRisk(row.workDescription);
  row.riskFactor = suggestion.risk;
  row.countermeasure = suggestion.countermeasure;
}

function applyRiskToAll() {
  for (const row of draftRows.value) {
    const suggestion = defaultRisk(row.workDescription);
    row.riskFactor = suggestion.risk;
    row.countermeasure = suggestion.countermeasure;
  }
}

function addRow() {
  draftRows.value.push({
    id: rowIdSeed++,
    teamName: "",
    workerName: "",
    workDescription: "",
    riskFactor: "",
    countermeasure: "",
  });
}

function removeRow(index: number) {
  draftRows.value.splice(index, 1);
}

function clearDraft() {
  rawInput.value = "";
  parseResult.value = null;
  draftRows.value = [];
  sourceDateInput.value = "";
  nextDateInput.value = "";
  siteNameInput.value = "";
  managerInput.value = "";
  workplaceInput.value = "";
  teamLeaderMessage.value = "";
}

function printNow() {
  window.print();
}
</script>

<style scoped>
.tbm-beta-page {
  display: grid;
  gap: 12px;
}

.tbm-beta-header h1 {
  margin: 0 0 4px;
  font-size: 24px;
}

.tbm-beta-subtitle {
  margin: 0;
  color: #475569;
  font-size: 14px;
}

.tbm-guide {
  background: #f8fafc;
  border-color: #dbeafe;
}

.tbm-guide-list {
  margin: 8px 0 0;
  padding-left: 20px;
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
}

.tbm-guide-list li {
  line-height: 1.5;
}

.tbm-guide-note {
  margin: 10px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.card {
  background: #fff;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  padding: 12px;
}

.tbm-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.tbm-paste-input {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px;
}

.tbm-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tbm-btn {
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #0f172a;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.tbm-btn--primary {
  background: linear-gradient(90deg, #ea580c, #fb923c);
  border-color: #fb923c;
  color: #fff;
}

.tbm-btn--danger {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #b91c1c;
}

.tbm-btn[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

.tbm-hint {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 12px;
}

.tbm-meta-grid {
  margin-top: 10px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}

.tbm-meta-grid label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tbm-meta-grid input,
.tbm-meta-grid textarea,
.tbm-row-grid input,
.tbm-row-grid textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 7px 8px;
  font-size: 13px;
}

.tbm-row-grid {
  margin-top: 10px;
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.tbm-row {
  border: 1px solid #f1f5f9;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px;
  margin-top: 10px;
}

.tbm-row-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tbm-row-description {
  grid-column: 1 / -1;
}

.tbm-row-risk {
  grid-column: 1 / -1;
}

.tbm-row-measure {
  grid-column: 1 / -1;
}

.tbm-empty {
  margin-top: 8px;
  color: #64748b;
}

.tbm-count {
  align-self: center;
  color: #475569;
  font-size: 14px;
}

.tbm-check {
  flex-direction: row !important;
  align-items: center;
  gap: 6px;
}

.tbm-check input {
  width: 16px;
  height: 16px;
}

.tbm-paper {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 12px;
}

.tbm-paper h2 {
  margin: 0 0 10px;
}

.tbm-paper-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 6px 12px;
  margin-bottom: 12px;
  color: #334155;
}

.tbm-paper-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  table-layout: fixed;
}

.tbm-paper-table th,
.tbm-paper-table td {
  border: 1px solid #e2e8f0;
  padding: 6px;
  vertical-align: top;
  text-align: left;
  line-height: 1.35;
  white-space: pre-wrap;
}

.tbm-paper-table th {
  background: #f8fafc;
}

.tbm-notice {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #cbd5e1;
  color: #334155;
  font-size: 12px;
}

.tbm-notice ol {
  padding-left: 18px;
  margin: 8px 0 0;
}

.tbm-notice li {
  margin-top: 4px;
}

@media print {
  :global(body) {
    background: #fff;
  }
  .card {
    border: none;
    padding: 0;
    margin: 0;
  }
  .tbm-btn,
  .tbm-actions,
  .no-print,
  .tbm-row,
  .tbm-row .tbm-btn,
  .tbm-beta-header,
  .tbm-hint,
  .tbm-meta-grid,
  .tbm-empty,
  .tbm-beta-subtitle {
    display: none !important;
  }

  .tbm-paper {
    border: none;
    border-radius: 0;
    padding: 0;
  }

  .tbm-paper-table th,
  .tbm-paper-table td {
    font-size: 11px;
    line-height: 1.4;
  }
}

@media (max-width: 768px) {
  .tbm-row-grid {
    grid-template-columns: 1fr;
  }

  .tbm-paper-table {
    font-size: 11px;
  }
}
</style>

