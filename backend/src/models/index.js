const { DataTypes } = require('sequelize');
const sequelize = require('../config/database');

/* ----------------------------- User (staff/admin) ---------------------------- */
const User = sequelize.define('User', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  fullName: { type: DataTypes.STRING(120), allowNull: false },
  email: { type: DataTypes.STRING(160), allowNull: false, unique: true, validate: { isEmail: true } },
  passwordHash: { type: DataTypes.STRING, allowNull: false },
  role: { type: DataTypes.ENUM('admin', 'dispatcher', 'technician'), defaultValue: 'dispatcher' },
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* --------------------------------- Brand ------------------------------------ */
const Brand = sequelize.define('Brand', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  nameFa: { type: DataTypes.STRING(80), allowNull: false },           // سامسونگ
  nameEn: { type: DataTypes.STRING(80), allowNull: false },           // Samsung
  slug: { type: DataTypes.STRING(90), allowNull: false, unique: true },
  logoUrl: DataTypes.STRING(300),
  hasServiceCenter: { type: DataTypes.BOOLEAN, defaultValue: true },  // نمایندگی مجاز
  sortOrder: { type: DataTypes.INTEGER, defaultValue: 0 },
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* ------------------------------ ApplianceType ------------------------------- */
const ApplianceType = sequelize.define('ApplianceType', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  nameFa: { type: DataTypes.STRING(80), allowNull: false },   // یخچال ساید بای ساید
  slug: { type: DataTypes.STRING(90), allowNull: false, unique: true },
  category: { type: DataTypes.ENUM('refrigerator', 'washing_machine', 'dishwasher'), allowNull: false },
  icon: DataTypes.STRING(60),
  descriptionFa: DataTypes.TEXT,
  basePriceMin: DataTypes.DECIMAL(12, 0),  // بازه قیمت تقریبی خدمات (تومان)
  basePriceMax: DataTypes.DECIMAL(12, 0),
  sortOrder: { type: DataTypes.INTEGER, defaultValue: 0 },
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* ------------------------------ FaultCategory ------------------------------- */
const FaultCategory = sequelize.define('FaultCategory', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  nameFa: { type: DataTypes.STRING(120), allowNull: false },  // یخ نزنی فریزر
  slug: { type: DataTypes.STRING(130), allowNull: false, unique: true },
  descriptionFa: DataTypes.TEXT,
  isCommon: { type: DataTypes.BOOLEAN, defaultValue: false },
  sortOrder: { type: DataTypes.INTEGER, defaultValue: 0 },
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* Junction: which faults apply to which appliance types */
const ApplianceTypeFault = sequelize.define('ApplianceTypeFault', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
});

/* -------------------------------- Province ---------------------------------- */
const Province = sequelize.define('Province', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  nameFa: { type: DataTypes.STRING(80), allowNull: false },
  slug: { type: DataTypes.STRING(90), allowNull: false, unique: true },
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* --------------------------------- City ------------------------------------- */
const City = sequelize.define('City', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  nameFa: { type: DataTypes.STRING(80), allowNull: false },
  slug: { type: DataTypes.STRING(90), allowNull: false },
  hasCoverage: { type: DataTypes.BOOLEAN, defaultValue: true }, // تحت پوشش شعبه
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* -------------------------------- Technician -------------------------------- */
const Technician = sequelize.define('Technician', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  fullName: { type: DataTypes.STRING(120), allowNull: false },
  phone: { type: DataTypes.STRING(20), allowNull: false },
  rating: { type: DataTypes.FLOAT, defaultValue: 5 },
  specializations: { type: DataTypes.ARRAY(DataTypes.STRING), defaultValue: [] }, // appliance slugs
  cityId: { type: DataTypes.UUID, allowNull: true },
  isActive: { type: DataTypes.BOOLEAN, defaultValue: true },
});

/* --------------------------------- Order ------------------------------------ */
const ORDER_STATUS = ['pending', 'confirmed', 'assigned', 'in_progress', 'completed', 'cancelled'];

const Order = sequelize.define('Order', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  trackingCode: { type: DataTypes.STRING(16), allowNull: false, unique: true }, // e.g. TRK-8F3K2A
  serviceType: { type: DataTypes.ENUM('repair', 'installation', 'warranty'), allowNull: false },

  /* Customer */
  customerName: { type: DataTypes.STRING(120), allowNull: false },
  customerPhone: { type: DataTypes.STRING(20), allowNull: false },
  customerMobile: DataTypes.STRING(20),
  nationalId: DataTypes.STRING(10),
  postalCode: DataTypes.STRING(12),

  /* Location */
  provinceId: { type: DataTypes.UUID, allowNull: false },
  cityId: { type: DataTypes.UUID, allowNull: false },
  address: { type: DataTypes.TEXT, allowNull: false },
  latitude: DataTypes.DECIMAL(10, 7),
  longitude: DataTypes.DECIMAL(10, 7),

  /* Appliance */
  applianceTypeId: { type: DataTypes.UUID, allowNull: false },
  brandId: { type: DataTypes.UUID, allowNull: false },
  faultCategoryId: { type: DataTypes.UUID, allowNull: true },
  deviceModel: DataTypes.STRING(120),      // مدل دستگاه
  purchaseDate: DataTypes.DATEONLY,        // تاریخ خرید (برای گارانتی)
  warrantyCode: DataTypes.STRING(60),      // کد کارت گارانتی
  problemDescription: DataTypes.TEXT,

  /* Scheduling */
  preferredDate: DataTypes.DATEONLY,
  preferredTimeSlot: DataTypes.ENUM('morning', 'afternoon', 'evening'),

  /* Lifecycle */
  status: { type: DataTypes.ENUM(...ORDER_STATUS), defaultValue: 'pending' },
  adminNote: DataTypes.TEXT,
  estimatedCost: DataTypes.DECIMAL(12, 0),
  finalCost: DataTypes.DECIMAL(12, 0),
  technicianId: { type: DataTypes.UUID, allowNull: true },
  completedAt: DataTypes.DATE,
  cancelReason: DataTypes.TEXT,

  /* Source / SEO analytics */
  utmSource: DataTypes.STRING(80),
  utmMedium: DataTypes.STRING(80),
  utmCampaign: DataTypes.STRING(80),
  landingPage: DataTypes.STRING(300),
  userAgent: DataTypes.STRING(300),
});

/* Order photos (uploaded via multer) */
const OrderPhoto = sequelize.define('OrderPhoto', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  orderId: { type: DataTypes.UUID, allowNull: false },
  url: { type: DataTypes.STRING(400), allowNull: false },
  caption: DataTypes.STRING(200),
});

/* Status history timeline */
const OrderStatusLog = sequelize.define('OrderStatusLog', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  orderId: { type: DataTypes.UUID, allowNull: false },
  fromStatus: DataTypes.STRING(30),
  toStatus: { type: DataTypes.STRING(30), allowNull: false },
  note: DataTypes.TEXT,
  byUserId: { type: DataTypes.UUID, allowNull: true },
});

/* Review / satisfaction */
const Review = sequelize.define('Review', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  orderId: { type: DataTypes.UUID, allowNull: false },
  customerName: DataTypes.STRING(120),
  rating: { type: DataTypes.INTEGER, validate: { min: 1, max: 5 } },
  comment: DataTypes.TEXT,
  isPublished: { type: DataTypes.BOOLEAN, defaultValue: false },
});

/* Simple contact/inquiry leads (SEO landing pages CTA) */
const Lead = sequelize.define('Lead', {
  id: { type: DataTypes.UUID, defaultValue: DataTypes.UUIDV4, primaryKey: true },
  name: DataTypes.STRING(120),
  phone: { type: DataTypes.STRING(20), allowNull: false },
  message: DataTypes.TEXT,
  sourcePage: DataTypes.STRING(300),
  isProcessed: { type: DataTypes.BOOLEAN, defaultValue: false },
});

/* ------------------------------- Associations ------------------------------- */
Province.hasMany(City, { foreignKey: 'provinceId' });
City.belongsTo(Province, { as: 'province' });

ApplianceType.belongsToMany(FaultCategory, { through: ApplianceTypeFault, foreignKey: 'applianceTypeId', otherKey: 'faultCategoryId', as: 'faults' });
FaultCategory.belongsToMany(ApplianceType, { through: ApplianceTypeFault, foreignKey: 'faultCategoryId', otherKey: 'applianceTypeId', as: 'applianceTypes' });

Order.belongsTo(Province, { as: 'province' });
Order.belongsTo(City, { as: 'city' });
Order.belongsTo(ApplianceType, { as: 'applianceType' });
Order.belongsTo(Brand, { as: 'brand' });
Order.belongsTo(FaultCategory, { as: 'faultCategory' });
Order.belongsTo(Technician, { as: 'technician' });
Order.hasMany(OrderPhoto, { as: 'photos', foreignKey: 'orderId' });
OrderPhoto.belongsTo(Order, { foreignKey: 'orderId' });
Order.hasMany(OrderStatusLog, { as: 'statusLogs', foreignKey: 'orderId' });
OrderStatusLog.belongsTo(Order, { foreignKey: 'orderId' });
Order.hasOne(Review, { as: 'review', foreignKey: 'orderId' });
Review.belongsTo(Order, { foreignKey: 'orderId' });
Technician.belongsTo(City, { as: 'city' });

module.exports = {
  sequelize,
  User, Brand, ApplianceType, FaultCategory, ApplianceTypeFault,
  Province, City, Technician, Order, OrderPhoto, OrderStatusLog,
  Review, Lead, ORDER_STATUS,
};
