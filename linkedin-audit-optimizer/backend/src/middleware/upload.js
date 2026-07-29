import multer from 'multer';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB — matches the frontend's own check

const ALLOWED_EXTENSIONS = new Set([
  'pdf', 'doc', 'docx', 'xlsx', 'xls', 'csv',
  'png', 'jpg', 'jpeg', 'webp', 'gif',
]);

function fileFilter(req, file, cb) {
  const ext = file.originalname.split('.').pop().toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    cb(new Error(`Unsupported file type ".${ext}". Allowed: ${[...ALLOWED_EXTENSIONS].join(', ')}`));
    return;
  }
  cb(null, true);
}

export const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: MAX_FILE_SIZE },
  fileFilter,
});

export { MAX_FILE_SIZE, ALLOWED_EXTENSIONS };
