const { Op } = require('sequelize');
const {
  Province, City, ApplianceType, Brand, FaultCategory, Technician, Review, Lead, sequelize,
} = require('../models');
const { ApiError, ah } = require('../utils/errors');

/* Public catalog endpoints — cached & SEO-friendly */

const listProvinces = ah(async (_req, res) => {
  const rows = await Province.findAll({
    where: { isActive: true },
    attributes: ['id', 'nameFa', 'slug'],
    order: [['nameFa', 'ASC']],
  });
  res.json({ success: true, data: rows });
});

const listCities = ah(async (req, res) => {
  const where = { isActive: true, hasCoverage: true };
  if (req.query.provinceId) where.provinceId = req.query.provinceId;
  const rows = await City.findAll({
    where,
    attributes: ['id', 'nameFa', 'slug', 'provinceId'],
    include: [{ model: Province, as: 'province', attributes: ['nameFa'] }],
    order: [['nameFa', 'ASC']],
  });
  res.json({ success: true, data: rows });
});

const listBrands = ah(async (_req, res) => {
  const rows = await Brand.findAll({
    where: { isActive: true },
    attributes: ['id', 'nameFa', 'nameEn', 'slug', 'logoUrl', 'hasServiceCenter'],
    order: [['sortOrder', 'ASC'], ['nameFa', 'ASC']],
  });
  res.json({ success: true, data: rows });
});

const listApplianceTypes = ah(async (req, res) => {
  const where = { isActive: true };
  if (req.query.category) where.category = req.query.category;
  const rows = await ApplianceType.findAll({
    where,
    order: [['sortOrder', 'ASC']],
    include: req.query.withFaults
      ? [{ model: FaultCategory, as: 'faults', through: { attributes: [] }, where: { isActive: true }, required: false }]
      : [],
  });
  res.json({ success: true, data: rows });
});

const listFaults = ah(async (req, res) => {
  let rows;
  if (req.query.applianceTypeId) {
    const appliance = await ApplianceType.findByPk(req.query.applianceTypeId, {
      include: [{ model: FaultCategory, as: 'faults', through: { attributes: [] } }],
    });
    if (!appliance) throw ApiError.notFound('دستگاه یافت نشد');
    rows = appliance.faults.filter((f) => f.isActive);
  } else {
    rows = await FaultCategory.findAll({
      where: { isActive: true },
      order: [['sortOrder', 'ASC']],
    });
  }
  res.json({ success: true, data: rows });
});

const listTechnicians = ah(async (_req, res) => {
  const rows = await Technician.findAll({
    where: { isActive: true },
    attributes: ['id', 'fullName', 'rating', 'specializations'],
    include: [{ model: City, as: 'city', attributes: ['nameFa'] }],
    order: [['rating', 'DESC']],
  });
  res.json({ success: true, data: rows });
});

const listReviews = ah(async (_req, res) => {
  const rows = await Review.findAll({
    where: { isPublished: true },
    attributes: ['customerName', 'rating', 'comment', 'createdAt'],
    order: [['created_at', 'DESC']],
    limit: 12,
  });
  res.json({ success: true, data: rows });
});

const createLead = ah(async (req, res) => {
  const lead = await Lead.create(req.validated);
  res.status(201).json({ success: true, message: 'درخواست شما ثبت شد، کارشناسان ما به‌زودی تماس می‌گیرند', data: { id: lead.id } });
});

/** Aggregated sitemap data for SEO (pages to generate) */
const sitemapData = ah(async (_req, res) => {
  const [brands, appliances, cities, faults] = await Promise.all([
    Brand.findAll({ where: { isActive: true }, attributes: ['slug', 'updatedAt'] }),
    ApplianceType.findAll({ where: { isActive: true }, attributes: ['slug', 'updatedAt'] }),
    City.findAll({ where: { isActive: true, hasCoverage: true }, attributes: ['slug', 'updatedAt'] }),
    FaultCategory.findAll({ where: { isActive: true }, attributes: ['slug', 'updatedAt'] }),
  ]);
  res.json({ success: true, data: { brands, appliances, cities, faults } });
});

module.exports = {
  listProvinces, listCities, listBrands, listApplianceTypes,
  listFaults, listTechnicians, listReviews, createLead, sitemapData,
};
