import { useCallback, useEffect, useState } from "react";
import { Box, Camera, Cloud, Play, Plus, RefreshCw, Square, Trash2 } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { api, type EnvironmentCatalog } from "@/lib/api";

function date(value: number) { return value ? new Date(value * 1000).toLocaleString() : "—"; }

export default function EnvironmentsPage() {
  const [catalog, setCatalog] = useState<EnvironmentCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [name, setName] = useState("Ambiente Athena");
  const [image, setImage] = useState("");
  const [ttl, setTtl] = useState(120);
  const [cpu, setCpu] = useState(1);
  const [memory, setMemory] = useState(1024);
  const [persistent, setPersistent] = useState(false);
  const [network, setNetwork] = useState(false);
  const { toast, showToast } = useToast();
  const load = useCallback(async () => {
    try { setCatalog(await api.getEnvironments()); } catch (e) { showToast(String(e), "error"); }
    finally { setLoading(false); }
  }, [showToast]);
  useEffect(() => { void load(); const id = window.setInterval(() => void load(), 10000); return () => clearInterval(id); }, [load]);

  async function create() {
    setBusy("create");
    try {
      await api.createEnvironment({ name, image: image || catalog?.default_image, ttl_minutes: ttl, cpu, memory_mb: memory, persistent, network });
      showToast("Ambiente criado e pronto", "success"); await load();
    } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); }
  }
  async function action(id: string, fn: () => Promise<unknown>, success: string) {
    setBusy(id);
    try { await fn(); showToast(success, "success"); await load(); }
    catch (e) { showToast(String(e), "error"); } finally { setBusy(""); }
  }

  return <div className="flex flex-col gap-6 pb-12">
    <div className="flex items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">Athena Environments</h1><p className="text-sm text-muted-foreground">Crie computadores isolados para tarefas, com prazo, limites e snapshots.</p></div><Button ghost prefix={<RefreshCw className="h-4 w-4"/>} onClick={() => void load()}>Atualizar</Button></div>
    <div className="grid gap-3 md:grid-cols-3">{catalog?.drivers.map(driver => <Card key={driver.id}><CardContent className="py-4"><div className="flex items-center justify-between"><div className="flex items-center gap-2">{driver.managed ? <Box className="h-5 w-5"/> : <Cloud className="h-5 w-5"/>}<span className="font-medium">{driver.name}</span></div><Badge tone={driver.available ? "success" : "destructive"}>{driver.available ? "disponível" : "indisponível"}</Badge></div><p className="mt-2 text-sm text-muted-foreground">{driver.description}</p></CardContent></Card>)}</div>
    <Card><CardContent className="grid gap-4 py-5 md:grid-cols-7"><div className="md:col-span-2"><Label>Nome</Label><Input value={name} onChange={e => setName(e.target.value)}/></div><div className="md:col-span-2"><Label>Imagem</Label><Input placeholder={catalog?.default_image} value={image} onChange={e => setImage(e.target.value)}/></div><div><Label>Duração (min)</Label><Input type="number" value={ttl} onChange={e => setTtl(Number(e.target.value))}/></div><div><Label>CPU</Label><Input type="number" min="0.1" step="0.1" value={cpu} onChange={e => setCpu(Number(e.target.value))}/></div><div><Label>Memória (MB)</Label><Input type="number" value={memory} onChange={e => setMemory(Number(e.target.value))}/></div><div className="flex items-center gap-2"><Switch checked={persistent} onCheckedChange={setPersistent}/><span className="text-sm">Guardar arquivos</span></div><div className="flex items-center gap-2"><Switch checked={network} onCheckedChange={setNetwork}/><span className="text-sm">Permitir internet</span></div><div className="md:col-span-5 flex justify-end"><Button disabled={busy === "create" || !catalog?.drivers[0]?.available} prefix={busy === "create" ? <Spinner/> : <Plus className="h-4 w-4"/>} onClick={() => void create()}>Criar ambiente</Button></div></CardContent></Card>
    <div className="grid gap-3 lg:grid-cols-2">{loading && !catalog ? <Spinner/> : catalog?.environments.map(env => <Card key={env.id}><CardContent className="py-5"><div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-2"><span className="font-medium">{env.name}</span><Badge tone={env.status === "running" ? "success" : env.status === "failed" ? "destructive" : "secondary"}>{env.status}</Badge></div><div className="mt-1 font-mono text-xs text-muted-foreground">{env.image}</div></div><span className="text-xs text-muted-foreground">expira {date(env.expires_at)}</span></div><div className="mt-4 grid grid-cols-3 gap-2 text-xs text-muted-foreground"><span>{env.cpu} CPU</span><span>{env.memory_mb} MB</span><span>{env.persistent ? "persistente" : "descartável"}</span></div><div className="mt-4 flex flex-wrap gap-2">{env.status === "running" ? <Button ghost size="sm" disabled={busy === env.id} prefix={<Square className="h-3.5 w-3.5"/>} onClick={() => void action(env.id, () => api.controlEnvironment(env.id, "stop"), "Ambiente parado")}>Parar</Button> : <Button size="sm" disabled={busy === env.id} prefix={<Play className="h-3.5 w-3.5"/>} onClick={() => void action(env.id, () => api.controlEnvironment(env.id, "start"), "Ambiente iniciado")}>Iniciar</Button>}<Button ghost size="sm" disabled={busy === env.id} prefix={<Camera className="h-3.5 w-3.5"/>} onClick={() => void action(env.id, () => api.snapshotEnvironment(env.id), "Snapshot criado")}>Snapshot</Button><Button ghost size="sm" disabled={busy === env.id} prefix={<Trash2 className="h-3.5 w-3.5"/>} onClick={() => void action(env.id, () => api.deleteEnvironment(env.id), "Ambiente removido")}>Remover</Button></div>{env.snapshots?.length ? <p className="mt-3 text-xs text-muted-foreground">{env.snapshots.length} snapshot(s) disponível(is)</p> : null}</CardContent></Card>)}</div>
    <Toast toast={toast}/>
  </div>;
}
