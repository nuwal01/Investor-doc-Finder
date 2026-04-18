import { Router, Request, Response } from 'express';
import { searchCompanies } from '../data/sp500';

const router = Router();

/**
 * GET /api/autocomplete
 * Returns company suggestions based on a query string
 * 
 * Query Parameters:
 *   - q: Search query (required, min 1 character)
 *   - limit: Maximum number of results (optional, default 10, max 20)
 * 
 * Response:
 *   - suggestions: Array of { name, ticker, cik } objects
 */
router.get('/', (req: Request, res: Response): void => {
    try {
        const query = req.query.q as string;
        const limit = Math.min(parseInt(req.query.limit as string, 10) || 10, 20);

        if (!query || query.length < 1) {
            res.status(400).json({
                error: 'Invalid query',
                message: 'Query parameter "q" is required and must be at least 1 character'
            });
            return;
        }

        const companies = searchCompanies(query, limit);

        res.json({
            query,
            suggestions: companies.map(c => ({
                name: c.name,
                ticker: c.ticker,
                cik: c.cik
            })),
            count: companies.length
        });

    } catch (error) {
        console.error('Autocomplete error:', error);
        res.status(500).json({
            error: 'Autocomplete failed',
            message: error instanceof Error ? error.message : 'Unknown error occurred'
        });
    }
});

export default router;
