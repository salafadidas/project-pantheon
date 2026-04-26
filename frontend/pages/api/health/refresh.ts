import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000';

/**
 * Proxy: POST /api/health/refresh  →  backend POST /health/models/refresh
 *
 * Re-probes all LLM models on demand and returns the fresh health status.
 * Takes ~20 s in the worst case.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  try {
    const upstream = await fetch(`${BACKEND_URL}/health/models/refresh`, {
      method: 'POST',
    });
    const data = await upstream.json();
    return res.status(upstream.status).json(data);
  } catch (err) {
    console.error('[api/health/refresh] upstream error:', err);
    return res.status(502).json({ detail: 'Could not reach backend' });
  }
}
