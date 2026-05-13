'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Server, Wifi, WifiOff, Copy, Check, Trash2, Zap, ArrowLeft, Terminal, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { ClusterInfo, ClusterRegistration } from '@/types';
import { useAuth } from '@/components/auth/AuthProvider';

export default function ClustersPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push('/login');
  }, [authLoading, isAuthenticated, router]);

  const [clusters, setClusters] = useState<ClusterInfo[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [newCluster, setNewCluster] = useState<ClusterRegistration | null>(null);
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('kubernetes');
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [installCmd, setInstallCmd] = useState<string | null>(null);
  const [showCmdFor, setShowCmdFor] = useState<string | null>(null);

  const fetchClusters = async () => {
    try {
      const data = await api.listClusters();
      setClusters(data);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to load clusters');
    }
    setLoading(false);
  };

  useEffect(() => { fetchClusters(); const i = setInterval(fetchClusters, 10000); return () => clearInterval(i); }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError('');
    try {
      const res = await api.registerCluster(name, provider);
      setNewCluster(res);
      fetchClusters();
    } catch (e: any) {
      setError(e.message || 'Failed to register cluster');
    }
  };

  const handleDelete = async (id: string) => {
    setError('');
    try { await api.deleteCluster(id); fetchClusters(); } catch (e: any) { setError(e.message || 'Failed to delete cluster'); }
  };

  const copyCmd = () => {
    if (newCluster) { navigator.clipboard.writeText(newCluster.install_command); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  const providers = ['kubernetes', 'minikube', 'k3s', 'eks', 'aks', 'gke', 'microk8s'];

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#020817]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-sky-500/30 border-t-sky-400 rounded-full animate-spin" />
          <p className="text-sm text-slate-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen p-4 lg:p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <a href="/" className="p-2 rounded-xl hover:bg-slate-800 transition-colors"><ArrowLeft className="w-5 h-5 text-slate-400" /></a>
          <div>
            <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2"><Server className="w-6 h-6 text-sky-400" /> Clusters</h1>
            <p className="text-sm text-slate-500">{clusters.length} cluster{clusters.length !== 1 ? 's' : ''} connected</p>
          </div>
        </div>
        <button onClick={() => { setShowModal(true); setNewCluster(null); setName(''); }}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 text-white font-bold text-sm flex items-center gap-2 hover:shadow-lg hover:shadow-sky-500/25 transition-all">
          <Plus className="w-4 h-4" /> Connect Cluster
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Cluster grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {clusters.map(c => (
          <motion.div key={c.cluster_id} layout initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            className="glass-card rounded-2xl p-5 border border-slate-700/40 hover:border-sky-500/30 transition-all group">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.is_healthy ? 'bg-emerald-500/20 border border-emerald-500/30' : 'bg-rose-500/20 border border-rose-500/30'}`}>
                  {c.is_healthy ? <Wifi className="w-5 h-5 text-emerald-400" /> : <WifiOff className="w-5 h-5 text-rose-400" />}
                </div>
                <div>
                  <h3 className="font-bold text-slate-200">{c.name}</h3>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">{c.cluster_id}</p>
                </div>
              </div>
              <div className="flex gap-1">
                {!c.agent_connected && (
                  <button onClick={async () => {
                    try { const r = await api.getInstallCommand(c.cluster_id); setInstallCmd(r.install_command); setShowCmdFor(c.cluster_id); } catch {}
                  }}
                    className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-sky-500/20 text-slate-500 hover:text-sky-400 transition-all"
                    title="Show install command">
                    <Terminal className="w-4 h-4" />
                  </button>
                )}
                <button onClick={() => handleDelete(c.cluster_id)}
                  className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">Provider</span><span className="text-slate-300 font-mono text-xs">{c.provider}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Agent</span>
                <span className={`text-xs font-bold ${c.agent_connected ? 'text-emerald-400' : 'text-slate-600'}`}>{c.agent_connected ? `v${c.agent_version || '?'}` : 'Not connected'}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Status</span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${c.is_healthy ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'}`}>{c.is_healthy ? 'Healthy' : 'Offline'}</span></div>
            </div>
          </motion.div>
        ))}
        {loading && <div className="col-span-full text-center py-12 text-slate-600">Loading clusters...</div>}
        {!loading && clusters.length === 0 && (
          <div className="col-span-full text-center py-16">
            <Server className="w-12 h-12 text-slate-700 mx-auto mb-4" />
            <p className="text-slate-500 mb-2">No clusters connected</p>
            <p className="text-slate-600 text-sm">Click &quot;Connect Cluster&quot; to add your first Kubernetes cluster</p>
          </div>
        )}
      </div>

      {/* Install Command Modal */}
      <AnimatePresence>
        {showCmdFor && installCmd && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={() => setShowCmdFor(null)}>
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card rounded-3xl p-6 w-full max-w-lg border border-slate-700/50 shadow-2xl"
              onClick={e => e.stopPropagation()}>
              <h2 className="text-lg font-bold text-slate-200 mb-2 flex items-center gap-2">
                <Terminal className="w-5 h-5 text-sky-400" /> Install Command
              </h2>
              <p className="text-sm text-slate-400 mb-4">Run this command in your cluster to install the KubeMind agent:</p>
              <div className="relative">
                <pre className="bg-slate-950 border border-slate-700/60 rounded-xl p-4 text-xs text-emerald-400 font-mono overflow-x-auto whitespace-pre-wrap">
                  {installCmd}
                </pre>
                <button onClick={() => { navigator.clipboard.writeText(installCmd); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                  className="absolute top-3 right-3 p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors">
                  {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-slate-400" />}
                </button>
              </div>
              <button onClick={() => setShowCmdFor(null)}
                className="w-full mt-4 py-3 rounded-xl bg-slate-800 text-slate-300 font-bold text-sm hover:bg-slate-700 transition-all">
                Close
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={() => setShowModal(false)}>
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card rounded-3xl p-6 w-full max-w-lg border border-slate-700/50 shadow-2xl"
              onClick={e => e.stopPropagation()}>

              {!newCluster ? (
                <>
                  <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                    <Plus className="w-5 h-5 text-sky-400" /> Connect Cluster
                  </h2>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Cluster Name</label>
                      <input value={name} onChange={e => setName(e.target.value)} placeholder="production-east"
                        className="w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-slate-700/60 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500/60 transition-all" />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Provider</label>
                      <div className="flex flex-wrap gap-2">
                        {providers.map(p => (
                          <button key={p} onClick={() => setProvider(p)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all ${provider === p ? 'bg-sky-500 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                    <button onClick={handleCreate} disabled={!name.trim()}
                      className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 text-white font-bold text-sm disabled:opacity-40 hover:shadow-lg transition-all">
                      Generate Install Command
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <h2 className="text-lg font-bold text-slate-200 mb-2 flex items-center gap-2">
                    <Check className="w-5 h-5 text-emerald-400" /> Cluster Registered
                  </h2>
                  <p className="text-sm text-slate-400 mb-4">Run this command in your cluster to install the KubeMind agent:</p>
                  <div className="relative">
                    <pre className="bg-slate-950 border border-slate-700/60 rounded-xl p-4 text-xs text-emerald-400 font-mono overflow-x-auto whitespace-pre-wrap">
                      <Terminal className="w-4 h-4 text-slate-600 mb-2" />
                      {newCluster.install_command}
                    </pre>
                    <button onClick={copyCmd}
                      className="absolute top-3 right-3 p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors">
                      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-slate-400" />}
                    </button>
                  </div>
                  <div className="mt-4 p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-xs text-sky-300">
                    <strong>API Key:</strong> <code className="font-mono text-sky-400">{newCluster.api_key}</code>
                  </div>
                  <button onClick={() => setShowModal(false)}
                    className="w-full mt-4 py-3 rounded-xl bg-slate-800 text-slate-300 font-bold text-sm hover:bg-slate-700 transition-all">
                    Done
                  </button>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
