# Website Cloner Application

A powerful website cloning application that recreates websites with dynamic color extraction, enhanced navigation, and intelligent image handling. Built with FastAPI backend and Next.js frontend.

## Features

-  **Dynamic Color Extraction**: Automatically extracts and applies color schemes from target websites
-  **Intelligent Image Handling**: Processes and optimizes background images with template-based implementation
-  **Enhanced Navigation**: Apple-style navigation with proper alignment and backdrop blur effects
-  **Responsive Design**: Modern, mobile-friendly interface
-  **Smart Text Content**: Preserves and enhances text content from original websites

## Prerequisites

Before setting up the application, ensure you have the following installed:

- **Python 3.13+** (for backend)
- **Node.js 18+** and **npm** (for frontend)
- **uv** (Python package manager) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

## API Keys Required

You'll need API keys from the following services:

1. **Anthropic API Key**: Sign up at [Anthropic Console](https://console.anthropic.com/)
2. **Browserbase API Key & Project ID**: Sign up at [Browserbase](https://www.browserbase.com/)

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd orchids-challenge
```

### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

#### Install Dependencies

```bash
uv sync
```

#### Start the Backend Server

```bash
# Method 1: Using uvicorn directly
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Method 2: With environment variables in one command
export ANTHROPIC_API_KEY="your-key" && export BROWSERBASE_API_KEY="your-key" && export BROWSERBASE_PROJECT_ID="your-project-id" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

Open a new terminal and navigate to the frontend directory:

```bash
cd frontend
```

#### Install Dependencies

```bash
npm install
```

#### Start the Frontend Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:3001`

## Usage

1. Open your browser and go to `http://localhost:3001`
2. Enter the URL of the website you want to clone
3. Click "Clone Website" 
4. Wait for the system to process and generate the cloned website
5. View the result with enhanced styling, proper navigation, and optimized images

## API Endpoints

### Backend Endpoints

- **GET** `/health` - Health check endpoint
- **POST** `/clone` - Clone a website
  - Body: `{"url": "https://example.com"}`
  - Returns: Generated HTML with enhanced styling

## Technical Architecture

### Backend (FastAPI)
- **Web Scraping**: Uses Browserbase for reliable web scraping
- **Content Processing**: BeautifulSoup for HTML parsing and content extraction
- **AI Enhancement**: Anthropic Claude for intelligent HTML generation
- **Image Processing**: Pillow for image optimization
- **Color Extraction**: Dynamic color palette generation

### Frontend (Next.js)
- **React 19**: Latest React features
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Axios**: HTTP client for API communication
- **Lucide React**: Beautiful icons

## Troubleshooting

### Common Issues

#### 1. Environment Variables Not Set
If you see `ValueError: ANTHROPIC_API_KEY environment variable is not set`:
- Ensure all environment variables are properly exported
- Check that there are no typos in variable names
- Restart the backend server after setting variables

#### 2. Browserbase Connection Issues
If you see Browserbase session creation failures:
- Verify your Browserbase API key and Project ID
- Check your Browserbase account limits and usage
- Ensure you have an active Browserbase subscription

#### 3. Port Already in Use
If you see `Address already in use` error:
```bash
# Kill existing processes
pkill -f "uvicorn app.main:app"
# Then restart the server
```

#### 4. Frontend Build Issues
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Development Tips

1. **Use Background Mode**: For long-running processes, you can run the backend in background mode
2. **Environment File**: Create a `.env` file in the backend directory for persistent environment variables
3. **Hot Reload**: Both frontend and backend support hot reloading during development


## License

This project is part of the Orchids SWE Intern Challenge.

---

**Need Help?** Check the troubleshooting section above or review the terminal logs for specific error messages.
