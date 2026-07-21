import '../styles/globals.css';
import Link from 'next/link';
import { FileText, Users, BarChart3, FileUp, CheckCircle, Download, History, MessageSquare, ListTodo, Building2, Bot } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CaseProvider, useCaseContext } from '../lib/case-context';

const NAVIGATION = [
  { name: 'Dashboard', href: '/dashboard', icon: BarChart3 },
  { name: 'Profile', href: '/profile', icon: Users },
  { name: 'Document Fetcher', href: '/document-fetcher', icon: FileUp },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Residency', href: '/residency', icon: Users },
  { name: 'Income', href: '/income', icon: BarChart3 },
  { name: 'Tax Credits', href: '/tax-credits', icon: CheckCircle },
  { name: 'Property', href: '/property', icon: Building2 },
  { name: 'Tasks', href: '/tasks', icon: ListTodo },
  { name: 'History', href: '/history', icon: History },
  { name: 'Reconciliation', href: '/reconciliation', icon: CheckCircle },
  { name: 'Calculations', href: '/calculations', icon: BarChart3 },
  { name: 'Review', href: '/review', icon: CheckCircle },
  { name: 'Export', href: '/export', icon: Download },
  { name: 'AI Specialists', href: '/ai-specialists', icon: Bot },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
];

function AppLayout({ Component, pageProps }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentPath, setCurrentPath] = useState('');
  const { members, selectedTaxpayerId, selectedCaseId, selectedMember, selectedCase, setSelection, refreshMembers } = useCaseContext();
  const [yearBusy, setYearBusy] = useState(false);
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const updatePath = () => setCurrentPath(window.location.pathname);
    updatePath();
    window.addEventListener('popstate', updatePath);
    return () => window.removeEventListener('popstate', updatePath);
  }, []);

  const ayOptions = useMemo(() => {
    const current = new Date().getFullYear();
    const startAY = current;
    return Array.from({ length: 6 }).map((_, idx) => {
      const ayStart = startAY - 2 + idx;
      const ay = `${ayStart}-${String(ayStart + 1).slice(-2)}`;
      const fyStart = ayStart - 1;
      const fy = `${fyStart}-${String(fyStart + 1).slice(-2)}`;
      return { ay, fy };
    });
  }, []);

  const selectedAy = selectedCase?.assessment_year || '';

  const changeTaxpayer = (taxpayerId) => {
    const member = members.find((m) => m.id === taxpayerId);
    const firstCase = member?.cases?.[0];
    if (member && firstCase) setSelection(member.id, firstCase.id);
  };

  const changeAssessmentYear = async (assessmentYear) => {
    if (!selectedTaxpayerId || !assessmentYear) return;
    const existing = (selectedMember?.cases || []).find((c) => c.assessment_year === assessmentYear);
    if (existing) {
      setSelection(selectedTaxpayerId, existing.id);
      return;
    }
    const fy = ayOptions.find((o) => o.ay === assessmentYear)?.fy || '';
    setYearBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/taxpayers/${selectedTaxpayerId}/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assessment_year: assessmentYear, financial_year: fy }),
      });
      const data = await res.json();
      if (data?.ok && data?.case?.id) {
        await refreshMembers();
        setSelection(selectedTaxpayerId, data.case.id);
      }
    } finally {
      setYearBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-600 to-primary-700 rounded-lg flex items-center justify-center text-white font-bold text-lg">
              ₹
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">ITR Assistant</h1>
              <p className="text-xs text-gray-500">Income Tax Return Filing</p>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <select
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm min-w-[180px]"
              value={selectedTaxpayerId || ''}
              onChange={(e) => changeTaxpayer(Number(e.target.value))}
            >
              {(members || []).map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name}
                </option>
              ))}
            </select>
            <select
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm min-w-[270px]"
              value={selectedAy}
              disabled={yearBusy}
              onChange={(e) => {
                changeAssessmentYear(e.target.value);
              }}
            >
              {ayOptions.map((opt) => {
                const existing = (selectedMember?.cases || []).find((c) => c.assessment_year === opt.ay);
                return (
                  <option key={opt.ay} value={opt.ay}>
                    FY {opt.fy} • AY {opt.ay}{existing ? '' : ' (create)'}
                  </option>
                );
              })}
            </select>
            <span className="text-xs text-gray-500 hidden md:block">
              {selectedCaseId ? `${selectedCase?.residential_status || ''} • Case ${selectedCaseId}` : ''}
            </span>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="px-3 py-2 rounded-lg hover:bg-gray-100 text-gray-600"
            >
              ☰
            </button>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="w-64 bg-white border-r border-gray-200 h-[calc(100vh-73px)] overflow-y-auto">
            <nav className="space-y-1 p-4">
              {NAVIGATION.map((item) => {
                const Icon = item.icon;
                const isActive = currentPath === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setCurrentPath(item.href)}
                    className={`flex items-center gap-3 px-4 py-2 rounded-lg transition ${
                      isActive
                        ? 'bg-primary-100 text-primary-700 font-semibold'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </aside>
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <div className="max-w-7xl mx-auto px-6 py-8">
            <Component {...pageProps} />
          </div>
        </main>
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-gray-50 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8 text-center text-sm text-gray-600">
          <p>© 2026 ITR Family Workspace | Personal Tax Filing Assistant | Nilesh & Avani</p>
        </div>
      </footer>
    </div>
  );
}

export default function App(props) {
  return (
    <CaseProvider>
      <AppLayout {...props} />
    </CaseProvider>
  );
}
