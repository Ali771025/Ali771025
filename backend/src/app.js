require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const compression = require('compression');
const path = require('path');
const routes = require('./routes');
const { errorMiddleware, notFoundMiddleware } = require('./utils/errors');

const app = express();

app.set('trust proxy', 1);
app.use(helmet({ crossOriginResourcePolicy: { policy: 'cross-origin' } }));
app.use(compression());
app.use(cors({ origin: process.env.CLIENT_ORIGIN?.split(',') || true, credentials: true }));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));
if (process.env.NODE_ENV !== 'test') app.use(morgan('dev'));

/* Static uploads */
app.use('/uploads', express.static(path.join(__dirname, '../uploads'), { maxAge: '7d' }));

/* API */
app.use('/api/v1', routes);
app.get('/api/health', (_req, res) => res.json({ ok: true, ts: new Date().toISOString() }));

app.use(notFoundMiddleware);
app.use(errorMiddleware);

module.exports = app;
