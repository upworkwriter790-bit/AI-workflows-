import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const MODEL = process.env.ANTHROPIC_MODEL || 'claude-sonnet-5';

const SYSTEM_PROMPT = `You are a senior LinkedIn profile auditor. You review LinkedIn profile
content (headline, About section, experience bullets, skills, etc.) exactly as a strict but
constructive editor would, and you always ground your findings in the exact wording you were
given rather than generic advice.

Score the profile 0-100 and assign it to exactly one band using these ranges:
- 0-32: "Very Poor"
- 33-49: "Poor"
- 50-74: "Good" (solid, but there is clear room to improve)
- 75-100: "Very Good" (already strong, can be optimized further toward 95+)

Be honest and specific. Do not inflate the score. If the content is generic, vague, full of
buzzwords with no evidence/results, poorly formatted, or too short to judge, say so plainly and
score accordingly.

For every weakness you list, you must quote the exact phrase or sentence from the supplied
content that caused it (verbatim, in "flagged_text") — never a paraphrase — and explain
specifically why it hurts (e.g. vague buzzword with no proof, no quantified result, generic
objective statement, wall of text with no line breaks, missing keywords a recruiter would search
for, passive/weak verbs, etc).

For strengths and engagement highlights, do the same: quote the specific phrase that is working
well and say why it helps engagement/credibility (e.g. quantified achievement, strong action
verb, specific and searchable skill, clear value proposition).

Recommendations must be concrete rewrites or specific actions tied to the flagged issues, not
generic tips — written so that applying them would plausibly move the score toward 95+.

If the supplied material is too thin to audit at all (e.g. only a bare link with no readable
profile text, or an empty/corrupt file), say so directly in "summary", set "score" to 0, and
explain in "weaknesses" exactly what's missing so the user knows what to provide instead.`;

const REPORT_TOOL = {
  name: 'submit_audit_report',
  description: 'Submit the structured LinkedIn profile audit report.',
  input_schema: {
    type: 'object',
    properties: {
      score: { type: 'integer', minimum: 0, maximum: 100 },
      band: { type: 'string', enum: ['Very Poor', 'Poor', 'Good', 'Very Good'] },
      summary: {
        type: 'string',
        description: '2-4 sentence plain-English verdict on the overall quality of the content.',
      },
      strengths: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            point: { type: 'string' },
            flagged_text: { type: 'string' },
          },
          required: ['point', 'flagged_text'],
        },
      },
      engagement_highlights: {
        type: 'array',
        description: 'Specific elements likely to drive profile views, connection requests, or replies.',
        items: {
          type: 'object',
          properties: {
            point: { type: 'string' },
            flagged_text: { type: 'string' },
          },
          required: ['point', 'flagged_text'],
        },
      },
      weaknesses: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            issue: { type: 'string' },
            flagged_text: { type: 'string' },
            why_it_hurts: { type: 'string' },
          },
          required: ['issue', 'flagged_text', 'why_it_hurts'],
        },
      },
      recommendations: {
        type: 'array',
        items: { type: 'string' },
      },
    },
    required: ['score', 'band', 'summary', 'strengths', 'engagement_highlights', 'weaknesses', 'recommendations'],
  },
};

/**
 * @param {{ link?: string, pastedContent?: string, fileResult?: { kind: 'text'|'image', text?: string, base64?: string, mediaType?: string, filename?: string } }} input
 */
export async function generateAuditReport({ link, pastedContent, fileResult }) {
  const textParts = [];
  if (link) textParts.push(`Reference link provided by the user (not fetched live): ${link}`);
  if (pastedContent) textParts.push(`Pasted content:\n${pastedContent}`);
  if (fileResult?.kind === 'text') {
    textParts.push(`Content extracted from uploaded file "${fileResult.filename}":\n${fileResult.text}`);
  }

  const content = [];
  if (textParts.length) {
    content.push({ type: 'text', text: textParts.join('\n\n---\n\n') });
  }
  if (fileResult?.kind === 'image') {
    content.push({
      type: 'text',
      text: `The user also uploaded an image file "${fileResult.filename}" (e.g. a screenshot of their LinkedIn profile). Read all visible profile text in it and audit that content too.`,
    });
    content.push({
      type: 'image',
      source: { type: 'base64', media_type: fileResult.mediaType, data: fileResult.base64 },
    });
  }

  if (content.length === 0) {
    content.push({ type: 'text', text: 'No content, link, or file was provided.' });
  }

  const message = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    tools: [REPORT_TOOL],
    tool_choice: { type: 'tool', name: 'submit_audit_report' },
    messages: [{ role: 'user', content }],
  });

  const toolUse = message.content.find((block) => block.type === 'tool_use');
  if (!toolUse) {
    throw new Error('Claude did not return a structured audit report.');
  }
  return toolUse.input;
}
