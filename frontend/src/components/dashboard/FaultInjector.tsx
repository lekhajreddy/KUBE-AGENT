'use client';
import { useState } from 'react';
import { Zap, ChevronDown } from 'lucide-react';
import { ServiceMetrics, FaultType } from '@/types';
import { motion, AnimatePresence } from 'framer-motion';

const FAULTS: { type: FaultType; label: string; color: string }[] = [
  { type: 'cpu_spike',          label: '⚡ CPU Spike',          color: 'border-amber-500/40 hover:bg-amber-500/10 text-amber-400' },
  { type: 'memory_leak',        label: '🧠 Memory Leak',        color: 'border-indigo-500/40 hover:bg-indigo-500/10 text-indigo-400' },
  { type: 'restart_loop',       label: '🔁 Restart Loop',       color: 'border-rose-500/40 hover:bg-rose-500/10 text-rose-400' },
  { type: 'network_congestion', label: '🌊 Network Congestion', color: 'border-sky-500/40 hover:bg-sky-500/10 text-sky-400' },
  { type: 'storage_overload',   label: '💾 Storage Overload',   color: 'border-violet-500/40 hover:bg-violet-500/10 text-violet-400' },
];

interface Props {
  metrics: ServiceMetrics[];
  activeFaults: Record<string, any>;
  onInject: (svc: string, fault: FaultType) => void;
  onClear:  (svc: string) => void;
}

export default function FaultInjector({ metrics, activeFaults, onInject, onClear }: Props) {
  const [open,    setOpen]    = useState(false);
  const [service, setService] = useState('');

  return (
    <div className="glass-card rounded-2xl overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-800/40 transition-colors">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          Fault Injector
          {Object.keys(activeFaults).length > 0 && (
            <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-400 text-[9px] font-bold rounded-full border border-rose-500/30">
              {Object.keys(activeFaults).length} ACTIVE
            </span>
          )}
        </h3>
        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="px-4 pb-4 space-y-3">
              {/* Service picker */}
              <select value={service} onChange={e => setService(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-sky-500">
                <option value="">— Select service —</option>
                {metrics.map(m => (
                  <option key={m.service} value={m.service}>{m.service}</option>
                ))}
              </select>

              {/* Fault buttons */}
              <div className="grid grid-cols-2 gap-2">
                {FAULTS.map(f => (
                  <button key={f.type} disabled={!service}
                    onClick={() => service && onInject(service, f.type)}
                    className={`text-[10px] font-bold px-2 py-1.5 rounded-lg border transition-all disabled:opacity-30 ${f.color}`}>
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Active faults list */}
              {Object.keys(activeFaults).length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-slate-800">
                  <p className="text-[9px] text-slate-500 uppercase font-bold">Active Faults</p>
                  {Object.entries(activeFaults).map(([svc, info]: [string, any]) => (
                    <div key={svc} className="flex items-center justify-between bg-rose-500/5 border border-rose-500/20 rounded-lg px-2 py-1.5">
                      <div>
                        <p className="text-[10px] font-bold text-slate-300">{svc}</p>
                        <p className="text-[9px] text-rose-400">{info.type?.replace(/_/g, ' ')}</p>
                      </div>
                      <button onClick={() => onClear(svc)}
                        className="text-[9px] px-2 py-0.5 bg-slate-800 hover:bg-rose-900/40 border border-rose-500/30 text-rose-400 rounded transition-colors">
                        Clear
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
