# Word to PDF Converter

A sophisticated, full-stack web application engineered to transform Word documents (.doc, .docx) into professional PDF format, featuring an intuitive user interface complemented by robust serverless backend architecture.

[![Author](https://img.shields.io/badge/Author-Nayan%20Das-blue?style=flat-square)](https://github.com/nayandas69)
[![GitHub stars](https://img.shields.io/github/stars/nayandas69/word-to-pdf-converter?style=flat-square)](https://github.com/nayandas69/word-to-pdf-converter/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/nayandas69/word-to-pdf-converter?style=flat-square)](https://github.com/nayandas69/word-to-pdf-converter/network)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Discord](https://img.shields.io/discord/1435329767149797461?label=Join%20Discord&logo=discord&color=5865F2)](https://discord.gg/u9XfHZN8K9)

## Overview

This application demonstrates modern web development practices through a comprehensive document conversion solution. The frontend leverages React's component-based architecture whilst the backend utilises Express.js within a serverless paradigm, specifically optimised for Vercel's cloud infrastructure.

## Key Features

- Instantaneous Word document to PDF transformation
- Intuitive drag-and-drop file upload mechanism
- Real-time conversion progress monitoring
- Automated file retrieval following successful conversion
- Responsive design optimised across diverse device specifications
- Secure file management with automatic resource cleanup
- Comprehensive support for .doc and .docx file formats
- File size validation enforcing 10MB threshold
- Contemporary user interface incorporating fluid animations
- Toast notification system providing immediate user feedback
- Rate limiting mechanisms safeguarding API integrity
- Cross-Origin Resource Sharing (CORS) and security middleware implementation

## Technical Architecture

### Frontend Technology Stack
- **React 18** - Contemporary React framework utilising hooks and functional components
- **Vite** - High-performance build tool and development server
- **Tailwind CSS** - Utility-first CSS framework for rapid interface development
- **Axios** - Promise-based HTTP client for API communication
- **React Hot Toast** - Elegant toast notification library
- **React Icons** - Comprehensive iconography collection

### Backend Technology Stack
- **Node.js** - JavaScript runtime environment
- **Express.js** - Minimalist web application framework
- **Multer** - Middleware facilitating multipart/form-data file uploads
- **Mammoth** - Library extracting textual content from Word documents
- **PDF-lib** - Sophisticated PDF document creation library
- **Helmet** - Security middleware establishing protective HTTP headers
- **CORS** - Cross-Origin Resource Sharing middleware
- **Express Rate Limit** - Request throttling middleware

## System Prerequisites

Prior to installation, ensure the following dependencies are satisfied:

- **Node.js**: Version 18.x or subsequent release
- **npm**: Version 8.x or subsequent release

Verify installed versions via terminal:
```bash
node -v
npm -v
```

## Installation Procedure

### Repository Cloning

```bash
git clone https://github.com/nayandas69/word-to-pdf-converter.git
cd word-to-pdf-converter
```

### Dependency Installation

Install dependencies across all project segments (root, backend, frontend):

```bash
npm run install-deps
```

This command executes the following operations:
- Root dependency installation
- Backend dependency installation
- Frontend dependency installation

### Environment Configuration

The backend requires environment variables for operational configuration. A default `.env` file exists within the backend directory configured for development:

```env
# Server Configuration
PORT=3000
NODE_ENV=development

# CORS Configuration
FRONTEND_URL=http://localhost:5173

# File Upload Configuration
MAX_FILE_SIZE=10485760
ALLOWED_FILE_TYPES=.doc,.docx

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

For production deployment, modify the `FRONTEND_URL` parameter to correspond with your deployed frontend URL.

## Development Workflow

### Concurrent Development Servers

Execute both frontend and backend development servers simultaneously:

```bash
npm run dev
```

This initiates:
- **Backend server**: http://localhost:3000
- **Frontend server**: http://localhost:5173

### Individual Server Commands

Backend server exclusively:
```bash
npm run server
```

Frontend client exclusively:
```bash
npm run client
```

## API Documentation

### Health Status Endpoint
```http
GET /health
```
Returns API operational status and version information.

**Response Structure:**
```json
{
  "status": "OK",
  "message": "Word to PDF Converter API is running",
  "timestamp": "2025-12-30T08:25:02.985Z",
  "version": "1.0.0",
  "endpoints": {
    "health": "/health",
    "convert": "/convert (POST)"
  }
}
```

### Document Conversion Endpoint
```http
POST /convert
```

**Request Specification:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: Form data containing `file` field with Word document

**Response Specification:**
- Success: Binary PDF file stream
- Error: JSON-formatted error message

**cURL Example:**
```bash
curl -X POST \
  https://<your-domain>/convert \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/document.docx'
```

## Deployment Architecture

### Serverless Backend Configuration

The backend has undergone substantial architectural modifications to accommodate Vercel's serverless function paradigm:

**Major Architectural Changes:**
1. **Serverless Function Adaptation** - Transformed traditional Express server into serverless-compatible export
2. **File System Modifications** - Migrated from persistent storage to ephemeral `/tmp` directory
3. **Route Configuration** - Restructured routing to eliminate `/api` prefix duplication
4. **Lifecycle Management** - Removed long-running processes incompatible with serverless execution
5. **Entry Point Creation** - Established `api/index.js` as Vercel function entry point

**Critical Implementation Notes:**
- The `app.listen()` invocation remains commented in production code
- File storage utilises `/tmp` directory exclusively in serverless environment
- Background cleanup processes have been disabled for serverless compatibility
- Maximum execution duration constrained by Vercel's function timeout limits

### Frontend Deployment

The frontend application requires static hosting infrastructure:

1. **Build Production Assets:**
   ```bash
   cd frontend
   npm run build
   ```

2. **Deploy Compiled Assets** - Upload `dist` directory to hosting provider (Vercel, Netlify, Cloudflare Pages)

3. **Environment Configuration** - Update API base URL to reference deployed backend endpoint

### Backend Deployment to Vercel

1. **Repository Integration:**
   - Link GitHub repository to Vercel dashboard
   - Import project and configure deployment settings

2. **Configuration Parameters:**
   - Set Root Directory: `backend`
   - Configure Build Command: Leave empty (auto-detected)
   - Configure Output Directory: Leave empty

3. **Environment Variables:**
   Navigate to Vercel project settings and configure:
   - `NODE_ENV=production`
   - `FRONTEND_URL=https://your-frontend-domain.vercel.app`
   - `MAX_FILE_SIZE=10485760`
   - `ALLOWED_FILE_TYPES=.doc,.docx`
   - `RATE_LIMIT_WINDOW_MS=900000`
   - `RATE_LIMIT_MAX_REQUESTS=100`

4. **Deployment Execution:**
   - Commit changes to repository
   - Vercel automatically triggers deployment pipeline
   - Monitor deployment logs for successful completion

**Serverless Constraints:**
- Function execution timeout: 10 seconds (Hobby tier), 60 seconds (Pro tier)
- Request payload limitation: 4.5MB (Hobby tier)
- Ephemeral file system: `/tmp` directory only
- No persistent storage without external service integration

### Alternative Backend Hosting Solutions

For applications requiring extended execution duration or persistent storage:

- **Railway**: Supports persistent storage and prolonged execution periods
- **Render**: Complimentary tier with comprehensive Node.js support
- **Fly.io**: Global distribution with persistent volume capabilities
- **DigitalOcean App Platform**: Scalable infrastructure with persistent storage options

## Security Implementation

The application incorporates multiple security layers:

- **Helmet.js** - Configures security-oriented HTTP response headers
- **CORS** - Restricts resource access to designated frontend origin
- **Rate Limiting** - Implements IP-based request throttling (100 requests per 15-minute window)
- **File Validation** - Validates file type, dimensions, and content integrity
- **Automatic Cleanup** - Removes uploaded files post-processing
- **Input Sanitisation** - Validates and sanitises all user inputs

## Error Handling Architecture

Comprehensive error handling encompasses:

### Backend Error Response Format
```json
{
  "success": false,
  "message": "Descriptive error message",
  "error": "ERROR_CODE",
  "timestamp": "2025-12-30T08:25:02.985Z"
}
```

### Error Code Taxonomy
- `UPLOAD_ERROR` - File upload operation failed
- `VALIDATION_ERROR` - File validation criteria not satisfied
- `CONVERSION_ERROR` - PDF conversion process encountered failure
- `FILE_TOO_LARGE` - File exceeds maximum size threshold
- `INVALID_FILE_TYPE` - Unsupported file format submitted

## Performance Optimisations

- File size limitations preventing excessive resource consumption
- Automatic cleanup routines eliminating orphaned temporary files
- Rate limiting mechanisms preventing server resource exhaustion
- Minified production builds reducing bandwidth requirements
- Component lazy loading improving initial page load performance
- Asset optimisation reducing overall application footprint

## Contributing Guidelines

1. Fork repository via GitHub interface
2. Create feature branch (`git checkout -b feature/enhancement-name`)
3. Commit modifications (`git commit -m 'Implement enhancement description'`)
4. Push to branch (`git push origin feature/enhancement-name`)
5. Submit Pull Request with comprehensive description

## Licence

This project operates under the MIT Licence. Refer to the [LICENSE](LICENSE) file for complete terms and conditions.

## Support Channels

Should you encounter difficulties or require clarification:

1. Examine the [Issues](https://github.com/nayandas69/word-to-pdf-converter/issues) section
2. Create a detailed issue report including reproduction steps
3. Contact repository maintainer: [Nayan Das](https://github.com/nayandas69)

## Acknowledgements

- [Mammoth](https://www.npmjs.com/package/mammoth) - Word document text extraction
- [PDF-lib](https://www.npmjs.com/package/pdf-lib) - PDF generation capabilities
- [React](https://reactjs.org/) - Frontend framework
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS framework
- [Express.js](https://expressjs.com/) - Backend web framework
- [Vercel](https://vercel.com/) - Serverless deployment platform
