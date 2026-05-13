'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthProvider';
import { motion } from 'framer-motion';
import { UserPlus, Eye, EyeOff, ArrowRight, Zap } from 'lucide-react';

export default function RegisterPage() {
  const { register, isAuthenticated, loading: authLoading } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: '', email: '', password: '', organization: '' });
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) router.push('/');
  }, [authLoading, isAuthenticated, router]);

  if (authLoading) return <div className="min-h-screen bg-[#020817]" />;
  if (isAuthenticated) return null;

  const update = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (form.password.length < 6) { setError('Password must be 6+ characters'); return; }
    setLoading(true);
    try {
      await register(form);
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950" />
      <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/3 left-1/4 w-80 h-80 bg-sky-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/30">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">KubeMind</h1>
          </div>
          <p className="text-slate-500 text-sm">Create your observability workspace</p>
        </div>

        <div className="glass-card rounded-3xl p-8 border border-slate-700/50 shadow-2xl shadow-black/50">
          <div className="flex items-center gap-2 mb-6">
            <UserPlus className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-slate-200">Create Account</h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {[
              { key: 'name', label: 'Full Name', type: 'text', ph: 'Jane Doe' },
              { key: 'email', label: 'Email', type: 'email', ph: 'admin@company.com' },
              { key: 'organization', label: 'Organization', type: 'text', ph: 'Acme Corp (optional)' },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">{f.label}</label>
                <input type={f.type} value={(form as any)[f.key]} onChange={e => update(f.key, e.target.value)}
                  required={f.key !== 'organization'} placeholder={f.ph}
                  className="w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-slate-700/60 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500/60 focus:ring-1 focus:ring-sky-500/30 transition-all" />
              </div>
            ))}

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={form.password} onChange={e => update('password', e.target.value)}
                  required placeholder="6+ characters"
                  className="w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-slate-700/60 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500/60 focus:ring-1 focus:ring-sky-500/30 transition-all pr-12" />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">{error}</motion.div>}

            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-sky-600 text-white font-bold text-sm flex items-center justify-center gap-2 hover:shadow-lg hover:shadow-indigo-500/25 transition-all disabled:opacity-50">
              {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <>Create Account <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>

          <div className="mt-6 text-center">
            <a href="/login" className="text-sm text-sky-400 hover:text-sky-300 transition-colors">
              Already have an account? <span className="font-semibold">Sign In</span>
            </a>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
