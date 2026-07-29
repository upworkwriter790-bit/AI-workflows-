import { Router } from 'express';
import { upload } from '../middleware/upload.js';
import { extractFileContent } from '../services/fileParser.js';
import { generateAuditReport } from '../services/claudeAudit.js';

const router = Router();

router.post('/', (req, res, next) => {
  upload.single('file')(req, res, async (err) => {
    if (err) {
      // Includes Multer's LIMIT_FILE_SIZE error for anything over 5MB.
      return res.status(400).json({ error: err.message });
    }

    try {
      const { link, content } = req.body;
      const file = req.file;

      if (!link && !content && !file) {
        return res.status(400).json({
          error: 'Provide a link, some pasted content, or upload a file before running the audit.',
        });
      }

      const fileResult = file ? await extractFileContent(file) : undefined;

      const report = await generateAuditReport({
        link: link?.trim() || undefined,
        pastedContent: content?.trim() || undefined,
        fileResult,
      });

      res.json(report);
    } catch (error) {
      next(error);
    }
  });
});

export default router;
