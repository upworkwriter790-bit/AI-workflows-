import mammoth from 'mammoth';
import readExcelFile from 'read-excel-file/node';
import pdfParse from 'pdf-parse';

const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif']);
const IMAGE_MEDIA_TYPES = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  gif: 'image/gif',
};

/**
 * Turns an uploaded file into either extracted text or a base64 image block,
 * so the caller can hand it straight to Claude as a content block.
 */
export async function extractFileContent(file) {
  const ext = file.originalname.split('.').pop().toLowerCase();

  if (IMAGE_EXTENSIONS.has(ext)) {
    return {
      kind: 'image',
      mediaType: IMAGE_MEDIA_TYPES[ext],
      base64: file.buffer.toString('base64'),
      filename: file.originalname,
    };
  }

  if (ext === 'csv' || ext === 'txt') {
    return { kind: 'text', text: file.buffer.toString('utf-8'), filename: file.originalname };
  }

  if (ext === 'xlsx') {
    const sheets = await readExcelFile(file.buffer);
    const sheetsText = sheets.map(({ sheet, data }) => {
      const rows = data.map((row) => row.map((cell) => (cell ?? '').toString()).join(', '));
      return `--- Sheet: ${sheet} ---\n${rows.join('\n')}`;
    }).join('\n\n');
    return { kind: 'text', text: sheetsText, filename: file.originalname };
  }

  if (ext === 'xls') {
    // read-excel-file only reads the modern .xlsx (OOXML) format, not the
    // legacy binary .xls format. Ask the user to re-save instead of pulling
    // in a second, less-maintained parser just for this edge case.
    return {
      kind: 'text',
      text: '[Could not read this legacy .xls file. Please re-save it as .xlsx or .csv and re-upload.]',
      filename: file.originalname,
    };
  }

  if (ext === 'docx') {
    const { value } = await mammoth.extractRawText({ buffer: file.buffer });
    return { kind: 'text', text: value, filename: file.originalname };
  }

  if (ext === 'doc') {
    // mammoth only reliably handles .docx; legacy .doc is a different binary
    // format. Try anyway and fall back to a clear message instead of crashing.
    try {
      const { value } = await mammoth.extractRawText({ buffer: file.buffer });
      if (value.trim()) return { kind: 'text', text: value, filename: file.originalname };
    } catch {
      // fall through to the message below
    }
    return {
      kind: 'text',
      text: '[Could not extract text from this legacy .doc file. Please re-save it as .docx or .pdf and re-upload.]',
      filename: file.originalname,
    };
  }

  if (ext === 'pdf') {
    const { text } = await pdfParse(file.buffer);
    return { kind: 'text', text, filename: file.originalname };
  }

  throw new Error(`Unsupported file type ".${ext}"`);
}
