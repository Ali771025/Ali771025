const { z } = require('zod');
const { isValidIranMobile, normalizeDigits } = require('../utils/helpers');

const phone = z
  .string({ required_error: 'شماره تماس الزامی است' })
  .transform((v) => normalizeDigits(v).replace(/[\s-]/g, ''))
  .refine(isValidIranMobile, { message: 'شماره موبایل معتبر نیست (مثال: 09121234567)' });

const uuid = z.string().uuid({ message: 'شناسه نامعتبر است' });

const createOrderSchema = z.object({
  serviceType: z.enum(['repair', 'installation', 'warranty'], {
    errorMap: () => ({ message: 'نوع خدمت نامعتبر است' }),
  }),
  customerName: z.string().min(3, 'نام و نام خانوادگی حداقل ۳ حرف').max(120),
  customerPhone: phone,
  customerMobile: phone.optional().or(z.literal('')),
  nationalId: z.string().regex(/^\d{10}$/).optional().or(z.literal('')),
  postalCode: z.string().regex(/^\d{10}$/).optional().or(z.literal('')),

  provinceId: uuid,
  cityId: uuid,
  address: z.string().min(10, 'آدرس کامل حداقل ۱۰ کاراکتر'),
  latitude: z.coerce.number().min(-90).max(90).optional().nullable(),
  longitude: z.coerce.number().min(-180).max(180).optional().nullable(),

  applianceTypeId: uuid,
  brandId: uuid,
  faultCategoryId: uuid.optional().nullable(),
  deviceModel: z.string().max(120).optional().or(z.literal('')),
  purchaseDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().or(z.literal('')),
  warrantyCode: z.string().max(60).optional().or(z.literal('')),
  problemDescription: z.string().max(2000).optional().or(z.literal('')),

  preferredDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().or(z.literal('')),
  preferredTimeSlot: z.enum(['morning', 'afternoon', 'evening']).optional().nullable(),

  utmSource: z.string().max(80).optional(),
  utmMedium: z.string().max(80).optional(),
  utmCampaign: z.string().max(80).optional(),
  landingPage: z.string().max(300).optional(),
});

/* Warranty orders require warranty card info */
const orderWithBusinessRules = createOrderSchema.superRefine((data, ctx) => {
  if (data.serviceType === 'warranty') {
    if (!data.warrantyCode) ctx.addIssue({ code: 'custom', path: ['warrantyCode'], message: 'برای سفارش گارانتی، کد کارت گارانتی الزامی است' });
    if (!data.purchaseDate) ctx.addIssue({ code: 'custom', path: ['purchaseDate'], message: 'برای سفارش گارانتی، تاریخ خرید الزامی است' });
  }
  if (data.serviceType === 'repair' && !data.faultCategoryId) {
    ctx.addIssue({ code: 'custom', path: ['faultCategoryId'], message: 'انتخاب نوع خرابی برای درخواست تعمیرات الزامی است' });
  }
});

const leadSchema = z.object({
  name: z.string().min(2).max(120).optional().or(z.literal('')),
  phone,
  message: z.string().max(1000).optional().or(z.literal('')),
  sourcePage: z.string().max(300).optional(),
});

const reviewSchema = z.object({
  trackingCode: z.string().min(6),
  rating: z.coerce.number().int().min(1).max(5),
  comment: z.string().max(1000).optional().or(z.literal('')),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(6),
});

const adminOrderUpdateSchema = z.object({
  status: z.enum(['pending', 'confirmed', 'assigned', 'in_progress', 'completed', 'cancelled']).optional(),
  technicianId: uuid.optional().nullable(),
  estimatedCost: z.coerce.number().min(0).optional().nullable(),
  finalCost: z.coerce.number().min(0).optional().nullable(),
  adminNote: z.string().max(2000).optional(),
  cancelReason: z.string().max(1000).optional(),
  note: z.string().max(1000).optional(),
});

function validate(schema) {
  return (req, _res, next) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      const details = result.error.issues.map((i) => ({ field: i.path.join('.'), message: i.message }));
      return next(Object.assign(new Error('اعتبارسنجی ناموفق'), { statusCode: 422, details }));
    }
    req.validated = result.data;
    next();
  };
}

module.exports = { validate, createOrderSchema: orderWithBusinessRules, leadSchema, reviewSchema, loginSchema, adminOrderUpdateSchema };
