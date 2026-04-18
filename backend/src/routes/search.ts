import { Router, Request, Response } from 'express';
import { parseQuery } from '../services/queryParser';
import { searchDocumentsExtended } from '../services/documentSearch';

const router = Router();

// POST /api/search
router.post('/', async (req: Request, res: Response): Promise<void> => {
    try {
        const { query } = req.body;

        if (!query || typeof query !== 'string' || query.trim().length === 0) {
            res.status(400).json({
                success: false,
                error: 'Invalid query',
                message: 'Query parameter is required and must be a non-empty string'
            });
            return;
        }

        // Parse the natural language query
        const parsedQuery = await parseQuery(query);

        console.log('Original query:', query);
        console.log('Parsed query:', JSON.stringify(parsedQuery, null, 2));

        if (!parsedQuery.company) {
            res.status(400).json({
                success: false,
                error: 'Could not parse query',
                message: 'Unable to identify company name from query. Please try rephrasing.',
                notes: 'We could not extract a company name from your search. Try using the full company name.'
            });
            return;
        }

        // Search for documents using OFFICIAL WEBSITE ONLY
        const searchResult = await searchDocumentsExtended(parsedQuery);

        res.json({
            success: searchResult.success,
            query: query,
            parsed: parsedQuery,
            company: searchResult.company,
            requestedReport: searchResult.requestedReport,
            officialWebsite: searchResult.officialWebsite,
            reportsPage: searchResult.reportsPage,
            results: searchResult.results,
            notes: searchResult.notes,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('Search error:', error);
        res.status(500).json({
            success: false,
            error: 'Search failed',
            message: error instanceof Error ? error.message : 'Unknown error occurred',
            notes: 'An unexpected error occurred. Please try again.'
        });
    }
});

export default router;
