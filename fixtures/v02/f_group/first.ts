export const first = (values: number[]) => values.length ? values.reduce((a,b) => a+b,0) / values.length : null;
