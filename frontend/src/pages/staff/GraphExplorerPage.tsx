import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { CurrencyDisplay } from '../../components/common/CurrencyDisplay';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { graphApi } from '../../api/graph';
import { GraphSubgraphResponse, GraphFindingResponse, GraphNode, GraphEdge } from '../../types/api';
import { getErrorMessage } from '../../api/client';
import { formatDate } from '../../utils/formatters';
import { List, Eye, Crosshair, X } from 'lucide-react';

const SEVERITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'neutral'> = {
  CRITICAL: 'danger',
  HIGH: 'danger',
  MEDIUM: 'warning',
  LOW: 'info',
};

const PATTERN_HELP: Array<[string, string]> = [
  ['Fan-in', 'Many different accounts send money into one account within a short window.'],
  ['Rapid pass-through', 'Money arrives and is sent on again within hours, with little left behind.'],
  ['Multi-hop layering', 'Funds move through a chain of accounts to obscure where they came from.'],
  ['Circular flow', 'Money travels around a loop and returns to the account it started from.'],
];

type ReviewStatus = 'CLEARED' | 'CONFIRMED_FRAUD' | 'ESCALATED';

const prettyPattern = (p: string) => p.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

export const GraphExplorerPage: React.FC = () => {
  const [subgraph, setSubgraph] = useState<GraphSubgraphResponse | null>(null);
  const [findings, setFindings] = useState<GraphFindingResponse[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [viewMode, setViewMode] = useState<'visual' | 'table'>('visual');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [anchor, setAnchor] = useState<GraphNode | null>(null);
  const [hops, setHops] = useState<number>(2);
  const [limit, setLimit] = useState<number>(60);

  const [reviewing, setReviewing] = useState<string | null>(null);
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>('CLEARED');
  const [reviewNotes, setReviewNotes] = useState('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const fetchGraphData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [graphData, findingsData] = await Promise.all([
        graphApi.getSubgraph({ account_id: anchor?.id, hops, limit }),
        graphApi.listFindings({ limit: 20 }),
      ]);
      setSubgraph(graphData);
      setFindings(findingsData);
      setSelectedEdge(null);
      setSelectedNode(graphData.nodes.find((n) => n.id === anchor?.id) ?? graphData.nodes[0] ?? null);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, [anchor, hops, limit]);

  const submitReview = async (findingId: string) => {
    if (reviewNotes.trim().length < 3) {
      setError('Add a short note (at least 3 characters) explaining the decision.');
      return;
    }
    setIsSubmittingReview(true);
    setError(null);
    try {
      const updated = await graphApi.reviewFinding(findingId, { review_status: reviewStatus, notes: reviewNotes.trim() });
      setFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
      setReviewing(null);
      setReviewNotes('');
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Simple circular layout: deterministic and readable for the bounded neighbourhoods the API returns
  const W = 600;
  const H = 380;
  const nodeCoords: Record<string, { x: number; y: number }> = {};
  subgraph?.nodes.forEach((node, i, all) => {
    const angle = (2 * Math.PI * i) / (all.length || 1) - Math.PI / 2;
    const r = all.length === 1 ? 0 : Math.min(W, H) * 0.38;
    nodeCoords[node.id] = { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle) };
  });
  const accountNumber = (id: string) => subgraph?.nodes.find((n) => n.id === id)?.account_number ?? id.slice(0, 8);
  const selectClass = 'bg-forensic-900 border border-forensic-700 rounded px-2.5 py-1.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500';

  return (
    <div className="space-y-8">
      <PageHeader
        title="LedgerGraph"
        description="Money movements drawn as a network: accounts are points, posted transfers are arrows. Pattern findings are advisory and need a staff decision."
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setViewMode(viewMode === 'visual' ? 'table' : 'visual')}
            leftIcon={viewMode === 'visual' ? <List className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          >
            {viewMode === 'visual' ? 'Show as table' : 'Show as graph'}
          </Button>
        }
      />

      {error && <ErrorBanner message={error} />}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
        {anchor ? (
          <span className="flex items-center gap-2 text-slate-300">
            Centred on <span className="font-mono text-slate-100">{anchor.account_number}</span>
            <button
              type="button"
              onClick={() => setAnchor(null)}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-forensic-800"
              aria-label="Show recent activity across all accounts"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </span>
        ) : (
          <span className="text-slate-400">Showing the most recent posted transfers. Select an account to centre on it.</span>
        )}
        <label className="flex items-center gap-2 text-slate-300">
          Hops
          <select value={hops} onChange={(e) => setHops(Number(e.target.value))} className={selectClass} disabled={!anchor}>
            <option value={1}>1, direct counterparties</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-slate-300">
          Transfers
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={selectClass}>
            <option value={20}>20</option>
            <option value={60}>60</option>
            <option value={100}>100</option>
          </select>
        </label>
        <span className="text-slate-400 tabular-nums">
          {subgraph?.nodes.length ?? 0} {subgraph?.nodes.length === 1 ? 'account' : 'accounts'},{' '}
          {subgraph?.edges.length ?? 0} {subgraph?.edges.length === 1 ? 'transfer' : 'transfers'}
        </span>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center p-16">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Card variant="forensic" title="Network">
              {!subgraph || subgraph.nodes.length === 0 ? (
                <p className="py-12 text-center text-sm text-slate-400">No posted transfers to draw yet.</p>
              ) : viewMode === 'visual' ? (
                <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto bg-forensic-950 rounded" role="img" aria-label="Money-flow network. Use the table view for an accessible list.">
                  <defs>
                    <marker id="arrow" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#34d399" />
                    </marker>
                  </defs>
                  {subgraph.edges.map((edge) => {
                    const src = nodeCoords[edge.source];
                    const dst = nodeCoords[edge.target];
                    if (!src || !dst) return null;
                    const isSelected = selectedEdge?.id === edge.id;
                    return (
                      <g key={edge.id} onClick={() => setSelectedEdge(edge)} className="cursor-pointer">
                        <line x1={src.x} y1={src.y} x2={dst.x} y2={dst.y} stroke="transparent" strokeWidth={12} />
                        <line
                          x1={src.x}
                          y1={src.y}
                          x2={dst.x}
                          y2={dst.y}
                          stroke={isSelected ? '#34d399' : '#4CAE86'}
                          strokeOpacity={isSelected ? 1 : 0.55}
                          strokeWidth={isSelected ? 2.5 : 1.5}
                          markerEnd="url(#arrow)"
                        />
                        <text x={(src.x + dst.x) / 2} y={(src.y + dst.y) / 2 - 6} fill="#C7D8BF" fontSize="11" textAnchor="middle" className="pointer-events-none">
                          ₹{Number(edge.amount).toLocaleString('en-IN')}
                        </text>
                      </g>
                    );
                  })}
                  {subgraph.nodes.map((node) => {
                    const pos = nodeCoords[node.id];
                    const isSelected = selectedNode?.id === node.id;
                    return (
                      <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`} onClick={() => setSelectedNode(node)} className="cursor-pointer">
                        <circle r={isSelected ? 15 : 11} fill={isSelected ? '#206A4C' : '#11221B'} stroke={isSelected ? '#34d399' : '#4CAE86'} strokeWidth={isSelected ? 2.5 : 1.5} />
                        <text y={28} fill="#DCE8D8" fontSize="11" textAnchor="middle" className="pointer-events-none font-mono">
                          {node.account_number.split('-').slice(-1)[0]}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              ) : (
                <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-slate-400 border-b border-forensic-700">
                        <th scope="col" className="font-medium py-2 px-4 sm:px-5">From</th>
                        <th scope="col" className="font-medium py-2 px-4">To</th>
                        <th scope="col" className="font-medium py-2 px-4 text-right">Amount</th>
                        <th scope="col" className="font-medium py-2 px-4 sm:px-5">Posted</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-forensic-700">
                      {subgraph.edges.map((e) => (
                        <tr key={e.id}>
                          <td className="py-2.5 px-4 sm:px-5 font-mono text-xs text-slate-200">{accountNumber(e.source)}</td>
                          <td className="py-2.5 px-4 font-mono text-xs text-slate-200">{accountNumber(e.target)}</td>
                          <td className="py-2.5 px-4 text-right">
                            <CurrencyDisplay amount={e.amount} size="sm" />
                          </td>
                          <td className="py-2.5 px-4 sm:px-5 text-slate-400 whitespace-nowrap">{formatDate(e.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card variant="forensic" title={`Pattern findings (${findings.length})`} subtitle="Raised by the deterministic LedgerGraph detectors. Each needs a staff decision.">
              {findings.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-400">
                  No patterns found yet. Findings appear when transfers form fan-in, pass-through, layering or circular shapes.
                </p>
              ) : (
                <ul className="space-y-3">
                  {findings.map((f) => (
                    <li key={f.id} className="p-4 rounded-lg bg-forensic-900 border border-forensic-700 text-sm space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-semibold text-slate-100">{prettyPattern(f.pattern_type)}</span>
                        <span className="flex items-center gap-2">
                          <Badge variant={SEVERITY_VARIANT[f.severity] ?? 'neutral'} size="sm">
                            {f.severity}
                          </Badge>
                          <span className="text-xs text-slate-400 tabular-nums">score {Number(f.heuristic_score).toFixed(2)}</span>
                        </span>
                      </div>
                      <p className="text-slate-300 leading-relaxed">{f.explanation}</p>
                      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                        <span>
                          {f.involved_account_ids.length} accounts, {f.involved_transfer_ids.length} transfers, {formatDate(f.created_at)}
                        </span>
                        {f.review_status === 'PENDING' ? (
                          reviewing !== f.id && (
                            <Button variant="secondary" size="sm" onClick={() => { setReviewing(f.id); setReviewNotes(''); }}>
                              Review
                            </Button>
                          )
                        ) : (
                          <Badge variant={f.review_status === 'CONFIRMED_FRAUD' ? 'danger' : f.review_status === 'ESCALATED' ? 'warning' : 'success'} size="sm">
                            {prettyPattern(f.review_status)}
                          </Badge>
                        )}
                      </div>
                      {reviewing === f.id && (
                        <div className="pt-3 mt-1 border-t border-forensic-700 space-y-2">
                          <label className="block text-slate-300">
                            Decision
                            <select value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value as ReviewStatus)} className={`${selectClass} block mt-1 w-full`}>
                              <option value="CLEARED">Cleared, legitimate activity</option>
                              <option value="ESCALATED">Escalate for further investigation</option>
                              <option value="CONFIRMED_FRAUD">Confirmed fraud</option>
                            </select>
                          </label>
                          <label className="block text-slate-300">
                            Reason
                            <textarea
                              rows={2}
                              value={reviewNotes}
                              onChange={(e) => setReviewNotes(e.target.value)}
                              className={`${selectClass} block mt-1 w-full resize-none`}
                              placeholder="What did you check, and why this decision?"
                            />
                          </label>
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="sm" onClick={() => setReviewing(null)}>
                              Cancel
                            </Button>
                            <Button variant="primary" size="sm" isLoading={isSubmittingReview} onClick={() => submitReview(f.id)}>
                              Record decision
                            </Button>
                          </div>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="space-y-6">
            {selectedNode && (
              <Card variant="forensic" title="Account">
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Number</dt>
                    <dd className="font-mono text-slate-100">{selectedNode.account_number}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Holder</dt>
                    <dd className="text-slate-100 text-right">{selectedNode.customer_name}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Type</dt>
                    <dd className="text-slate-100">{prettyPattern(selectedNode.account_type)}, {selectedNode.status.toLowerCase()}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Balance</dt>
                    <dd>
                      <CurrencyDisplay amount={selectedNode.cached_balance} size="sm" />
                    </dd>
                  </div>
                </dl>
                {anchor?.id !== selectedNode.id && (
                  <Button variant="secondary" size="sm" className="mt-4 w-full" leftIcon={<Crosshair className="w-3.5 h-3.5" />} onClick={() => setAnchor(selectedNode)}>
                    Centre the graph on this account
                  </Button>
                )}
              </Card>
            )}

            {selectedEdge && (
              <Card variant="forensic" title="Transfer">
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Amount</dt>
                    <dd>
                      <CurrencyDisplay amount={selectedEdge.amount} size="md" />
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">From</dt>
                    <dd className="font-mono text-xs text-slate-100">{accountNumber(selectedEdge.source)}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">To</dt>
                    <dd className="font-mono text-xs text-slate-100">{accountNumber(selectedEdge.target)}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Posted</dt>
                    <dd className="text-slate-100">{formatDate(selectedEdge.created_at)}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Reference</dt>
                    <dd className="font-mono text-xs text-slate-300 truncate max-w-[160px]" title={selectedEdge.id}>
                      {selectedEdge.id}
                    </dd>
                  </div>
                </dl>
              </Card>
            )}

            <Card variant="forensic" title="What the detectors look for">
              <dl className="space-y-3 text-sm">
                {PATTERN_HELP.map(([name, help]) => (
                  <div key={name}>
                    <dt className="font-semibold text-slate-100">{name}</dt>
                    <dd className="text-slate-400 leading-relaxed">{help}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
};
