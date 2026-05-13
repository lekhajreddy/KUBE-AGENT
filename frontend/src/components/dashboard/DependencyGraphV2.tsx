'use client';
import { useMemo } from 'react';
import dagre from 'dagre';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  NodeProps,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { ServiceMetrics, TopologyNode, TopologyLink, CorrelationData } from '@/types';
import { motion } from 'framer-motion';

const NODE_COLORS: Record<string, string> = {
  deployment: '#38bdf8',
  ingress: '#a78bfa',
  pvc: '#34d399',
  service: '#fbbf24',
  default: '#64748b',
};

function ServiceNode({ data }: NodeProps) {
  const color = data.nodeColor || NODE_COLORS.default;
  const isAnomaly = data.isAnomaly;
  const isFault = data.isFault;
  const borderColor = isFault ? '#f43f5e' : isAnomaly ? '#fbbf24' : color;

  return (
    <div className="relative">
      <motion.div
        animate={isAnomaly ? {
          boxShadow: ['0 0 0px rgba(251,191,36,0.4)', '0 0 20px rgba(251,191,36,0.6)', '0 0 0px rgba(251,191,36,0.4)'],
        } : isFault ? {
          boxShadow: ['0 0 0px rgba(244,63,94,0.4)', '0 0 20px rgba(244,63,94,0.6)', '0 0 0px rgba(244,63,94,0.4)'],
        } : {}}
        transition={{ duration: 2, repeat: Infinity }}
        className="px-3 py-2 rounded-xl border-2 bg-slate-900/90 backdrop-blur-sm min-w-[120px]"
        style={{ borderColor }}
      >
        <Handle type="target" position={Position.Top} className="!bg-slate-600" />
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: color }} />
          <div>
            <p className="text-[10px] font-bold text-slate-200 leading-none">{data.label}</p>
            <p className="text-[8px] text-slate-500 mt-0.5">{data.namespace}</p>
          </div>
        </div>
        {data.cpu !== undefined && (
          <div className="mt-1.5 flex gap-2 text-[8px] font-mono">
            <span className={data.cpu > 80 ? 'text-rose-400' : 'text-slate-500'}>
              CPU {data.cpu}%
            </span>
            {data.restarts > 0 && (
              <span className="text-rose-400">R:{data.restarts}</span>
            )}
          </div>
        )}
        <Handle type="source" position={Position.Bottom} className="!bg-slate-600" />
      </motion.div>
    </div>
  );
}

const nodeTypes = { serviceNode: ServiceNode };

interface Props {
  nodes: TopologyNode[];
  links: TopologyLink[];
  metrics: ServiceMetrics[];
  correlationIntelligence?: CorrelationData;
}

function layoutNodes(nodes: TopologyNode[], links: TopologyLink[]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 80, marginx: 30, marginy: 30 });

  for (const n of nodes) g.setNode(n.id, { width: 140, height: 50 });
  for (const l of links) g.setEdge(l.source, l.target);

  dagre.layout(g);

  const positions: Record<string, { x: number; y: number }> = {};
  for (const n of nodes) {
    const pt = g.node(n.id);
    positions[n.id] = pt ? { x: pt.x, y: pt.y } : { x: 0, y: 0 };
  }
  return positions;
}

export default function DependencyGraphV2({ nodes: topoNodes, links: topoLinks, metrics, correlationIntelligence }: Props) {
  const statusMap = useMemo(() => new Map(metrics.map(m => [m.service, {
    anomaly: m.anomaly?.is_anomaly ?? false,
    fault: !!m.active_fault,
    cpu: m.cpu_percent,
    restarts: m.restart_count,
    namespace: m.namespace,
  }])), [metrics]);

  const impactedServices = useMemo(() => {
    if (!correlationIntelligence?.impact_chains) return new Set<string>();
    const set = new Set<string>();
    for (const chain of correlationIntelligence.impact_chains) {
      for (const item of chain.chain) {
        if (item.is_anomaly) set.add(item.service);
      }
    }
    return set;
  }, [correlationIntelligence]);

  const positions = useMemo(() => layoutNodes(topoNodes, topoLinks), [topoNodes, topoLinks]);

  const rfNodes = useMemo(() => topoNodes.map((n) => {
    const st = statusMap.get(n.id);
    const isImpacted = impactedServices.has(n.id);
    const pos = positions[n.id] || { x: 0, y: 0 };
    return {
      id: n.id,
      type: 'serviceNode',
      position: { x: pos.x, y: pos.y },
      data: {
        label: n.id.replace(/-service$/, '').replace(/-deployment$/, ''),
        namespace: n.namespace,
        nodeColor: NODE_COLORS[n.type || 'default'] || NODE_COLORS.default,
        isAnomaly: st?.anomaly || isImpacted,
        isFault: st?.fault || false,
        cpu: st?.cpu,
        restarts: st?.restarts,
      },
    };
  }), [topoNodes, statusMap, impactedServices, positions]);

  const rfEdges = useMemo(() => topoLinks.map((l, idx) => ({
    id: `e-${idx}`,
    source: l.source,
    target: l.target,
    type: 'smoothstep',
    animated: statusMap.get(l.source)?.anomaly || statusMap.get(l.target)?.anomaly,
    style: {
      stroke: statusMap.get(l.source)?.anomaly ? '#f43f5e' : statusMap.get(l.target)?.anomaly ? '#fbbf24' : '#475569',
      strokeWidth: statusMap.get(l.source)?.anomaly ? 2.5 : 1.5,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: statusMap.get(l.source)?.anomaly ? '#f43f5e' : '#475569',
      width: 15,
      height: 15,
    },
    label: l.type || '',
  })), [topoLinks, statusMap]);

  return (
    <div className="w-full h-full">
      <ReactFlowProvider>
        <div className="w-full h-full">
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#1e293b" gap={20} />
            <Controls className="!bg-slate-900 !border-slate-700 !rounded-lg" />
            <MiniMap
              nodeColor={(n: any) => n.data?.nodeColor || '#64748b'}
              maskColor="rgba(2,8,23,0.8)"
              className="!bg-slate-900 !border-slate-700 !rounded-lg"
            />
          </ReactFlow>
        </div>
        {correlationIntelligence && correlationIntelligence.impact_chains.length > 0 && (
          <div className="absolute top-3 right-3 z-10 glass rounded-xl p-2 max-w-[200px]">
            <p className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mb-1">Impact Chains</p>
            {correlationIntelligence.impact_chains.slice(0, 2).map((chain, i) => (
              <div key={i} className="text-[8px] text-slate-500 mb-1">
                <span className="text-sky-400">{chain.namespace}</span>
                <div className="flex items-center gap-0.5 mt-0.5">
                  {chain.chain.slice(0, 4).map((item, j) => (
                    <span key={j} className={`px-1 py-0.5 rounded ${item.is_anomaly ? 'bg-rose-500/20 text-rose-400' : 'bg-slate-800 text-slate-400'}`}>
                      {item.service.substring(0, 8)}
                      {j < chain.chain.length - 1 && j < 3 ? <span className="ml-0.5">→</span> : null}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </ReactFlowProvider>
    </div>
  );
}
