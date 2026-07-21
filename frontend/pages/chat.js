import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, HelpCircle, Bot } from 'lucide-react';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Chat() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      text: 'Hi! I can route your query to Tax, Deduction, Compliance, Reconciliation, or Document specialists.',
      timestamp: new Date(),
      specialist: 'general_assistant',
      confidence: null,
      reasoning: null,
    },
  ]);
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [caseOnlyMode, setCaseOnlyMode] = useState(true);
  const scrollRef = useRef(null);

  const suggestions = [
    'Which regime is better for me this year?',
    'Check compliance risks before filing',
    'How to reconcile AIS with my income?',
    'What documents are still missing?',
  ];

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const currentInput = input;
    const userMessage = {
      id: messages.length + 1,
      role: 'user',
      text: currentInput,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(apiUrl('/api/phase3/chat/orchestrator'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_message: currentInput,
          case_id: String(caseId),
          session_id: sessionId,
          context: { source: 'frontend-chat', case_only: caseOnlyMode },
        }),
      });
      const data = await res.json();
      if (data.session_id) setSessionId(data.session_id);
      const response = data?.response || {};
      setMessages((prev) => [
        ...prev,
        {
          id: prev.length + 1,
          role: 'assistant',
          text: response.text || 'No response.',
          specialist: response.specialist || 'general_assistant',
          confidence: response.confidence,
          reasoning: response.reasoning,
          followUps: response.follow_up_questions || [],
          timestamp: new Date(),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: prev.length + 1,
          role: 'assistant',
          text: 'Error connecting to orchestrator.',
          specialist: 'general_assistant',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">🤖 AI Master Orchestrator</h1>
        <p className="text-lg text-gray-600">Routes each question to a specialist and shows confidence + reasoning.</p>
        <label className="mt-2 inline-flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={caseOnlyMode} onChange={(e) => setCaseOnlyMode(e.target.checked)} />
          Restrict answers to selected case context
        </label>
      </div>

      <div className="card flex flex-col h-[650px]">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xl px-4 py-3 rounded-lg ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                {msg.role === 'assistant' && (
                  <div className="mt-2 text-xs text-gray-600 space-y-1">
                    <p className="inline-flex items-center gap-1"><Bot className="w-3 h-3" /> {msg.specialist || 'general_assistant'}</p>
                    {typeof msg.confidence === 'number' && <p>confidence: {(msg.confidence * 100).toFixed(0)}%</p>}
                    {msg.reasoning && <p>{msg.reasoning}</p>}
                    {(msg.followUps || []).length > 0 && (
                      <p>follow-ups: {(msg.followUps || []).join(' | ')}</p>
                    )}
                  </div>
                )}
                <span className={`text-xs mt-2 block ${msg.role === 'user' ? 'text-blue-100' : 'text-gray-500'}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-900 px-4 py-3 rounded-lg">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>

        <div className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask a tax question..."
              className="input flex-1"
            />
            <button onClick={handleSend} disabled={loading} className="btn-primary">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div>
        <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-primary-600" />
          Suggested Questions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              onClick={() => setInput(s)}
              className="card p-4 text-left text-sm text-gray-700 hover:bg-primary-50 hover:border-primary-300 transition"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
