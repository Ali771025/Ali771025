import { Alert, Card, CardContent, Chip, Grid, Stack, Typography } from '@mui/material';

export function estimateReportTokens(question: string) {
  const prompt = Math.max(120, Math.ceil(question.length / 2.6) + 560);
  const completion = Math.max(80, Math.min(700, Math.ceil(prompt * 0.34)));
  const cost = Number((prompt * 0.00002 + completion * 0.00004).toFixed(6));
  return { prompt, completion, total: prompt + completion, cost };
}

export function TokenAccountingPanel({ question = 'آخرین پرونده‌های ماده ۱۰۰ را نشان بده', balance = 10_000 }: { question?: string; balance?: number }) {
  const estimate = estimateReportTokens(question);
  const after = Number((balance - estimate.cost).toFixed(6));
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <Typography sx={{ fontWeight: 800 }}>محاسبه Token و اعتبار درخواست گزارش</Typography>
          <Grid container spacing={1}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}><Chip color="primary" label={`Prompt: ${estimate.prompt}`} /></Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}><Chip color="primary" label={`Completion: ${estimate.completion}`} /></Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}><Chip label={`Cost: ${estimate.cost}`} /></Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}><Chip color={after > 0 ? 'success' : 'error'} label={`Balance after: ${after}`} /></Grid>
          </Grid>
          <Alert severity="info">
            Backend همین محاسبه را با Tariff فعال، Policy Hash، Access Fingerprint و Idempotency-Key نهایی می‌کند و در Wallet Ledger غیرقابل‌ویرایش ثبت می‌کند.
          </Alert>
        </Stack>
      </CardContent>
    </Card>
  );
}
