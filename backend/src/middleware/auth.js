const jwt = require('jsonwebtoken');
const { ApiError } = require('../utils/errors');
const { User } = require('../models');

/** Verify JWT from Authorization header */
async function authenticate(req, _res, next) {
  try {
    const header = req.headers.authorization || '';
    const token = header.startsWith('Bearer ') ? header.slice(7) : null;
    if (!token) throw ApiError.unauthorized();
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    const user = await User.findByPk(payload.sub);
    if (!user || !user.isActive) throw ApiError.unauthorized('کاربر غیرفعال است');
    req.user = user;
    next();
  } catch (e) {
    next(e.name === 'JsonWebTokenError' || e.name === 'TokenExpiredError' ? ApiError.unauthorized() : e);
  }
}

/** Role guard */
function requireRole(...roles) {
  return (req, _res, next) => {
    if (!req.user || !roles.includes(req.user.role)) return next(ApiError.forbidden());
    next();
  };
}

module.exports = { authenticate, requireRole };
