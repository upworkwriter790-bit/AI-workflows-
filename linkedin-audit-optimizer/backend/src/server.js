import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import auditRouter from './routes/audit.js';

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json({ limit: '1mb' }));

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.use('/api/audit', auditRouter);

// Multer/validation errors and anything unhandled land here as JSON,
// not the default HTML error page.
app.use((err, req, res, next) => {
  console.error(err);
  const status = err.status || 500;
  res.status(status).json({ error: err.message || 'Unexpected server error.' });
});

app.listen(PORT, () => {
  console.log(`LinkedIn Profile Audit API listening on port ${PORT}`);
});
