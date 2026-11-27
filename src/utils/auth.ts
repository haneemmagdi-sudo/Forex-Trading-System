/**
 * auth.ts — رمز الدخول الذي يطلبه الخادم لكل عملية تغيّر شيئاً.
 * يُدخله المستخدم مرة ويُحفظ في متصفحه فقط؛ قيمته هي API_TOKEN في ملف .env.
 */
const STORAGE_KEY = 'qfsm.apiToken';
let memoryToken = '';

export function getApiToken(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setApiToken(token: string) {
  memoryToken = token.trim();
  try {
    if (memoryToken) localStorage.setItem(STORAGE_KEY, memoryToken);
    else localStorage.removeItem(STORAGE_KEY);
  } catch { /* التخزين غير متاح: يبقى الرمز لهذه الجلسة فقط */ }
}

export function authHeaders(): Record<string, string> {
  const token = getApiToken();
  return token ? { 'X-API-Token': token } : {};
}
