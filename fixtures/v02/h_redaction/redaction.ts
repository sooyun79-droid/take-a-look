// Entirely synthetic credential-looking fixture. This is not an active key.
const API_KEY = "sk-SYNTHETIC_FIXTURE_NOT_A_REAL_KEY_123456";
export function average(values: number[]) {
  if (!values.length) return 0;
  return values.reduce((a,b)=>a+b,0) / values.length;
}
