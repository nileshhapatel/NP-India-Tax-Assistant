import Link from 'next/link';
import { FileText, Users, MessageSquare, Zap, CheckCircle2, TrendingUp } from 'lucide-react';

export default function Home() {
  const features = [
    {
      icon: FileText,
      title: 'Smart Document Fetcher',
      description: 'Find where to get all required ITR documents. Official portal links + step-by-step instructions.',
      href: '/documents',
      color: 'from-blue-500 to-cyan-500',
    },
    {
      icon: Users,
      title: 'Household Profile',
      description: 'Manage family information, residency status, dependent details for accurate tax filing.',
      href: '/profile',
      color: 'from-purple-500 to-pink-500',
    },
    {
      icon: MessageSquare,
      title: 'AI Tax Assistant',
      description: 'Ask questions about deductions, residency rules, tax savings. Get instant guidance.',
      href: '/chat',
      color: 'from-green-500 to-emerald-500',
    },
    {
      icon: TrendingUp,
      title: 'Tax Optimization',
      description: 'Compare old vs new regime, identify deduction opportunities, maximize tax savings.',
      href: '/#',
      color: 'from-orange-500 to-red-500',
    },
  ];

  const steps = [
    { step: 1, title: 'Complete Profile', desc: 'Enter personal & family details' },
    { step: 2, title: 'Fetch Documents', desc: 'Download from official sources' },
    { step: 3, title: 'Upload & Process', desc: 'Upload documents to your case' },
    { step: 4, title: 'Get Guidance', desc: 'AI assistant helps with deductions' },
    { step: 5, title: 'Reconcile', desc: 'Match AIS / 26AS with your entries' },
    { step: 6, title: 'File & Export', desc: 'Generate & download final report' },
  ];

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="text-center py-12">
        <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-primary-600 to-blue-600 bg-clip-text text-transparent mb-6">
          Professional ITR Filing Assistant
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Intelligent income tax return preparation for Nilesh (NRI) & Avani (RNOR)
        </p>
        <div className="flex gap-4 justify-center flex-wrap">
          <Link href="/documents">
            <button className="btn-primary text-lg px-8 py-3">
              Get Started →
            </button>
          </Link>
          <Link href="/chat">
            <button className="btn-secondary text-lg px-8 py-3">
              Ask AI Assistant
            </button>
          </Link>
        </div>
      </section>

      {/* Quick Stats */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="text-4xl font-bold text-primary-600 mb-2">2</div>
          <p className="text-gray-600">Taxpayers Registered</p>
          <p className="text-sm text-gray-400 mt-2">Nilesh (NRI) & Avani (RNOR)</p>
        </div>
        <div className="card p-6">
          <div className="text-4xl font-bold text-success-500 mb-2">15+</div>
          <p className="text-gray-600">Documents Tracked</p>
          <p className="text-sm text-gray-400 mt-2">AIS, 26AS, bank, investments</p>
        </div>
        <div className="card p-6">
          <div className="text-4xl font-bold text-blue-600 mb-2">7+</div>
          <p className="text-gray-600">AI Tax Strategies</p>
          <p className="text-sm text-gray-400 mt-2">80C, 80D, 24(b), and more</p>
        </div>
      </section>

      {/* Feature Cards */}
      <section>
        <h2 className="text-3xl font-bold text-gray-900 mb-8">Core Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, idx) => {
            const Icon = feature.icon;
            return (
              <Link href={feature.href} key={idx}>
                <div className="card p-6 hover:shadow-lg cursor-pointer group">
                  <div className={`inline-flex p-3 rounded-lg bg-gradient-to-br ${feature.color} text-white mb-4 group-hover:scale-110 transition`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-gray-900 mb-2">{feature.title}</h3>
                  <p className="text-sm text-gray-600">{feature.description}</p>
                  <div className="text-primary-600 text-sm font-medium mt-4">Learn more →</div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Quick Start Steps */}
      <section>
        <h2 className="text-3xl font-bold text-gray-900 mb-8">Getting Started in 6 Steps</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {steps.map((item, idx) => (
            <div key={idx} className="card p-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-12 h-12 bg-primary-100 text-primary-600 rounded-lg flex items-center justify-center font-bold text-lg">
                  {item.step}
                </div>
                <div>
                  <h3 className="font-bold text-gray-900">{item.title}</h3>
                  <p className="text-sm text-gray-600 mt-1">{item.desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Key Highlights */}
      <section className="bg-gradient-to-r from-primary-600 to-blue-600 rounded-2xl p-8 md:p-12 text-white">
        <h2 className="text-3xl font-bold mb-8">Why Use This Assistant?</h2>
        <div className="grid md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="flex gap-3">
              <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
              <div>
                <h3 className="font-bold">Personalized for NRI & RNOR</h3>
                <p className="text-sm text-blue-100">Specific rules for non-resident & residency status</p>
              </div>
            </div>
            <div className="flex gap-3">
              <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
              <div>
                <h3 className="font-bold">AI-Powered Guidance</h3>
                <p className="text-sm text-blue-100">Real-time deduction suggestions & tax planning</p>
              </div>
            </div>
            <div className="flex gap-3">
              <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
              <div>
                <h3 className="font-bold">Document Management</h3>
                <p className="text-sm text-blue-100">Centralized tracking of all required documents</p>
              </div>
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex gap-3">
              <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
              <div>
                <h3 className="font-bold">Compliance & Accuracy</h3>
                <p className="text-sm text-blue-100">Latest tax rules & 2026-27 compliance</p>
              </div>
            </div>
            <div className="flex gap-3">
              <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
              <div>
                <h3 className="font-bold">Multi-Year History</h3>
                <p className="text-sm text-blue-100">Track income & deductions year over year</p>
              </div>
            </div>
            <div className="flex gap-3">
              <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
              <div>
                <h3 className="font-bold">Privacy First</h3>
                <p className="text-sm text-blue-100">Documents stored locally, no cloud sharing</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Ready to file your ITR?</h2>
        <p className="text-gray-600 mb-8">Start with documents, get AI guidance, and file with confidence</p>
        <Link href="/documents">
          <button className="btn-primary text-lg px-8 py-3">
            Begin Filing Process →
          </button>
        </Link>
      </section>
    </div>
  );
}

