import React from 'react';

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-primary-100 bg-white/80 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-600 to-primary-700 rounded-lg flex items-center justify-center text-white font-bold text-lg">
              ₹
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">ITR Assistant</h1>
              <p className="text-xs text-gray-500">Income Tax Return Filing</p>
            </div>
          </div>
          <nav className="hidden sm:flex gap-6">
            <a href="/" className="text-sm text-gray-600 hover:text-primary-600 transition">Home</a>
            <a href="/documents" className="text-sm text-gray-600 hover:text-primary-600 transition">Documents</a>
            <a href="/profile" className="text-sm text-gray-600 hover:text-primary-600 transition">Profile</a>
            <a href="/chat" className="text-sm text-gray-600 hover:text-primary-600 transition">AI Chat</a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-gray-50 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center text-sm text-gray-600">
          <p>© 2026 ITR Family Workspace | Personal Tax Filing Assistant | Nilesh & Avani</p>
        </div>
      </footer>
    </div>
  );
}
