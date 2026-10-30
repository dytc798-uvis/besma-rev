import { workReturn } from "/assets/workspace-return.js";
export function collectionWorkEntry(query) {
  const requested = query.work_entry !== void 0;
  const scalar = (v, max) => typeof v === "string" && v.length > 0 && v.length <= max && !/[\u0000-\u001f\u007f\\]/.test(v);
  if (!requested) return { requested: false, valid: true, month: "", site: "", documentCode: "", period: "", returnTo: "" };
  const valid = query.work_entry === "1" && scalar(query.month, 7) && /^20\d{2}-(0[1-9]|1[0-2])$/.test(query.month) && scalar(query.site, 100) && scalar(query.document_code, 60) && /^GOV_[A-Z0-9_]+$/.test(query.document_code) && (query.period === void 0 || scalar(query.period, 15) && /^(20\d{2}-(0[1-9]|1[0-2])(-W[1-6])?|20\d{2}-H[12]|once)$/.test(query.period));
  return { requested: true, valid: !!valid, month: valid ? query.month : "", site: valid ? query.site : "", documentCode: valid ? query.document_code : "", period: valid && typeof query.period === "string" ? query.period : "", returnTo: workReturn(typeof query.return === "string" ? query.return : "/") };
}
