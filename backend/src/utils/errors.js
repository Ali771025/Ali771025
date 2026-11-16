class ApiError extends Error {
  constructor(statusCode, message, details = undefined) {
    super(message);
    this.statusCode = statusCode;
    this.details = details;
  }
  static badRequest(msg = 'درخواست نامعتبر است', details) { return new ApiError(400, msg, details); }
  static notFound(msg = 'یافت نشد') { return new ApiError(404, msg); }
  static conflict(msg) { return new ApiError(409, msg); }
  static unauthorized(msg = 'نیاز به احراز هویت') { return new ApiError(401, msg); }
  static forbidden(msg = 'دسترسی غیرمجاز') { return new ApiError(403, msg); }
}

/** async handler wrapper */
const ah = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

/** Express error middleware */
function errorMiddleware(err, req, res, _next) {
  const status = err.statusCode || 500;
  if (status >= 500) console.error(err);
  res.status(status).json({
    success: false,
    message: err.message || 'خطای سرور',
    details: err.details,
  });
}

/** 404 handler */
function notFoundMiddleware(req, res) {
  res.status(404).json({ success: false, message: 'مسیر مورد نظر یافت نشد' });
}

module.exports = { ApiError, ah, errorMiddleware, notFoundMiddleware };
