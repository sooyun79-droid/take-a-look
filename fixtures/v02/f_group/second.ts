export const second = (items: number[]) => items.length > 0 ? items.reduce((a,b) => a+b,0) / items.length : 0;
