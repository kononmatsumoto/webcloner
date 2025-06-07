'use client';

import axios from 'axios';
import { AlertCircle, CheckCircle, Download, Eye, Globe, Loader2 } from 'lucide-react';
import { useState } from 'react';

interface CloneResponse {
  success: boolean;
  html_content: string;
  error?: string;
  scraped_data?: {
    title: string;
    url: string;
    text_content_count: number;
    images_count: number;
    colors_count: number;
    components_count?: number;
    navigation_items?: number;
    buttons_count?: number;
  };
}

export default function Home() {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<CloneResponse | null>(null);
  const [error, setError] = useState('');
  const [showPreview, setShowPreview] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!url.trim()) {
      setError('Please enter a valid URL');
      return;
    }

    setIsLoading(true);
    setError('');
    setResult(null);

    try {
      const apiUrl = process.env.NODE_ENV === 'development'
        ? 'http://localhost:8000/clone'
        : '/api/clone';

      const response = await axios.post<CloneResponse>(apiUrl, {
        url: url.trim()
      });

      setResult(response.data);
      setShowPreview(true);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as { response?: { data?: { detail?: string } } }).response;
        if (response?.data?.detail) {
          setError(response.data.detail);
        } else {
          setError('Failed to clone website. Please check the URL and try again.');
        }
      } else {
        setError('Failed to clone website. Please check the URL and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const downloadHtml = () => {
    if (!result?.html_content) return;

    const blob = new Blob([result.html_content], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cloned-website.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <header className="text-center mb-12">
          <div className="flex items-center justify-center mb-4">
            <Globe className="h-12 w-12 text-indigo-600 mr-3" />
            <h1 className="text-4xl font-bold text-gray-900">Website Cloner</h1>
          </div>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Enter any public website URL and get an AI-generated HTML clone that matches the original design
          </p>
        </header>

        {/* Main Content */}
        <div className="max-w-4xl mx-auto">
          {/* Input Form */}
          <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-lg p-6 mb-8">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                  Website URL
                </label>
                <input
                  type="url"
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  disabled={isLoading}
                />
              </div>
              <div className="sm:pt-7">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full sm:w-auto px-8 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Cloning...
                    </>
                  ) : (
                    <>
                      <Globe className="h-5 w-5" />
                      Clone Website
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-red-800 font-medium">Error</h3>
                <p className="text-red-700">{error}</p>
              </div>
            </div>
          )}

          {/* Success Result */}
          {result && result.success && (
            <div className="bg-white rounded-lg shadow-lg overflow-hidden mb-8">
              {/* Result Header */}
              <div className="bg-green-50 border-b border-green-200 p-6">
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-6 w-6 text-green-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="text-green-800 font-medium text-lg">Website Cloned Successfully!</h3>
                    <p className="text-green-700 mt-1">Your website has been successfully cloned and is ready for preview or download.</p>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="p-6 border-b border-gray-200">
                <div className="flex flex-col sm:flex-row gap-4">
                  <button
                    onClick={() => setShowPreview(!showPreview)}
                    className="flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                  >
                    <Eye className="h-5 w-5" />
                    {showPreview ? 'Hide Preview' : 'Show Preview'}
                  </button>
                  <button
                    onClick={downloadHtml}
                    className="flex items-center justify-center gap-2 px-6 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
                  >
                    <Download className="h-5 w-5" />
                    Download HTML
                  </button>
                </div>
              </div>

              {/* HTML Preview */}
              {showPreview && (
                <div className="p-6">
                  <h4 className="text-lg font-medium text-gray-900 mb-4">Live Preview</h4>
                  <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                    <iframe
                      srcDoc={result.html_content}
                      className="w-full border-0"
                      style={{
                        height: 'calc(100vh - 200px)',
                        minHeight: '800px',
                        maxHeight: '1200px'
                      }}
                      title="Website Preview"
                      sandbox="allow-same-origin allow-scripts"
                    />
                  </div>

                  {/* Preview Controls */}
                  <div className="mt-4 flex flex-wrap gap-2 justify-center">
                    <button
                      onClick={() => {
                        const iframe = document.querySelector('iframe');
                        if (iframe) {
                          iframe.style.height = '600px';
                        }
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                    >
                      Compact (600px)
                    </button>
                    <button
                      onClick={() => {
                        const iframe = document.querySelector('iframe');
                        if (iframe) {
                          iframe.style.height = '800px';
                        }
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                    >
                      Standard (800px)
                    </button>
                    <button
                      onClick={() => {
                        const iframe = document.querySelector('iframe');
                        if (iframe) {
                          iframe.style.height = '1000px';
                        }
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                    >
                      Large (1000px)
                    </button>
                    <button
                      onClick={() => {
                        const iframe = document.querySelector('iframe');
                        if (iframe) {
                          iframe.style.height = 'calc(100vh - 200px)';
                        }
                      }}
                      className="px-3 py-1 text-xs bg-blue-100 hover:bg-blue-200 rounded text-blue-700"
                    >
                      Full Screen
                    </button>
                  </div>

                  {/* HTML Code */}
                  <div className="mt-6">
                    <h4 className="text-lg font-medium text-gray-900 mb-4">Generated HTML Code</h4>
                    <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-auto">
                      <pre className="text-sm text-gray-800 whitespace-pre-wrap">
                        {result.html_content}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Loading State */}
          {isLoading && (
            <div className="bg-white rounded-lg shadow-lg p-8 text-center">
              <Loader2 className="h-12 w-12 animate-spin text-indigo-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Cloning Website...</h3>
              <p className="text-gray-600">
                This may take a few moments as we scrape the website and generate the HTML clone.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="text-center mt-16 text-gray-500">
          <p>Powered by AI • Built for the Orchids SWE Internship Challenge</p>
        </footer>
      </div>
    </div>
  );
}
