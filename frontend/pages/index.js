import Link from 'next/link';
import { ArrowRight, FileText, CheckCircle, BarChart3, MessageSquare } from 'lucide-react';

export default function Home() {
  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="text-center py-12">
        <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-primary-600 to-blue-600 bg-clip-text text-transparent mb-6">
          Professional ITR Filing
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Intelligent income tax return preparation for Nilesh (NRI) & Avani (RNOR) with AI-powered assistance
        </p>
        <div className="flex gap-4 justify-center flex-wrap">
          <Link href="/dashboard">
            <button className="flex items-center gap-2 px-8 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-semibold text-lg">
              Get Started <ArrowRight className="w-5 h-5" />
            </button>
          </Link>
          <Link href="/document-fetcher">
            <button className="flex items-center gap-2 px-8 py-3 bg-gray-200 text-gray-900 rounded-lg hover:bg-gray-300 font-semibold text-lg">
              Download Documents <FileText className="w-5 h-5" />
            </button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <FileText className="w-8 h-8 text-blue-600 mb-3" />
          <h3 className="font-semibold text-gray-900 mb-2">Smart Document Fetcher</h3>
          <p className="text-sm text-gray-600">Find all required ITR documents with official portal links and step-by-step instructions</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <CheckCircle className="w-8 h-8 text-green-600 mb-3" />
          <h3 className="font-semibold text-gray-900 mb-2">Document Tracking</h3>
          <p className="text-sm text-gray-600">Upload and track all required documents with verification status</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <BarChart3 className="w-8 h-8 text-purple-600 mb-3" />
          <h3 className="font-semibold text-gray-900 mb-2">Tax Calculations</h3>
          <p className="text-sm text-gray-600">Compare old vs new regime and identify deduction opportunities</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <MessageSquare className="w-8 h-8 text-orange-600 mb-3" />
          <h3 className="font-semibold text-gray-900 mb-2">AI Tax Assistant</h3>
          <p className="text-sm text-gray-600">Get instant guidance on deductions, residency rules, and tax savings</p>
        </div>
      </section>

      {/* Filing Workflow */}
      <section className="bg-white rounded-lg border border-gray-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Filing Workflow</h2>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
          {[
            { step: 1, title: 'Profile', desc: 'Personal details' },
            { step: 2, title: 'Residency', desc: 'NRI/RNOR status' },
            { step: 3, title: 'Documents', desc: 'Upload & verify' },
            { step: 4, title: 'Income', desc: 'Enter all sources' },
            { step: 5, title: 'Reconcile', desc: 'Cross-verify data' },
            { step: 6, title: 'Export', desc: 'File return' },
          ].map((item, idx) => (
            <div key={idx} className="text-center">
              <div className="w-12 h-12 rounded-full bg-primary-100 text-primary-600 font-bold text-lg flex items-center justify-center mx-auto mb-2">
                {item.step}
              </div>
              <p className="font-semibold text-gray-900">{item.title}</p>
              <p className="text-xs text-gray-600">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Taxpayers */}
      <section className="bg-gradient-to-r from-primary-50 to-blue-50 rounded-lg border border-primary-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Taxpayers</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg p-6 border border-primary-100">
            <p className="text-lg font-semibold text-gray-900">Nilesh Kumar</p>
            <p className="text-primary-600 font-medium">NRI (Non-Resident Indian)</p>
            <p className="text-sm text-gray-600 mt-2">AY 2026-27 | FY 2025-26</p>
            <div className="mt-3 space-y-1 text-sm text-gray-600">
              <p>• Foreign income (salary)</p>
              <p>• NRE & NRO accounts</p>
              <p>• Zerodha investments</p>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 border border-green-100">
            <p className="text-lg font-semibold text-gray-900">Avani</p>
            <p className="text-green-600 font-medium">RNOR (Resident Not Ordinarily Resident)</p>
            <p className="text-sm text-gray-600 mt-2">AY 2026-27 | FY 2025-26</p>
            <div className="mt-3 space-y-1 text-sm text-gray-600">
              <p>• Foreign income & remittances</p>
              <p>• Regular savings account</p>
              <p>• Home ownership in India</p>
            </div>
          </div>
        </div>
      </section>

      {/* Quick Stats */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <p className="text-3xl font-bold text-primary-600 mb-1">18+</p>
          <p className="text-gray-600">Required Documents</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <p className="text-3xl font-bold text-green-600 mb-1">6</p>
          <p className="text-gray-600">Portal Sources</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <p className="text-3xl font-bold text-purple-600 mb-1">100%</p>
          <p className="text-gray-600">ITR-2 Ready</p>
        </div>
      </section>
    </div>
  );
}
