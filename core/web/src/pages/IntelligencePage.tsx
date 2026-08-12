import { useCallback, useEffect, useState } from "react";
import { Activity, Boxes, BrainCircuit, Check, Download, GitBranch, Network, RefreshCw, RotateCcw, X } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { H2 } from "@nous-research/ui/ui/components/typography/h2";
import { api, ATHENA_BASE_PATH } from "@/lib/api";
import type { IntelligenceStatus, ReviewItem, TraceRun, TraceRunDetail } from "@/lib/api";

function when(value: number | null | undefined): string {
  return value ? new Date(value * 1000).toLocaleString() : "—";
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Card><CardContent className="py-4"><div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div><div className="mt-1 text-2xl font-semibold">{value}</div></CardContent></Card>
  );
}

export default function IntelligencePage() {
  const [status, setStatus] = useState<IntelligenceStatus | null>(null);
  const [traces, setTraces] = useState<TraceRun[]>([]);
  const [results, setResults] = useState<ReviewItem[]>([]);
  const [selected, setSelected] = useState<TraceRunDetail | null>(null);
  const [selectedResult, setSelectedResult] = useState<ReviewItem | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [overview, traceRows, resultRows] = await Promise.all([
      api.getIntelligenceStatus(), api.getIntelligenceTraces(30), api.getReviewResults(30),
    ]);
    setStatus(overview); setTraces(traceRows.runs); setResults(resultRows.items); setLoading(false);
  }, []);
  useEffect(() => { void load(); }, [load]);

  const review = async (id: string, next: string) => {
    await api.setReviewResultStatus(id, next);
    await load();
  };

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-semibold">Athena Intelligence</h1><p className="text-sm text-muted-foreground">Rastreamento, entregas, fluxos, modelos, experimentos e trabalhadores em um só lugar.</p></div>
        <Button ghost prefix={<RefreshCw className="h-4 w-4" />} disabled={loading} onClick={() => void load()}>Atualizar</Button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Execuções rastreadas" value={status?.traces.total ?? 0} />
        <Metric label="Aguardando revisão" value={status?.results.needs_attention ?? 0} />
        <Metric label="Fluxos instalados" value={status?.flows.definitions.length ?? 0} />
        <Metric label="Trabalhadores online" value={status?.workers.online ?? 0} />
      </div>

      <section className="flex flex-col gap-3">
        <H2 variant="sm" className="flex items-center gap-2"><Activity className="h-4 w-4" /> Trace Studio</H2>
        <Card><CardContent className="overflow-x-auto py-2">
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted-foreground"><th className="py-2">Quando</th><th>Modelo</th><th>Estado</th><th>Etapas</th><th>Tempo</th><th /></tr></thead>
            <tbody>{traces.map((trace) => <tr key={trace.id} className="border-t border-border"><td className="py-3">{when(trace.started_at)}</td><td>{trace.model || "—"}</td><td><Badge tone={trace.status === "completed" ? "success" : trace.error_count ? "destructive" : "secondary"}>{trace.status}</Badge></td><td>{trace.model_calls} modelo · {trace.tool_calls} ferramentas</td><td>{trace.ended_at ? `${(trace.ended_at - trace.started_at).toFixed(1)}s` : "executando"}</td><td><Button ghost size="sm" onClick={() => void api.getIntelligenceTrace(trace.id).then(setSelected)}>Linha do tempo</Button></td></tr>)}</tbody>
          </table>
        </CardContent></Card>
        {selected && <Card><CardContent className="py-4"><div className="mb-3 flex items-center justify-between"><div><div className="font-medium">{selected.summary || selected.id}</div><div className="text-xs text-muted-foreground">{selected.duration_seconds}s · {selected.input_tokens + selected.output_tokens} tokens · ${selected.estimated_cost_usd.toFixed(6)}</div></div><Button ghost size="icon" onClick={() => setSelected(null)}><X /></Button></div><div className="max-h-96 space-y-2 overflow-auto">{selected.events.map((event) => <div key={event.id} className="flex gap-3 border-l-2 border-border pl-3 text-xs"><span className="w-32 font-mono">{event.event_type}</span><span className="text-muted-foreground">{event.duration_ms ? `${event.duration_ms}ms` : ""}</span><span>{event.status}</span></div>)}</div></CardContent></Card>}
      </section>

      <section className="flex flex-col gap-3">
        <H2 variant="sm" className="flex items-center gap-2"><Check className="h-4 w-4" /> Central de resultados</H2>
        <div className="grid gap-3 lg:grid-cols-2">{results.map((item) => <Card key={item.id}><CardContent className="py-4"><div className="flex items-start justify-between gap-3"><div><div className="font-medium">{item.title}</div><div className="mt-1 line-clamp-3 text-sm text-muted-foreground">{item.summary || item.source_type}</div></div><Badge tone={item.status === "approved" ? "success" : item.status === "failed" ? "destructive" : "secondary"}>{item.status}</Badge></div><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" prefix={<Check className="h-3.5 w-3.5" />} onClick={() => void review(item.id, "approved")}>Aprovar</Button><Button ghost size="sm" prefix={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => void review(item.id, "changes_requested")}>Pedir ajustes</Button><Button ghost size="sm" onClick={() => void api.getReviewResult(item.id).then(setSelectedResult)}>Ver entrega</Button></div></CardContent></Card>)}</div>
        {selectedResult && <Card><CardContent className="py-4"><div className="mb-4 flex items-start justify-between gap-3"><div><div className="font-medium">{selectedResult.title}</div><div className="mt-1 text-sm text-muted-foreground">{selectedResult.summary || "Entrega sem descrição."}</div></div><Button ghost size="icon" onClick={() => setSelectedResult(null)}><X /></Button></div>{selectedResult.artifacts?.length ? <div className="grid gap-2 md:grid-cols-2">{selectedResult.artifacts.map((artifact) => <a key={artifact.id} className="flex items-center justify-between rounded-lg border border-border p-3 text-sm transition-colors hover:bg-muted" href={`${ATHENA_BASE_PATH}/api/intelligence/results/${encodeURIComponent(selectedResult.id)}/artifacts/${encodeURIComponent(artifact.id)}`} download><span><span className="block font-medium">{artifact.name}</span><span className="text-xs text-muted-foreground">versão {artifact.version} · {(artifact.size_bytes / 1024).toFixed(1)} KB</span></span><Download className="h-4 w-4" /></a>)}</div> : <p className="text-sm text-muted-foreground">Esta entrega não possui arquivos anexados.</p>}</CardContent></Card>}
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card><CardContent className="py-4"><GitBranch className="mb-2 h-5 w-5" /><div className="font-medium">Fluxos duráveis</div><p className="text-sm text-muted-foreground">{status?.flows.definitions.length ?? 0} modelos · {status?.flows.counts.waiting ?? 0} aguardando</p></CardContent></Card>
        <Card><CardContent className="py-4"><BrainCircuit className="mb-2 h-5 w-5" /><div className="font-medium">Roteamento adaptativo</div><p className="text-sm text-muted-foreground">{status?.router.observations ?? 0} resultados aprendidos · {status?.router.enabled_candidates.length ?? 0} modelos</p></CardContent></Card>
        <Card><CardContent className="py-4"><Boxes className="mb-2 h-5 w-5" /><div className="font-medium">Pacotes de trabalho</div><p className="text-sm text-muted-foreground">{status?.packages.available.length ?? 0} disponíveis · {status?.packages.installed.length ?? 0} instalados</p></CardContent></Card>
        <Card><CardContent className="py-4"><Network className="mb-2 h-5 w-5" /><div className="font-medium">Rede Athena</div><p className="text-sm text-muted-foreground">{status?.workers.online ?? 0} online · {status?.workers.jobs.queued ?? 0} na fila</p></CardContent></Card>
      </section>
    </div>
  );
}
