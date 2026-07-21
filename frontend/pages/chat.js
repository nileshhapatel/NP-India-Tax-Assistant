import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, HelpCircle } from 'lucide-react';

export default function Chat() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      text: 'Hi! I\'m your ITR filing assistant. Ask me about deductions (80C, 80D, 80AC), residency rules (NRI/RNOR/ROR), tax savings strategies, or anything about filing ITR. What can I help with?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  const suggestions = [
    'What is Section 80C?',
    'NRI vs RNOR difference',
    'Tax deduction options',
    'Sukanya Samriddhi for girl child',
    'Home loan interest deduction',
    'Form 26AS vs AIS',
  ];

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    // Add user message
    const userMessage = {
      id: messages.length + 1,
      role: 'user',
      text: input,
      timestamp: new Date(),
    };
    setMessages([...messages, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input }),
      });
      const data = await res.json();

      const assistantMessage = {
        id: messages.length + 2,
        role: 'assistant',
        text: data.response || 'I could not process that. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = {
        id: messages.length + 2,
        role: 'assistant',
        text: 'Error connecting to AI. Please check your connection.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">🤖 AI Tax Assistant</h1>
        <p className="text-lg text-gray-600">Ask questions about deductions, residency rules, and tax savings</p>
      </div>

      {/* Chat Container */}
      <div className="card flex flex-col h-[600px]">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                <p className="text-sm">{msg.text}</p>
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

        {/* Input */}
        <div className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about deductions, residency, tax savings..."
              className="input flex-1"
            />
            <button onClick={handleSend} disabled={loading} className="btn-primary">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Suggestions */}
      <div>
        <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-primary-600" />
          Suggested Questions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              onClick={() => {
                setInput(s);
              }}
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
