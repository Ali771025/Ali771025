const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { User } = require('../models');
const { ApiError, ah } = require('../utils/errors');

const login = ah(async (req, res) => {
  const { email, password } = req.validated;
  const user = await User.findOne({ where: { email } });
  if (!user || !user.isActive) throw ApiError.unauthorized('ایمیل یا رمز عبور اشتباه است');
  const ok = await bcrypt.compare(password, user.passwordHash);
  if (!ok) throw ApiError.unauthorized('ایمیل یا رمز عبور اشتباه است');
  const token = jwt.sign({ sub: user.id, role: user.role }, process.env.JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || '7d',
  });
  res.json({
    success: true,
    data: { token, user: { id: user.id, fullName: user.fullName, email: user.email, role: user.role } },
  });
});

const me = ah(async (req, res) => {
  const { id, fullName, email, role } = req.user;
  res.json({ success: true, data: { id, fullName, email, role } });
});

module.exports = { login, me };
