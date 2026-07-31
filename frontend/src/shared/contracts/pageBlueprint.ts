export type EnvironmentKey = 'public' | 'owner' | 'software-admin' | 'on-premise' | 'connector';

export type FieldBlueprint = {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'date' | 'datetime' | 'textarea' | 'checkbox' | 'file' | 'password' | 'matrix';
  required?: boolean;
  sensitive?: boolean;
  options?: string[];
};

export type TableColumnBlueprint = {
  field: string;
  headerName: string;
  width?: number;
  sensitive?: boolean;
};

export type PageBlueprint = {
  id: string;
  environment: EnvironmentKey;
  module: string;
  path: string;
  title: string;
  description: string;
  persona: string;
  priority: 'pilot' | 'pre-production' | 'final';
  permissions: string[];
  api: string[];
  cards?: string[];
  filters?: string[];
  tableColumns?: TableColumnBlueprint[];
  formTabs?: { title: string; fields: FieldBlueprint[] }[];
  workflow?: string[];
  sensitiveOperations?: string[];
  securityNotes?: string[];
};

export const managementPageCapabilities = [
  'Breadcrumb',
  'عنوان و توضیح صفحه',
  'انتخاب سازمان، نرم‌افزار و نسخه',
  'جست‌وجو و فیلتر پیشرفته',
  'مرتب‌سازی و صفحه‌بندی Server-side',
  'انتخاب چند رکورد و عملیات گروهی',
  'Export CSV/Excel بر اساس مجوز',
  'Loading / Empty / Error State',
  'تأیید دومرحله‌ای عملیات حساس',
  'نمایش مجوز مؤثر کاربر',
  'زمان آخرین به‌روزرسانی',
  'Request ID و Correlation ID در خطاهای فنی',
  'Audit Log برای عملیات مهم'
];
