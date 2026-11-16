const { Op } = require('sequelize');
const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');
const multer = require('multer');
const {
  Order, OrderPhoto, OrderStatusLog, Province, City, ApplianceType,
  Brand, FaultCategory, Technician, Review, sequelize,
} = require('../models');
const { ApiError, ah } = require('../utils/errors');
const { generateTrackingCode, getPagination } = require('../utils/helpers');

/* ------------------------- photo upload (multer) ------------------------- */
const UPLOAD_DIR = path.join(__dirname, '../../uploads');
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, UPLOAD_DIR),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    cb(null, `${uuidv4()}${ext}`);
  },
});
const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024, files: 5 },
  fileFilter: (_req, file, cb) => {
    if (/^image\/(jpe?g|png|webp)$/i.test(file.mimetype)) cb(null, true);
    else cb(ApiError.badRequest('فقط تصویر JPG/PNG/WebP مجاز است'));
  },
});

/* ------------------------------ create order ----------------------------- */
const createOrder = ah(async (req, res) => {
  const data = req.validated;

  // verify referential integrity
  const [province, city, appliance, brand] = await Promise.all([
    Province.findByPk(data.provinceId),
    City.findByPk(data.cityId),
    ApplianceType.findByPk(data.applianceTypeId),
    Brand.findByPk(data.brandId),
  ]);
  if (!province || !province.isActive) throw ApiError.badRequest('استان نامعتبر است');
  if (!city || !city.isActive || city.provinceId !== province.id) throw ApiError.badRequest('شهر نامعتبر یا خارج از پوشش است');
  if (!appliance || !appliance.isActive) throw ApiError.badRequest('نوع دستگاه نامعتبر است');
  if (!brand || !brand.isActive) throw ApiError.badRequest('برند نامعتبر است');

  if (data.faultCategoryId) {
    const fault = await FaultCategory.findByPk(data.faultCategoryId);
    if (!fault) throw ApiError.badRequest('نوع خرابی نامعتبر است');
  }

  // unique tracking code (retry on rare collision)
  let trackingCode;
  for (let i = 0; i < 5; i++) {
    trackingCode = generateTrackingCode();
    const exists = await Order.findOne({ where: { trackingCode } });
    if (!exists) break;
  }

  const t = await sequelize.transaction();
  try {
    const order = await Order.create({
      ...data,
      trackingCode,
      customerMobile: data.customerMobile || null,
      nationalId: data.nationalId || null,
      postalCode: data.postalCode || null,
      deviceModel: data.deviceModel || null,
      purchaseDate: data.purchaseDate || null,
      warrantyCode: data.warrantyCode || null,
      problemDescription: data.problemDescription || null,
      preferredDate: data.preferredDate || null,
      userAgent: (req.headers['user-agent'] || '').slice(0, 300),
    }, { transaction: t });

    await OrderStatusLog.create({ orderId: order.id, fromStatus: null, toStatus: 'pending', note: 'ثبت سفارش توسط مشتری' }, { transaction: t });
    await t.commit();

    // attach uploaded photos if any
    if (req.files && req.files.length) {
      await OrderPhoto.bulkCreate(req.files.map((f) => ({ orderId: order.id, url: `/uploads/${f.filename}` })));
    }

    res.status(201).json({
      success: true,
      message: 'سفارش شما با موفقیت ثبت شد',
      data: { id: order.id, trackingCode: order.trackingCode, status: order.status },
    });
  } catch (e) {
    await t.rollback();
    throw e;
  }
});

/* --------------------------- track by code/phone -------------------------- */
const trackOrder = ah(async (req, res) => {
  const { code } = req.params;
  const order = await Order.findOne({
    where: { trackingCode: code.toUpperCase() },
    include: [
      { model: ApplianceType, as: 'applianceType', attributes: ['nameFa', 'slug'] },
      { model: Brand, as: 'brand', attributes: ['nameFa', 'slug'] },
      { model: FaultCategory, as: 'faultCategory', attributes: ['nameFa'] },
      { model: Province, as: 'province', attributes: ['nameFa'] },
      { model: City, as: 'city', attributes: ['nameFa'] },
      { model: Technician, as: 'technician', attributes: ['fullName', 'rating'] },
      { model: OrderStatusLog, as: 'statusLogs', order: [['created_at', 'ASC']] },
    ],
    attributes: { exclude: ['nationalId', 'userAgent'] },
  });
  if (!order) throw ApiError.notFound('سفارشی با این کد رهگیری یافت نشد');
  res.json({ success: true, data: order });
});

/* -------------------------------- my orders ------------------------------- */
const getOrdersByPhone = ah(async (req, res) => {
  const phoneRaw = (req.query.phone || '').replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
  if (!phoneRaw) throw ApiError.badRequest('شماره موبایل را وارد کنید');
  const orders = await Order.findAll({
    where: { customerPhone: phoneRaw },
    order: [['created_at', 'DESC']],
    include: [
      { model: ApplianceType, as: 'applianceType', attributes: ['nameFa'] },
      { model: Brand, as: 'brand', attributes: ['nameFa'] },
    ],
    attributes: ['id', 'trackingCode', 'serviceType', 'status', 'createdAt', 'preferredDate', 'estimatedCost', 'finalCost'],
  });
  res.json({ success: true, data: orders });
});

/* ---------------------------------- review -------------------------------- */
const submitReview = ah(async (req, res) => {
  const { trackingCode, rating, comment } = req.validated;
  const order = await Order.findOne({ where: { trackingCode: trackingCode.toUpperCase() } });
  if (!order) throw ApiError.notFound('سفارش یافت نشد');
  if (order.status !== 'completed') throw ApiError.badRequest('امکان ثبت نظر فقط برای سفارش‌های تکمیل‌شده وجود دارد');
  const existing = await Review.findOne({ where: { orderId: order.id } });
  if (existing) throw ApiError.conflict('برای این سفارش قبلاً نظر ثبت شده است');
  const review = await Review.create({
    orderId: order.id,
    customerName: order.customerName,
    rating,
    comment: comment || null,
    isPublished: true,
  });
  res.status(201).json({ success: true, message: 'از ثبت نظر شما سپاسگزاریم', data: review });
});

/* ============================ ADMIN controllers =========================== */
const adminListOrders = ah(async (req, res) => {
  const { page, limit, offset } = getPagination(req.query);
  const where = {};
  if (req.query.status) where.status = req.query.status;
  if (req.query.serviceType) where.serviceType = req.query.serviceType;
  if (req.query.cityId) where.cityId = req.query.cityId;
  if (req.query.brandId) where.brandId = req.query.brandId;
  if (req.query.search) {
    const s = `%${req.query.search}%`;
    where[Op.or] = [
      { trackingCode: { [Op.iLike]: s } },
      { customerName: { [Op.like]: s } },
      { customerPhone: { [Op.like]: s } },
    ];
  }
  const { rows, count } = await Order.findAndCountAll({
    where,
    offset,
    limit,
    order: [['created_at', 'DESC']],
    include: [
      { model: ApplianceType, as: 'applianceType', attributes: ['nameFa'] },
      { model: Brand, as: 'brand', attributes: ['nameFa'] },
      { model: City, as: 'city', attributes: ['nameFa'] },
      { model: Technician, as: 'technician', attributes: ['id', 'fullName'] },
    ],
  });
  res.json({ success: true, data: rows, meta: { total: count, page, limit, pages: Math.ceil(count / limit) } });
});

const STATUS_FLOW = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['assigned', 'cancelled'],
  assigned: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

const adminUpdateOrder = ah(async (req, res) => {
  const order = await Order.findByPk(req.params.id);
  if (!order) throw ApiError.notFound('سفارش یافت نشد');
  const d = req.validated;

  if (d.status && d.status !== order.status) {
    const allowed = STATUS_FLOW[order.status] || [];
    if (!allowed.includes(d.status)) {
      throw ApiError.badRequest(`انتقال وضعیت از «${order.status}» به «${d.status}» مجاز نیست`);
    }
    if (d.status === 'assigned' && !d.technicianId && !order.technicianId) {
      throw ApiError.badRequest('برای تخصیص، انتخاب تکنسین الزامی است');
    }
    if (d.status === 'cancelled' && !d.cancelReason) {
      throw ApiError.badRequest('ذکر دلیل لغو الزامی است');
    }
    await OrderStatusLog.create({
      orderId: order.id, fromStatus: order.status, toStatus: d.status,
      note: d.note || null, byUserId: req.user.id,
    });
    if (d.status === 'completed') d.completedAt = new Date();
  }

  const updates = {};
  ['status', 'technicianId', 'estimatedCost', 'finalCost', 'adminNote', 'cancelReason', 'completedAt'].forEach((k) => {
    if (d[k] !== undefined) updates[k] = d[k];
  });
  await order.update(updates);
  res.json({ success: true, message: 'سفارش به‌روزرسانی شد', data: order });
});

const adminDashboardStats = ah(async (_req, res) => {
  /* Raw aggregate queries (simple & reliable for Postgres) */
  const todayStart = new Date(); todayStart.setHours(0, 0, 0, 0);
  const tomorrowStart = new Date(todayStart.getTime() + 24 * 3600 * 1000);

  const [byStatusRows, totalRow, todayRow, revenueRow, byAppliance, byCity] = await Promise.all([
    sequelize.query('SELECT status, COUNT(*)::int AS c FROM "Order" GROUP BY status'),
    sequelize.query('SELECT COUNT(*)::int AS c FROM "Order"'),
    sequelize.query('SELECT COUNT(*)::int AS c FROM "Order" WHERE created_at >= :start AND created_at < :end', {
      replacements: { start: todayStart, end: tomorrowStart },
    }),
    sequelize.query('SELECT COALESCE(SUM(final_cost), 0)::float AS s FROM "Order" WHERE status = \'completed\''),
    sequelize.query(`
      SELECT at.name_fa AS name, COUNT(o.id)::int AS count
      FROM "ApplianceType" at
      JOIN "Order" o ON o.appliance_type_id = at.id AND o.status != 'cancelled'
      GROUP BY at.id, at.name_fa ORDER BY count DESC LIMIT 6`),
    sequelize.query(`
      SELECT c.name_fa AS name, COUNT(o.id)::int AS count
      FROM "City" c
      JOIN "Order" o ON o.city_id = c.id
      GROUP BY c.id, c.name_fa ORDER BY count DESC LIMIT 8`),
  ]);

  const statusCounts = Object.fromEntries(byStatusRows[0].map((r) => [r.status, Number(r.c)]));
  res.json({
    success: true,
    data: {
      total: Number(totalRow[0][0].c),
      today: Number(todayRow[0][0].c),
      revenue: Number(revenueRow[0][0].s),
      statusCounts,
      topAppliances: byAppliance[0],
      topCities: byCity[0],
    },
  });
});

module.exports = {
  upload,
  createOrder, trackOrder, getOrdersByPhone, submitReview,
  adminListOrders, adminUpdateOrder, adminDashboardStats,
};
