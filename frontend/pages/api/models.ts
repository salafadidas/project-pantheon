import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000';

/**
 * Proxy: GET /api/models  →  backend GET /api/v1/models
 *
 * Returns the full model catalog (pricing, token estimates, availability)
 * so the frontend never calls the backend directly.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  try {
    const upstream = await fetch(`${BACKEND_URL}/api/v1/models`);
    const data = await upstream.json();
    return res.status(upstream.status).json(data);
  } catch (err) {
    console.error('[api/models] upstream error:', err);
    return res.status(502).json({ detail: 'Could not reach backend' });
  }
}
