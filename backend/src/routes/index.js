const router = require('express').Router();
const rateLimit = require('express-rate-limit');
const oc = require('../controllers/orderController');
const cc = require('../controllers/catalogController');
const ac = require('../controllers/authController');
const { validate, createOrderSchema, leadSchema, reviewSchema, loginSchema, adminOrderUpdateSchema } = require('../validators/schemas');
const { authenticate, requireRole } = require('../middleware/auth');

/* Rate limiters */
const orderLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 10, message: { success: false, message: 'تعداد درخواست‌ها زیاد است، لطفاً بعداً تلاش کنید' } });
const publicLimiter = rateLimit({ windowMs: 60 * 1000, max: 60 });

/* ------------------------------- Public: catalog ------------------------------ */
router.get('/provinces', cc.listProvinces);
router.get('/cities', cc.listCities);
router.get('/brands', cc.listBrands);
router.get('/appliance-types', cc.listApplianceTypes);
router.get('/faults', cc.listFaults);
router.get('/technicians', cc.listTechnicians);
router.get('/reviews', cc.listReviews);
router.get('/sitemap-data', cc.sitemapData);

/* --------------------------------- Orders (public) ---------------------------- */
router.post('/orders', publicLimiter, orderLimiter, validate(createOrderSchema), oc.upload.array('photos', 5), oc.createOrder);
router.get('/orders/track/:code', oc.trackOrder);
router.get('/orders/my', oc.getOrdersByPhone);
router.post('/reviews', orderLimiter, validate(reviewSchema), oc.submitReview);
router.post('/leads', orderLimiter, validate(leadSchema), cc.createLead);

/* ----------------------------------- Auth ------------------------------------- */
router.post('/auth/login', validate(loginSchema), ac.login);
router.get('/auth/me', authenticate, ac.me);

/* ----------------------------------- Admin ------------------------------------ */
router.get('/admin/orders', authenticate, requireRole('admin', 'dispatcher'), oc.adminListOrders);
router.patch('/admin/orders/:id', authenticate, requireRole('admin', 'dispatcher'), validate(adminOrderUpdateSchema), oc.adminUpdateOrder);
router.get('/admin/stats', authenticate, requireRole('admin', 'dispatcher'), oc.adminDashboardStats);

module.exports = router;
