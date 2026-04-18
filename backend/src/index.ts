import express, { Express, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import dotenv from 'dotenv';
import searchRouter from './routes/search';
import autocompleteRouter from './routes/autocomplete';

dotenv.config();

const app: Express = express();
const PORT = process.env.PORT || 3001;

// Trust proxy is required for rate limiting behind reverse proxies (Render, Vercel, Heroku)
app.set('trust proxy', 1);

// Middleware
app.use(helmet());
// CORS configuration - supports both development and production
const allowedOrigins = process.env.CORS_ORIGINS
    ? process.env.CORS_ORIGINS.split(',').map(o => o.trim())
    : ['http://localhost:3000', 'http://localhost:3002'];

app.use(cors({
    origin: allowedOrigins,
    credentials: true
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Rate limiting - separate limiters for different endpoints
const searchLimiter = rateLimit({
    windowMs: 60 * 1000, // 1 minute
    max: 30, // 30 requests per minute for search
    message: 'Too many search requests from this IP, please try again later.',
    standardHeaders: true,
    legacyHeaders: false,
});

const autocompleteLimiter = rateLimit({
    windowMs: 60 * 1000, // 1 minute
    max: 100, // 100 requests per minute for autocomplete (fires on each keystroke)
    message: 'Too many autocomplete requests from this IP, please try again later.',
    standardHeaders: true,
    legacyHeaders: false,
});

// Routes
app.get('/', (_req: Request, res: Response) => {
    res.json({
        name: 'Financial Report Finder API',
        version: '1.0.0',
        endpoints: {
            health: '/health',
            search: '/api/search',
            autocomplete: '/api/autocomplete'
        }
    });
});

app.get('/api', (_req: Request, res: Response) => {
    res.json({
        message: 'Financial Report Finder API',
        endpoints: {
            search: 'POST /api/search - Search for financial documents',
            autocomplete: 'GET /api/autocomplete?q=query - Get company suggestions'
        }
    });
});

app.get('/health', (_req: Request, res: Response) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use('/api/search', searchLimiter, searchRouter);
app.use('/api/autocomplete', autocompleteLimiter, autocompleteRouter);

// Global error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    console.error('Error:', err);
    res.status(500).json({
        error: 'Internal Server Error',
        message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
    });
});

// 404 handler
app.use((_req: Request, res: Response) => {
    res.status(404).json({ error: 'Route not found' });
});

// Start server
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

export default app;
