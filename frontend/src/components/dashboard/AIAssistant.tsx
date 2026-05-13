'use client';
import { useState, useRef, useEffect } from 'react';
import { Sparkles, Send, Loader2, Terminal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '@/lib/api';

interface Message { role: 'user' | 'ai'; text: string; source?: string; ts: string }

const SUGGESTIONS = [
  'Why is traffic-ai-service slow?',
  'Which service is causing CPU spikes?',
  'Predict future failures',
  'Show impacted services',
];

export default function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>([{
    role: 'ai',
    text: 'KubeMind AI online. Ask me anything about your infrastructure.',
    ts: new Date().toLocaleTimeString(),
  }]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: question, ts: new Date().toLocaleTimeString() }]);
    setLoading(true);
    try {
      const res = await api.aiQuery(question);
      setMessages(prev => [...prev, {
        role: 'ai',
        text: res.response,
        source: res.source,
        ts: new Date().toLocaleTimeString(),
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'ai', text: 'AI engine unavailable. Check Ollama status.', ts: new Date().toLocaleTimeString() }]);
    } finally { setLoading(false); }
  };

  return (
    <div className="glass-card rounded-2xl flex flex-col h-[420px]">
      <div className="px-4 py-3 border-b border-slate-800/80 flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-sky-400" />AI Operational Assistant
        </h3>
        <Terminal className="w-3.5 h-3.5 text-slate-600" />
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`max-w-[88%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
              m.role === 'user'
                ? 'bg-sky-600/80 text-white rounded-tr-sm'
                : 'bg-slate-800/80 text-slate-300 rounded-tl-sm'
            }`}>{m.text}</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[9px] text-slate-600">{m.ts}</span>
              {m.source && <span className="text-[9px] text-violet-500">{m.source}</span>}
            </div>
          </motion.div>
        ))}
        {loading && (
          <div className="flex items-start">
            <div className="bg-slate-800/80 rounded-xl rounded-tl-sm px-3 py-2">
              <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      <div className="px-3 pb-2 flex gap-1.5 overflow-x-auto">
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => send(s)}
            className="text-[9px] whitespace-nowrap px-2 py-1 rounded-full bg-slate-800/60 border border-slate-700/50 text-slate-400 hover:border-sky-500/40 hover:text-sky-400 transition-colors flex-shrink-0">
            {s}
          </button>
        ))}
      </div>

      <div className="px-3 pb-3">
        <div className="flex gap-2">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send(input)}
            placeholder="Ask infrastructure question..."
            className="flex-1 bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500/50 placeholder:text-slate-600"
          />
          <button onClick={() => send(input)} disabled={loading || !input.trim()}
            className="p-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 rounded-xl transition-colors">
            <Send className="w-3.5 h-3.5 text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}
