'use client';
import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { ServiceMetrics, TopologyNode, TopologyLink } from '@/types';

const DOMAIN_COLOR: Record<string, string> = {
  traffic: '#38bdf8', energy: '#34d399', campus: '#a78bfa',
  industrial: '#fbbf24', emergency: '#f43f5e',
};

interface Props {
  nodes: TopologyNode[];
  links: TopologyLink[];
  metrics: ServiceMetrics[];
}

export default function DependencyGraph({ nodes, links, metrics }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const statusMap = new Map(metrics.map(m => [m.service, {
    anomaly: m.anomaly?.is_anomaly ?? false,
    fault: !!m.active_fault,
    cpu: m.cpu_percent,
  }]));

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    const el = svgRef.current;
    const W = el.clientWidth || 800;
    const H = el.clientHeight || 500;
    const svg = d3.select(el);
    svg.selectAll('*').remove();

    const defs = svg.append('defs');
    defs.append('marker').attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10').attr('refX', 22).attr('refY', 0)
      .attr('markerWidth', 5).attr('markerHeight', 5).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#475569');
    const glow = defs.append('filter').attr('id', 'glow');
    glow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
    const merge = glow.append('feMerge');
    merge.append('feMergeNode').attr('in', 'coloredBlur');
    merge.append('feMergeNode').attr('in', 'SourceGraphic');

    const root = svg.append('g');
    svg.call(d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.4, 3])
      .on('zoom', (e) => root.attr('transform', e.transform)) as any);

    const simNodes = nodes.map(n => ({ ...n }) as any);
    const simLinks = links.map(l => ({ ...l }) as any);
    const sim = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink(simLinks).id((d: any) => d.id).distance(130))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(40));

    const linkSel = root.append('g').selectAll('line').data(simLinks).join('line')
      .attr('stroke', '#334155').attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '4 2').attr('marker-end', 'url(#arrow)');

    const nodeSel = root.append('g').selectAll('g').data(simNodes).join('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<any, any>()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

    nodeSel.append('circle').attr('r', 14)
      .attr('fill', (d: any) => {
        const st = statusMap.get(d.id);
        if (st?.fault) return '#f43f5e';
        if (st?.anomaly) return '#fbbf24';
        return DOMAIN_COLOR[d.namespace] ?? '#64748b';
      })
      .attr('stroke', '#020817').attr('stroke-width', 2)
      .attr('filter', (d: any) => statusMap.get(d.id)?.anomaly ? 'url(#glow)' : null);

    nodeSel.append('text').attr('dy', 28).attr('text-anchor', 'middle')
      .attr('fill', '#94a3b8').attr('font-size', '9px').attr('font-family', 'monospace')
      .text((d: any) => d.id.replace(/-service$/, ''));

    sim.on('tick', () => {
      linkSel.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
      nodeSel.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [nodes, links, metrics]);

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-3 left-3 z-10 flex flex-col gap-1.5 pointer-events-none">
        {Object.entries(DOMAIN_COLOR).map(([ns, c]) => (
          <div key={ns} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: c }} />
            <span className="text-[9px] text-slate-400 capitalize">{ns}</span>
          </div>
        ))}
      </div>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
