/** 미확인 문서 코멘트 티커 갱신 — 확인 상태는 서버(현장 단위 DB) 기준. */
export function notifyDocCommentTickerChanged(): void {
  window.dispatchEvent(new CustomEvent("besma-doc-comment-ticker-ack"));
}
