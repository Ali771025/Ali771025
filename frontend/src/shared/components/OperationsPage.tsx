import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography
} from '@mui/material';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { TokenAccountingPanel } from '../../reporting/components/TokenAccountingPanel';
import type { PageBlueprint } from '../contracts/pageBlueprint';
import { managementPageCapabilities } from '../contracts/pageBlueprint';

function makeRows(page: PageBlueprint) {
  const columns = page.tableColumns?.length ? page.tableColumns : [{ field: 'name', headerName: 'نام' }, { field: 'status', headerName: 'وضعیت' }];
  return Array.from({ length: 8 }).map((_, index) => {
    const row: Record<string, string | number> = { id: index + 1 };
    columns.forEach((column) => {
      row[column.field] = column.sensitive
        ? '***REDACTED***'
        : column.field.includes('status') || column.field === 'result'
          ? index % 3 === 0 ? 'نیازمند بررسی' : 'فعال'
          : column.field.includes('request')
            ? `req-${page.id}-${index + 1}`
            : `${column.headerName} ${index + 1}`;
    });
    return row;
  });
}

export function OperationsPage({ page }: { page: PageBlueprint }) {
  const [activeTab, setActiveTab] = useState(0);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const rows = useMemo(() => makeRows(page), [page]);
  const columns: GridColDef[] = (page.tableColumns?.length ? page.tableColumns : [{ field: 'name', headerName: 'نام', width: 220 }, { field: 'status', headerName: 'وضعیت', width: 140 }]).map((column) => ({
    field: column.field,
    headerName: column.headerName,
    width: column.width ?? 170,
    sortable: true,
    filterable: false,
    renderCell: (params) => column.sensitive ? <Chip color="warning" size="small" label="Redacted" /> : String(params.value ?? '-')
  }));

  return (
    <Stack spacing={3}>
      <Box>
        <Typography color="text.secondary" variant="body2">
          خانه / {page.environment} / {page.module}
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mt: 1 }}>
          <Box>
            <Typography sx={{ fontWeight: 800 }} variant="h4">{page.title}</Typography>
            <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 980 }}>{page.description}</Typography>
          </Box>
          <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
            <Chip color="primary" label={page.priority} />
            <Chip label={page.persona} variant="outlined" />
            <Chip label={`مجوزها: ${page.permissions.join('، ')}`} variant="outlined" />
          </Stack>
        </Stack>
      </Box>

      <Card variant="outlined">
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <TextField fullWidth label="جست‌وجو" placeholder="جست‌وجو در رکوردها، Request ID یا Correlation ID" />
            <FormControl fullWidth>
              <InputLabel>سازمان</InputLabel>
              <Select defaultValue="all" label="سازمان"><MenuItem value="all">همه سازمان‌ها</MenuItem><MenuItem value="municipality-01">شهرداری نمونه</MenuItem></Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>نرم‌افزار</InputLabel>
              <Select defaultValue="behsaz" label="نرم‌افزار"><MenuItem value="behsaz">بهساز</MenuItem><MenuItem value="all">همه نرم‌افزارها</MenuItem></Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>نسخه</InputLabel>
              <Select defaultValue="12.4.0" label="نسخه"><MenuItem value="12.4.0">12.4.0</MenuItem><MenuItem value="all">همه نسخه‌ها</MenuItem></Select>
            </FormControl>
          </Stack>
          <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', mt: 2 }}>
            {(page.filters ?? []).map((filter) => <Chip key={filter} label={filter} variant="outlined" />)}
            <Chip color="success" label="Server-side pagination" />
            <Chip label="Rows: 25 / 50 / 100" />
            <Chip label="آخرین به‌روزرسانی: اکنون" />
          </Stack>
        </CardContent>
      </Card>

      {page.cards?.length ? (
        <Grid container spacing={2}>
          {page.cards.map((card, index) => (
            <Grid key={card} size={{ xs: 12, sm: 6, md: 3 }}>
              <Card sx={{ height: '100%' }} variant="outlined">
                <CardContent>
                  <Typography color="text.secondary" variant="body2">{card}</Typography>
                  <Typography sx={{ fontWeight: 800, mt: 1 }} variant="h5">{index % 2 ? '۹۴٪' : (index + 1) * 17}</Typography>
                  <Typography color="success.main" variant="caption">قابل کلیک برای گزارش جزئی</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      ) : null}

      {['onprem-report-request', 'requests-monitoring'].includes(page.id) ? (
        <TokenAccountingPanel />
      ) : null}

      {page.workflow?.length ? (
        <Card variant="outlined">
          <CardContent>
            <Typography sx={{ fontWeight: 700 }} gutterBottom>گردش‌کار اجرایی</Typography>
            <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
              {page.workflow.map((step, index) => <Chip key={step} color={index === 0 ? 'primary' : 'default'} label={`${index + 1}. ${step}`} />)}
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      {page.formTabs?.length ? (
        <Card variant="outlined">
          <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} variant="scrollable">
            {page.formTabs.map((tab) => <Tab key={tab.title} label={tab.title} />)}
          </Tabs>
          <Divider />
          <CardContent>
            <Grid container spacing={2}>
              {page.formTabs[activeTab]?.fields.map((field) => (
                <Grid key={field.name} size={{ xs: 12, md: field.type === 'textarea' || field.type === 'matrix' ? 12 : 6 }}>
                  <TextField
                    fullWidth
                    label={`${field.label}${field.required ? ' *' : ''}`}
                    multiline={field.type === 'textarea' || field.type === 'matrix'}
                    minRows={field.type === 'textarea' || field.type === 'matrix' ? 4 : undefined}
                    placeholder={field.sensitive ? 'پس از ثبت دوباره نمایش داده نمی‌شود' : field.label}
                    type={field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'}
                  />
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      ) : null}

      <Card variant="outlined">
        <CardContent>
          <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', mb: 2 }}>
            <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
              <Button variant="contained">ایجاد</Button>
              <Button variant="outlined">ویرایش</Button>
              <Button color="warning" variant="outlined">عملیات گروهی</Button>
              <Button variant="outlined">Export CSV/Excel</Button>
            </Stack>
            <Button onClick={() => { setLoadingDemo(true); setTimeout(() => setLoadingDemo(false), 700); }}>نمایش Loading State</Button>
          </Stack>
          {loadingDemo ? <LinearProgress sx={{ mb: 2 }} /> : null}
          <Box sx={{ height: 440, width: '100%' }}>
            <DataGrid
              checkboxSelection
              columns={columns}
              disableRowSelectionOnClick
              initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
              pageSizeOptions={[10, 25, 50, 100]}
              rows={rows}
            />
          </Box>
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Alert severity="info">
            اجزای مشترک فعال: {managementPageCapabilities.slice(0, 7).join('، ')} و سایر الزامات مدیریتی.
          </Alert>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Alert severity="warning">
            عملیات حساس: {(page.sensitiveOperations?.length ? page.sensitiveOperations : ['ثبت Audit', 'تأیید دومرحله‌ای']).join('، ')}
          </Alert>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Alert severity="success">
            APIهای صفحه: {page.api.join(' | ')} — Headerهای فنی: X-Request-ID، X-Correlation-ID، Idempotency-Key برای Mutationها.
          </Alert>
        </Grid>
        {page.securityNotes?.map((note) => (
          <Grid key={note} size={{ xs: 12 }}><Alert severity="error">{note}</Alert></Grid>
        ))}
      </Grid>
    </Stack>
  );
}
