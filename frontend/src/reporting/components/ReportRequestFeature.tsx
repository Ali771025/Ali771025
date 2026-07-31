import { useMemo, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import { clientUuid } from '../../shared/api/httpClient';
import { reportApi } from '../../features/reporting/api/reportApi';
import type { ReportResponse } from '../../features/reporting/model/types';

const reportRequestSchema = z.object({
  question: z.string().min(5, 'حداقل ۵ کاراکتر لازم است.').max(4000, 'سؤال بیش از حد طولانی است.'),
  outputType: z.enum(['auto', 'table', 'text']),
  maxRows: z.number().int().min(1).max(500),
  region: z.string().min(1),
  caseNo: z.string().optional(),
  dateFrom: z.string().optional(),
  dateTo: z.string().optional()
});

type ReportRequestForm = z.infer<typeof reportRequestSchema>;

function toPayload(values: ReportRequestForm) {
  const question = [values.question, values.caseNo ? `شماره پرونده ${values.caseNo}` : ''].filter(Boolean).join(' ');
  return {
    request_id: clientUuid(),
    software_id: 'behsaz',
    software_version: '12.4.0',
    user_id: 'user-1025',
    question,
    access_context: {
      organization: 'municipality-01',
      region: values.region.split(',').map((item) => item.trim()).filter(Boolean),
      roles: ['report-user'],
      scopes: ['commission100.read']
    },
    locale: 'fa-IR',
    timezone: 'Asia/Tehran'
  };
}

export function ReportRequestFeature() {
  const [response, setResponse] = useState<ReportResponse>();
  const [technicalErrorId, setTechnicalErrorId] = useState<string>();
  const form = useForm<ReportRequestForm>({
    resolver: zodResolver(reportRequestSchema),
    defaultValues: {
      question: 'آخرین پرونده‌های ماده ۱۰۰ را نشان بده',
      outputType: 'table',
      maxRows: 20,
      region: '1,2',
      caseNo: '',
      dateFrom: '',
      dateTo: ''
    }
  });
  const watchedQuestion = form.watch('question');
  const watchedPayload = useMemo(() => toPayload(form.getValues()), [watchedQuestion]);

  const estimateMutation = useMutation({ mutationFn: (values: ReportRequestForm) => reportApi.estimateTokens(toPayload(values)) });
  const generateMutation = useMutation({
    mutationFn: (values: ReportRequestForm) => reportApi.generate(toPayload(values)),
    onSuccess: (result) => setResponse(result),
    onError: () => setTechnicalErrorId(`ui-report-${Date.now()}`)
  });

  async function submit(values: ReportRequestForm) {
    setTechnicalErrorId(undefined);
    await estimateMutation.mutateAsync(values);
    await generateMutation.mutateAsync(values);
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography color="text.secondary" variant="body2">بهساز / گزارش‌ساز هوشمند / درخواست گزارش</Typography>
        <Typography sx={{ fontWeight: 900 }} variant="h4">فرم عملیاتی درخواست گزارش</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          این صفحه نمونه واقعی مسیر کاربر نهایی است: اعتبارسنجی فرم، تخمین Token/Cost، کنترل سهمیه و تولید SQL پارامتری بدون خروج داده خام از شبکه مشتری.
        </Typography>
      </Box>

      <Card variant="outlined">
        <CardContent>
          <Stack component="form" spacing={2} onSubmit={form.handleSubmit(submit)}>
            <Controller
              control={form.control}
              name="question"
              render={({ field, fieldState }) => (
                <TextField {...field} error={!!fieldState.error} helperText={fieldState.error?.message ?? 'نمونه: آخرین پرونده‌های ماده ۱۰۰ منطقه ۱ را نشان بده'} label="شرح فارسی گزارش" multiline minRows={4} />
              )}
            />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 3 }}>
                <Controller control={form.control} name="outputType" render={({ field }) => <TextField {...field} label="نوع خروجی" select fullWidth><MenuItem value="auto">خودکار</MenuItem><MenuItem value="table">جدول</MenuItem><MenuItem value="text">متن</MenuItem></TextField>} />
              </Grid>
              <Grid size={{ xs: 12, md: 3 }}>
                <Controller control={form.control} name="maxRows" render={({ field, fieldState }) => <TextField {...field} onChange={(event) => field.onChange(Number(event.target.value))} error={!!fieldState.error} helperText={fieldState.error?.message} label="حداکثر رکورد" type="number" fullWidth />} />
              </Grid>
              <Grid size={{ xs: 12, md: 3 }}>
                <Controller control={form.control} name="region" render={({ field, fieldState }) => <TextField {...field} error={!!fieldState.error} helperText={fieldState.error?.message} label="منطقه" fullWidth />} />
              </Grid>
              <Grid size={{ xs: 12, md: 3 }}>
                <Controller control={form.control} name="caseNo" render={({ field }) => <TextField {...field} label="شماره پرونده اختیاری" fullWidth />} />
              </Grid>
            </Grid>
            <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
              <Button disabled={estimateMutation.isPending || generateMutation.isPending} onClick={() => estimateMutation.mutate(form.getValues())} variant="outlined">تخمین Token و هزینه</Button>
              <Button disabled={estimateMutation.isPending || generateMutation.isPending} type="submit" variant="contained">تولید گزارش</Button>
              <Button onClick={() => { form.reset(); setResponse(undefined); }} variant="text">پاک‌کردن</Button>
            </Stack>
            {(estimateMutation.isPending || generateMutation.isPending) ? <LinearProgress /> : null}
          </Stack>
        </CardContent>
      </Card>

      {estimateMutation.data ? (
        <Card variant="outlined">
          <CardContent>
            <Typography sx={{ fontWeight: 800 }} gutterBottom>نتیجه تخمین Backend</Typography>
            <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
              <Chip color="primary" label={`Prompt: ${estimateMutation.data.prompt_tokens}`} />
              <Chip color="primary" label={`Completion: ${estimateMutation.data.completion_tokens}`} />
              <Chip label={`Cost: ${estimateMutation.data.estimated_cost}`} />
              <Chip color="success" label={`Balance After: ${estimateMutation.data.balance_after}`} />
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      {response?.status === 'success' ? (
        <Alert severity="success">
          SQL پارامتری تولید شد. Audit ID: {response.audit_id} | Cost: {String(response.policy.estimated_cost)} | Access Fingerprint: {String(response.policy.access_fingerprint)}
        </Alert>
      ) : null}
      {response?.status === 'needs_clarification' ? <Alert severity="warning">{response.question}</Alert> : null}
      {response?.status === 'rejected' ? <Alert severity="error">{response.reason_code}: {response.message}</Alert> : null}
      {technicalErrorId ? <Alert severity="error">خطای فنی کنترل‌شده. Request ID: {technicalErrorId}</Alert> : null}

      <Card variant="outlined">
        <CardContent>
          <Typography sx={{ fontWeight: 800 }} gutterBottom>Payload سیستمی مخفی</Typography>
          <pre dir="ltr" style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(watchedPayload, null, 2)}</pre>
        </CardContent>
      </Card>
    </Stack>
  );
}
