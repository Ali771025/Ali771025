const crypto = require('crypto');

/** Generate short human-friendly tracking code, e.g. TRK-7G2K9Q */
function generateTrackingCode() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code = '';
  const bytes = crypto.randomBytes(6);
  for (let i = 0; i < 6; i++) code += alphabet[bytes[i] % alphabet.length];
  return `TRK-${code}`;
}

/** Convert Persian/Arabic digits to English digits */
function normalizeDigits(str = '') {
  return String(str)
    .replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}

/** Validate Iranian mobile: 09xxxxxxxxx */
function isValidIranMobile(phone) {
  return /^09\d{9}$/.test(normalizeDigits(phone).replace(/[\s-]/g, ''));
}

/** Simple transliteration-based slug for Latin names */
function slugify(str = '') {
  return str
    .toString()
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\u0600-\u06FFa-z0-9-]/g, '')
    .replace(/-+/g, '-');
}

/** Pagination helper */
function getPagination(query, defaultLimit = 20, maxLimit = 100) {
  const page = Math.max(parseInt(query.page, 10) || 1, 1);
  const limit = Math.min(Math.max(parseInt(query.limit, 10) || defaultLimit, 1), maxLimit);
  return { page, limit, offset: (page - 1) * limit };
}

module.exports = { generateTrackingCode, normalizeDigits, isValidIranMobile, slugify, getPagination };
