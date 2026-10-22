import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { fraudLabApi } from '../../api/fraudLab';
import { FraudLabScenario, FraudLabRunResult, DetectorMetrics } from '../../types/api';
import { getErrorMessage } from '../../api/client';
import { Play } from 'lucide-react';

export const FraudLabPage: React.FC = () => {
  const [scenarios, setScenarios] = useState<FraudLabScenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('ALL_SCENARIOS_BENCHMARK');
  const [seed, setSeed] = useState<number>(42);
  const [sampleSize, setSampleSize] = useState<number>(200);

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<FraudLabRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadScenarios();
  }, []);

  const loadScenarios = async () => {
    setError(null);
    try {
      const data = await fraudLabApi.listScenarios();
      setScenarios(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    }
  };

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsRunning(true);
    setError(null);

    try {
      const runResult = await fraudLabApi.runSimulation({
        scenario_name: selectedScenario,
        seed,
        sample_size: sampleSize,
      });
      setResult(runResult);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsRunning(false);
    }
  };

  const renderConfusionMatrix = (matrix: DetectorMetrics['confusion_matrix']) => (
    <dl className="grid grid-cols-2 gap-1.5 text-xs text-center">
      {[
        ['Caught', matrix.true_positives, 'text-emerald-300'],
        ['False alarms', matrix.false_positives, 'text-rose-300'],
        ['Missed', matrix.false_negatives, 'text-amber-300'],
        ['Correctly ignored', matrix.true_negatives, 'text-slate-300'],
      ].map(([label, value, color]) => (
        <div key={label as string} className="p-2 rounded bg-forensic-950 border border-forensic-700">
          <dt className="text-slate-400">{label}</dt>
          <dd className={`font-semibold tabular-nums text-sm ${color}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );

  const DETECTOR_NAMES: Record<string, string> = {
    rule_baseline: 'Rule baseline',
    random_forest: 'Random Forest',
    ledger_graph: 'LedgerGraph',
    hybrid_ensemble: 'Hybrid ensemble',
  };
  const detectorEntries = result ? Object.entries(result.detectors) : [];
  const bestF1 = Math.max(0, ...detectorEntries.map(([, m]) => m.f1_score));
  const inputClass =
    'w-full bg-forensic-900 border border-forensic-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500';

  return (
    <div className="space-y-8">
      <PageHeader
        title="Fraud Lab"
        description="Compare the four detectors on seeded synthetic transfers. Runs happen in memory: no real accounts, transfers or ledger entries are created, only a record of the run."
      />

      {error && <ErrorBanner message={error} />}

      <Card variant="forensic" title="Run a benchmark" subtitle="The same seed always produces the same synthetic data, so results can be reproduced.">
        <form onSubmit={handleRunSimulation} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="lab-scenario" className="block text-sm text-slate-300 mb-1">
                Scenario
              </label>
              <select id="lab-scenario" value={selectedScenario} onChange={(e) => setSelectedScenario(e.target.value)} className={inputClass}>
                {scenarios.map((sc) => (
                  <option key={sc.name} value={sc.name}>
                    {sc.name.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}
                  </option>
                ))}
              </select>
              {scenarios.find((sc) => sc.name === selectedScenario) && (
                <p className="text-xs text-slate-400 mt-1">{scenarios.find((sc) => sc.name === selectedScenario)?.description}</p>
              )}
            </div>
            <div>
              <label htmlFor="lab-seed" className="block text-sm text-slate-300 mb-1">
                Seed
              </label>
              <input id="lab-seed" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} className={`${inputClass} tabular-nums`} required />
            </div>
            <div>
              <label htmlFor="lab-size" className="block text-sm text-slate-300 mb-1">
                Synthetic transfers
              </label>
              <input
                id="lab-size"
                type="number"
                min={20}
                max={2000}
                value={sampleSize}
                onChange={(e) => setSampleSize(Number(e.target.value))}
                className={`${inputClass} tabular-nums`}
                required
              />
            </div>
          </div>
          <div className="flex justify-end pt-3 border-t border-forensic-700">
            <Button variant="primary" type="submit" isLoading={isRunning} leftIcon={<Play className="w-3.5 h-3.5" />}>
              Run benchmark
            </Button>
          </div>
        </form>
      </Card>

      {result && (
        <div className="space-y-6">
          <p className="text-sm text-slate-400">
            {result.sample_size} synthetic transfers ({result.fraud_count} fraudulent, {result.legitimate_count} legitimate,{' '}
            {(result.fraud_prevalence * 100).toFixed(1)}% fraud) scored in {result.execution_duration_ms} ms. {result.disclaimer}.
          </p>

          <Card variant="forensic" title="Detector comparison" subtitle="Precision: how many alerts were real fraud. Recall: how much fraud was caught.">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {detectorEntries.map(([key, metrics]) => {
                const isLeader = metrics.f1_score === bestF1 && bestF1 > 0;
                return (
                  <section
                    key={key}
                    aria-label={DETECTOR_NAMES[key] ?? key}
                    className={`p-4 rounded-lg flex flex-col gap-4 ${
                      isLeader ? 'bg-forensic-800 border-2 border-emerald-600' : 'bg-forensic-900 border border-forensic-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold text-slate-100">{DETECTOR_NAMES[key] ?? key}</h3>
                      {isLeader && <Badge variant="success" size="sm">Best F1</Badge>}
                    </div>
                    <dl className="space-y-1.5 text-sm">
                      {[
                        ['Precision', metrics.precision],
                        ['Recall', metrics.recall],
                        ['F1', metrics.f1_score],
                        ['PR AUC', metrics.pr_auc],
                      ].map(([label, value]) => (
                        <div key={label as string} className="flex justify-between">
                          <dt className="text-slate-400">{label}</dt>
                          <dd className="tabular-nums text-slate-100">{((value as number) * 100).toFixed(1)}%</dd>
                        </div>
                      ))}
                      <div className="flex justify-between">
                        <dt className="text-slate-400">Alerts raised</dt>
                        <dd className="tabular-nums text-slate-100">{metrics.review_alerts_count}</dd>
                      </div>
                    </dl>
                    {renderConfusionMatrix(metrics.confusion_matrix)}
                  </section>
                );
              })}
            </div>
            {result.ablation_finding && (
              <p className="mt-5 pt-4 border-t border-forensic-700 text-sm text-slate-300 leading-relaxed">{result.ablation_finding}</p>
            )}
          </Card>

          <Card variant="forensic" title="Detection rate by scenario" subtitle="Share of each scenario's transfers each detector flagged. On legitimate scenarios, lower is better.">
            <div className="overflow-x-auto -mx-4 sm:-mx-5 -mb-4 sm:-mb-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400 border-b border-forensic-700">
                    <th scope="col" className="font-medium py-2 px-4 sm:px-5">Scenario</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Transfers</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Rules</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">Random Forest</th>
                    <th scope="col" className="font-medium py-2 px-4 text-right">LedgerGraph</th>
                    <th scope="col" className="font-medium py-2 px-4 sm:px-5 text-right">Hybrid</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-forensic-700">
                  {Object.entries(result.scenario_breakdown).map(([scenario, item]) => (
                    <tr key={scenario}>
                      <td className="py-2.5 px-4 sm:px-5">
                        <span className="text-slate-100">{scenario.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</span>
                        <span className={`block text-xs ${item.is_fraud_scenario ? 'text-rose-300' : 'text-slate-400'}`}>
                          {item.is_fraud_scenario ? 'Fraud' : 'Legitimate'}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right tabular-nums text-slate-300">{item.count}</td>
                      {[item.rule_detection_rate, item.rf_detection_rate, item.graph_detection_rate, item.hybrid_detection_rate].map((rate, i) => (
                        <td key={i} className={`py-2.5 px-4 text-right tabular-nums ${i === 3 ? 'sm:pr-5' : ''} text-slate-100`}>
                          {(rate * 100).toFixed(0)}%
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
