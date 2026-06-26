<template>
  <div class="tbm-beta-page">
    <header class="tbm-beta-header">
      <h1>TBM(甕곗쥚????뮞??</h1>
      <p class="tbm-beta-subtitle">
        ERP ?臾믩씜/??됱읈??곕궖???븐늿肉?節딇????구??댟?우삂??낃땀??뱀뱽 疫꿸퀣???곗쨮 ?袁⑷텢 TBM(?袁る퓮?源딅즸揶쎛/TBM)???臾믩씜 ??TBM ?λ뜆釉????밴쉐??????륁젟 獄??곗뮆???뤾쉭??
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
      <label for="tbm-paste" class="tbm-label">ERP ?臾믩씜/??됱읈??곕궖 ?븐늿肉?節딅┛</label>
      <textarea
        id="tbm-paste"
        v-model="rawInput"
        class="tbm-paste-input"
        rows="10"
        placeholder="ERP ??? ??뺤삋域?癰귣벊沅????용뮞???癒?뮉 HTML ?븐늿肉?節딅┛"
      />
      <div class="tbm-actions">
        <button type="button" class="tbm-btn tbm-btn--primary" @click="parseInput">
          ?븐늿肉?節딅┛ ??곸뒠 ???뼓(沃섎챶?곮퉪?용┛ ??밴쉐)
        </button>
        <button type="button" class="tbm-btn" :disabled="!parseResult" @click="applyRiskToAll">
          ?袁る퓮?遺우뵥/??筌??袁⑷퍥 ?癒?짗?곕뗄荑?
        </button>
        <button type="button" class="tbm-btn" :disabled="draftRows.length === 0" @click="clearDraft">
          ??낆젾?λ뜃由??        </button>
      </div>
      <p class="tbm-hint">
        筌ㅼ뮇????밴쉐 ????볧닊??꽷??닌덉퍢?? ??뽰뇚??랁???뺤구??꽷??닌덉퍢筌?TBM ???怨몄몵嚥?獄쏆꼷???몃빍??
      </p>
    </section>

    <section v-if="parseResult" class="card">
      <h2>TBM ?λ뜆釉?/h2>
      <div class="tbm-meta-grid">
        <label>
          TBM??깆쁽
          <input v-model="nextDateInput" type="text" readonly />
        </label>
        <label>
          ?臾믨쉐 疫꿸퀣????곗뮇肉??
          <input v-model="sourceDateInput" type="text" readonly />
        </label>
        <label>
          ?袁⑹삢筌?          <input v-model="siteNameInput" type="text" />
        </label>
        <label>
          ?????          <input v-model="managerInput" type="text" />
        </label>
        <label>
          ?臾믩씜?關??
          <input v-model="workplaceInput" type="text" />
        </label>
      </div>
      <div class="tbm-meta-grid">
        <label>
          ?臾믩씜?????袁⑤뼎??鍮?
          <textarea v-model="teamLeaderMessage" rows="2" />
        </label>
        <label class="tbm-check">
          <input v-model="removeDuplicateRows" type="checkbox" />
          ??덉뵬 ?臾믩씜??곸뒠 餓λ쵎????볤탢 ????밴쉐
        </label>
      </div>
      <div class="tbm-meta-grid">
        <span class="tbm-count">???? {{ displayRows.length }}揶?/span>
        <button type="button" class="tbm-btn" :disabled="displayRows.length === 0" @click="addRow">
          ???곕떽?
        </button>
      </div>

      <div v-if="displayRows.length === 0" class="tbm-empty">
        ???뼓 野껉퀗??癒?퐣 ??뺤구??꽷??臾믩씜??곸뒠????곷뮸??덈뼄.
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
            ??筌?            <input v-model="row.teamName" type="text" />
          </label>
          <label>
            ?臾믩씜??            <input v-model="row.workerName" type="text" />
          </label>
          <label class="tbm-row-description">
            ?臾믩씜??곸뒠
            <textarea v-model="row.workDescription" rows="3" />
          </label>
          <label class="tbm-row-risk">
            ?袁る퓮?遺우뵥
            <textarea v-model="row.riskFactor" rows="3" />
          </label>
          <label class="tbm-row-measure">
            揶쏆뮇苑??筌?            <textarea v-model="row.countermeasure" rows="3" />
          </label>
        </div>
        <button type="button" class="tbm-btn" @click="applyRisk(idx)">
          ?????袁る퓮?遺우뵥/??筌??癒?짗?곕뗄荑?
        </button>
      </div>
    </section>

    <section v-if="parseResult && displayRows.length > 0" class="card">
      <div class="no-print">
        <button type="button" class="tbm-btn tbm-btn--primary" @click="printNow">
          PDF/?紐꾨뇵 ?遺얇늺 ?곗뮆??
        </button>
      </div>

      <div class="tbm-paper" id="tbm-paper">
        <h2>TBM ???(沃섎챶?곮퉪?용┛)</h2>
        <div class="tbm-paper-meta">
          <div><strong>TBM??깆쁽:</strong> {{ nextDateInput }}</div>
          <div><strong>?袁⑹삢筌?</strong> {{ siteNameInput || "-" }}</div>
          <div><strong>?????</strong> {{ managerInput || "-" }}</div>
          <div><strong>?臾믨쉐疫꿸퀣????곗뮇肉??:</strong> {{ sourceDateInput || "-" }}</div>
        </div>

        <table class="tbm-paper-table">
          <thead>
            <tr>
              <th style="width: 8%">??筌?/th>
              <th style="width: 10%">?臾믩씜??/th>
              <th style="width: 20%">?臾믩씜??곸뒠</th>
              <th style="width: 22%">?袁る퓮?遺우뵥</th>
              <th style="width: 22%">揶쏆뮇苑??筌?/th>
              <th style="width: 18%">?諭???臾믩씜??곸뒠</th>
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
          <p><strong>?臾믩씜?關??</strong> {{ workplaceInput || "-" }}</p>
          <p><strong>?臾믩씜?????袁⑤뼎??鍮?</strong> {{ teamLeaderMessage || "-" }}</p>
          <ol>
            <li>?袁⑷텢 TBM(?袁る퓮?源딅즸揶쎛/TBM)???袁④텊 ERP 筌뤿굞??臾믩씜??곕궖??疫꿸퀣???곗쨮 ?臾믨쉐??렽? 域뱀눖以??筌〓챷肉?獄?疫꿸퀡以됭퉪?곥?筌뤴뫗????臾믩씜 ??TBM ?λ뜆釉??낅빍??</li>
            <li>?袁㏉닋??TBM ??뺤구筌왖???袁㏉닋??TBM???嚥?揶쏅뜆???????됰뮸??덈뼄.</li>
            <li>?? ?袁㏉닋??TBM ??뺤구筌왖?癒?뮉 ?諭沅??臾믩씜?癒? ??釉??뤿선????렽? ?봔?袁⑹읈疫?TBM????? ??덉뵬???醫롮???疫꿸퀡以??곷선????몃빍??</li>
            <li>?袁る퓮?源딅즸揶쎛 野껉퀗???袁る솁???袁る립 ?봔?袁⑹읈疫?TBM????? ??彛??筌왖??PDF ?癒?뮉 ??롫굡燁삳똾逾?餓???롪돌嚥?癰귣떯???몃빍??</li>
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

const RAW_SAMPLE_HINT = `?곗뮇肉?? 2026-06-25
?袁⑹삢筌? [24025][1.???怨뚭탷?? 筌??찪18BL ??쎈돗??쎈?
????? 獄쏅베梨??;

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
    keywords: ["筌≪럥揆", "???춦", "??덈춦", "筌≪??", "?怨?", "?⑥쥙??, "?곕뗀??, "????, "??뺚뵭"],
    risk: "?⑤벊?쒒겫? 筌≪럥揆 ?怨? ??덈춦筌??臾믩씜 ???얜????띿쓺 筌ｋ똻夷????쇰선 ???⑤벏釉??? ??뺚뵭 ?醫롮벥 ??꾧퉱嚥?餓λ쵐????猿됲??곕뗀????袁る퓮",
    countermeasure: "獄쏆꼶諭??筌뤿챷????륁㉦?? 筌띾Ŧ?ф??袁⑥삋 ?癒?뮉 ??쇈걹???癒?? ?癒?궢 ?遺우벥 ??륁몵嚥≪뮆彛????⑤벏釉?袁⑥쨯 ?대Ŋ???뺣뼄. ?臾믩씜???關? ?????臾믩씜???怨몌폒 ?온?귐덉빵??뉖립??",
  },
  {
    keywords: ["??녾퐨", "?袁⑥젂??뺥닜", "獄쏄퀣苑?, "?냈????, "?띯뫀?", "野껉퀣??, "?諛?", "??곸벉", "?怨뚭퍙"],
    risk: "??녾퐨 獄??袁⑥젂??뺥닜 ?띯뫀? ?臾믩씜 餓??냈?????諛?, ?臾믩꺖???臾믩씜?癒?쉭, 獄쏅뗀???癒?삺嚥??紐낅퉸 域뱀눊?뤷칰?룻??봔??獄??袁⑤즲 ?袁る퓮",
    countermeasure: "?臾믩씜 ????ъ쨮?? 獄쏅뗀???癒?삺???類ｂ봺??랁? ?얜?????諛? ?臾믩씜?? 2????곴맒 ?臾믩씜??뺣뼄. ?臾믩씜 餓???댿봺 ??쑵??깆눊???얜???????????疫뀀뜆???랁??臾믩씜???關???臾믩씜?癒?쉭?? ??ъ쨮 ?怨밴묶???類ㅼ뵥??뺣뼄.",
  },
  {
    keywords: ["獄쏄퀗?", "???뵠??, "?⑤벀??, "???롧뵳?, "筌띾Ŧ?ф?, "?臾믩씜獄쏆뮉??],
    risk: "?怨? ?癒?뮉 甕곗럩猿?獄쏄퀗? ?臾믩씜 餓????롧뵳?猷몄춾??쑨?????? ?⑤벀?????? ?癒?삺 ??而??⑥눘??癒?퐣 ?곕뗀?レ쮯??됰릭夷?袁⑤즲 ?袁る퓮",
    countermeasure: "筌띾Ŧ?ф??癒?뮉 ?臾믩씜獄쏆뮉?????됱젟?怨몄몵嚥???쇳뒄??랁? ?怨? ?臾믩씜 ??筌뤿챷???⑥눖猷??띿쓺 筌묒? ??낅뮉?? ?⑤벀??? ?癒?삺????됰릭??? ??낅즲嚥??類ｂ봺??랁? ??猷??ъ쨮???類ｋ궖?????臾믩씜??뺣뼄.",
  },
  {
    keywords: ["?袁⑸였", "?袁㏓┛", "?袁⑹읈", "?냈????, "?袁?", "??곕궗", "?袁⑸뻻?袁⑸였", "?袁⑸뻻 ?袁⑸였", "?袁⑹뜚"],
    risk: "?袁⑸뻻?袁⑸였 ??쇳뒄 餓??袁⑹뜚 ?怨뚭퍙, ?냈??????곕궗 ?癒?맒, ?袁⑹읈筌△뫀?믤묾?沃섎챸??紐꾩몵嚥??紐낅립 揶쏅Ŋ??獄??遺우삺 ?袁る퓮",
    countermeasure: "?臾믩씜 ???袁⑹뜚 筌△뫀??????? ?袁⑹읈筌△뫀?믤묾??臾먮짗?怨밴묶???類ㅼ뵥??뺣뼄. ?癒?맒???냈????? ?????? ??꾪? 野껉퀣苑묌겫????紐꾪뀱??? ??낅즲嚥?鈺곌퀣??????臾믩씜??뺣뼄.",
  },
  {
    keywords: ["??뱀젔", "??뱀젔疫?, "??쎈솭??, "???뒄", "疫꿸퀗??, "?⑥쥙??],
    risk: "?⑤벀??鈺곌퀣??餓??臾믩씜?癒?벥 ?⑥눘??? ?袁㏓럡 ??됰릭, ??됰릭??獄??袁⑤즲 ?袁る퓮??獄쏆뮇源??????덈뼄",
    countermeasure: "?⑥쥙????븍뜄????⑤벀???筌앸맩???대Ŋ猿??랁? ????餓??袁㏓럡????됰릭??筌띾맦由??袁る퉸 獄쏆꼷?싷쭕?룸궢 癰귣똻??癒? 筌왖?類λ립?? ?臾믩씜 ?닌딅열?癒?뮉 ?臾롫젏 ???젫????쇰뻻??뺣뼄.",
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
      "?臾믩씜 餓??곕뗀?? ??깆뿫, ??됰릭??獄?域뱀눊?뤷칰?룻??봔????癰귣벏鍮 ??됱읈?袁る퓮??獄쏆뮇源??????됱몵沃샕嚥??袁⑹삢癰??袁る퓮?源딅즸揶쎛 疫꿸퀣???곗쨮 ????癒????袁⑹뒄??몃빍??",
    countermeasure: "?臾믩씜獄쏆꼷??筌왖??뽯퓠 ?怨뺤뵬 癰귣똾?뉑뤃?筌△뫗??獄??臾믩씜 ??덇퐨?????뤷칰???랁? ?臾믩씜 ??뽮퐣???브쑨由??疫꿸퀣???곗쨮 ?類?夷???????筌욊쑵六??뺣뼄.",
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
