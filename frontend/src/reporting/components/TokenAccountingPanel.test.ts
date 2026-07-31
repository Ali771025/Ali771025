import { describe, expect, it } from 'vitest';
import { estimateReportTokens } from './TokenAccountingPanel';

describe('estimateReportTokens', () => {
  it('estimates non-zero tokens and cost', () => {
    const result = estimateReportTokens('آخرین پرونده‌های ماده ۱۰۰ را نشان بده');
    expect(result.prompt).toBeGreaterThan(0);
    expect(result.completion).toBeGreaterThan(0);
    expect(result.total).toBe(result.prompt + result.completion);
    expect(result.cost).toBeGreaterThan(0);
  });
});
