import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, CirclePause, MessageSquarePlus, Play, Plus, RefreshCw, RotateCw, Send, Users } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { api, type MissionControlResponse, type MissionTask } from "@/lib/api";

const COLUMNS = ["triage", "todo", "ready", "running", "blocked", "review", "done"];
const LABELS: Record<string, string> = { triage: "Triagem", todo: "Planejadas", ready: "Prontas", running: "Em execução", blocked: "Pausadas", review: "Revisão", done: "Concluídas" };

export default function MissionControlPage() {
  const [data, setData] = useState<MissionControlResponse | null>(null);
  const [board, setBoard] = useState("");
  const [selected, setSelected] = useState<MissionTask | null>(null);
  const [title, setTitle] = useState(""); const [body, setBody] = useState(""); const [assignee, setAssignee] = useState("");
  const [instruction, setInstruction] = useState(""); const [busy, setBusy] = useState("");
  const { toast, showToast } = useToast();
  const load = useCallback(async () => {
    try { const next = await api.getMissionControl(board); setData(next); if (!board) setBoard(next.board); setSelected(old => old ? next.tasks.find(t => t.id === old.id) ?? null : null); }
    catch (e) { showToast(String(e), "error"); }
  }, [board, showToast]);
  useEffect(() => { void load(); const id = window.setInterval(() => void load(), 4000); return () => clearInterval(id); }, [load]);
  const groups = useMemo(() => Object.fromEntries(COLUMNS.map(status => [status, data?.tasks.filter(task => task.status === status) ?? []])), [data]);

  async function createTask() {
    if (!title.trim()) return; setBusy("create");
    try { await api.createMissionTask({ board, title, body, assignee, goal_mode: true }); setTitle(""); setBody(""); showToast("Missão criada", "success"); await load(); }
    catch (e) { showToast(String(e), "error"); } finally { setBusy(""); }
  }
  async function act(action: string, nextAssignee = "") {
    if (!selected) return; setBusy(action);
    try { await api.actOnMissionTask(selected.id, { board, action, assignee: nextAssignee }); showToast("Comando enviado", "success"); await load(); }
    catch (e) { showToast(String(e), "error"); } finally { setBusy(""); }
  }
  async function send() {
    if (!selected || !instruction.trim()) return; setBusy("instruction");
    try { await api.instructMissionTask(selected.id, { board, message: instruction }); setInstruction(""); showToast("Instrução registrada", "success"); await load(); }
    catch (e) { showToast(String(e), "error"); } finally { setBusy(""); }
  }

  return <div className="flex flex-col gap-6 pb-12">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">Central de Missão</h1><p className="text-sm text-muted-foreground">Veja a equipe pensar, divida trabalhos e intervenha durante a execução.</p></div><div className="flex gap-2"><Select value={board} onValueChange={setBoard}>{data?.boards.map(item => <SelectOption key={item.slug} value={item.slug}>{item.name || item.slug}</SelectOption>)}</Select><Button ghost prefix={<RefreshCw className="h-4 w-4"/>} onClick={() => void load()}>Atualizar</Button></div></div>
    <div className="grid gap-3 md:grid-cols-4"><Card><CardContent className="py-4"><Users className="mb-2 h-5 w-5"/><div className="text-2xl font-semibold">{data?.agents.length ?? 0}</div><div className="text-xs text-muted-foreground">agentes envolvidos</div></CardContent></Card><Card><CardContent className="py-4"><Bot className="mb-2 h-5 w-5"/><div className="text-2xl font-semibold">{data?.stats.by_status.running ?? 0}</div><div className="text-xs text-muted-foreground">trabalhando agora</div></CardContent></Card><Card><CardContent className="py-4"><CirclePause className="mb-2 h-5 w-5"/><div className="text-2xl font-semibold">{(data?.stats.by_status.blocked ?? 0) + (data?.stats.by_status.triage ?? 0)}</div><div className="text-xs text-muted-foreground">pedem atenção</div></CardContent></Card><Card><CardContent className="py-4"><div className="text-2xl font-semibold">{data?.workers.online ?? 0}</div><div className="text-xs text-muted-foreground">máquinas trabalhadoras online</div></CardContent></Card></div>
    <Card><CardContent className="grid gap-3 py-4 lg:grid-cols-5"><div><Label>Título da missão</Label><Input value={title} onChange={e => setTitle(e.target.value)}/></div><div className="lg:col-span-2"><Label>Instruções</Label><Input value={body} onChange={e => setBody(e.target.value)}/></div><div><Label>Agente</Label><Input placeholder="automático" value={assignee} onChange={e => setAssignee(e.target.value)}/></div><div className="flex items-end"><Button disabled={busy === "create"} prefix={busy === "create" ? <Spinner/> : <Plus className="h-4 w-4"/>} onClick={() => void createTask()}>Criar e executar</Button></div></CardContent></Card>
    <div className="grid auto-cols-[minmax(250px,1fr)] grid-flow-col gap-3 overflow-x-auto pb-3">{COLUMNS.map(status => <section key={status} className="min-h-72 rounded-lg border border-border bg-muted/20 p-3"><div className="mb-3 flex items-center justify-between text-sm font-medium"><span>{LABELS[status]}</span><Badge tone="secondary">{groups[status].length}</Badge></div><div className="space-y-2">{groups[status].map(task => <button key={task.id} className="w-full rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted" onClick={() => setSelected(task)}><div className="font-medium">{task.title}</div><div className="mt-2 flex items-center justify-between text-xs text-muted-foreground"><span>{task.assignee || "roteamento automático"}</span><span>{task.id}</span></div>{task.latest_run?.summary ? <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{task.latest_run.summary}</p> : null}</button>)}</div></section>)}</div>
    {selected && <Card><CardContent className="py-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-lg font-medium">{selected.title}</div><p className="mt-1 max-w-4xl text-sm text-muted-foreground">{selected.body || "Sem descrição."}</p></div><Badge tone={selected.status === "done" ? "success" : selected.status === "blocked" ? "destructive" : "secondary"}>{selected.status}</Badge></div><div className="mt-4 flex flex-wrap gap-2">{selected.status === "running" ? <Button ghost size="sm" prefix={<CirclePause className="h-4 w-4"/>} onClick={() => void act("pause")}>Pausar</Button> : <Button size="sm" prefix={<Play className="h-4 w-4"/>} onClick={() => void act("resume")}>Retomar</Button>}<Button ghost size="sm" prefix={<RotateCw className="h-4 w-4"/>} onClick={() => void act("retry")}>Tentar novamente</Button><Input className="max-w-44" placeholder="novo agente" onKeyDown={e => { if (e.key === "Enter") void act("reassign", e.currentTarget.value); }}/></div><div className="mt-5 flex gap-2"><Input value={instruction} onChange={e => setInstruction(e.target.value)} placeholder="Envie uma orientação para este agente..." onKeyDown={e => { if (e.key === "Enter") void send(); }}/><Button prefix={busy === "instruction" ? <Spinner/> : <Send className="h-4 w-4"/>} onClick={() => void send()}>Enviar</Button></div>{selected.comments.length ? <div className="mt-4 space-y-2">{selected.comments.map(comment => <div key={comment.id} className="rounded-lg border-l-2 border-primary bg-muted/30 p-3 text-sm"><div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground"><MessageSquarePlus className="h-3.5 w-3.5"/>{comment.author}</div>{comment.body}</div>)}</div> : null}</CardContent></Card>}
    <Toast toast={toast}/>
  </div>;
}
