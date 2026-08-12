import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Eye, FilePlus2, FileText, Globe, Image, Presentation, RefreshCw, Save, Sheet, Trash2, Upload } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { api, ATHENA_BASE_PATH, type StudioArtifact, type StudioCatalog } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

const templates = [
  { id: "document", label: "Documento", icon: FileText }, { id: "presentation", label: "Apresentação", icon: Presentation },
  { id: "spreadsheet", label: "Planilha", icon: Sheet }, { id: "website", label: "Site", icon: Globe },
  { id: "diagram", label: "Diagrama", icon: Image }, { id: "note", label: "Nota", icon: FilePlus2 },
];

export default function StudioPage() {
  const [catalog, setCatalog] = useState<StudioCatalog | null>(null); const [selected, setSelected] = useState<StudioArtifact | null>(null);
  const [content, setContent] = useState(""); const [busy, setBusy] = useState(""); const uploadRef = useRef<HTMLInputElement>(null);
  const { toast, showToast } = useToast();
  const load = useCallback(async () => { try { setCatalog(await api.getStudio()); } catch (e) { showToast(String(e), "error"); } }, [showToast]);
  useEffect(() => { void load(); }, [load]);
  async function open(item: StudioArtifact) { setBusy("open"); try { const detail = await api.getStudioArtifact(item.id); setSelected(detail); setContent(detail.content ?? ""); } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); } }
  async function create(kind: string) { setBusy("create"); try { const item = await api.createStudioArtifact({ kind }); await load(); await open(item); } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); } }
  async function save() { if (!selected) return; setBusy("save"); try { const item = await api.saveStudioArtifact(selected.id, content, selected.title); setSelected(item); showToast("Nova versão salva", "success"); await load(); } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); } }
  async function publish() { if (!selected) return; setBusy("publish"); try { const result = await api.publishStudioArtifact(selected.id); setSelected(result.artifact); showToast("Publicado na Central de Resultados", "success"); await load(); } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); } }
  async function remove() { if (!selected) return; setBusy("delete"); try { await api.deleteStudioArtifact(selected.id); setSelected(null); setContent(""); await load(); showToast("Arquivo removido", "success"); } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); } }
  async function upload(file?: File) { if (!file) return; setBusy("upload"); try { const item = await api.importStudioArtifact(file); await load(); await open(item); showToast("Arquivo importado", "success"); } catch (e) { showToast(String(e), "error"); } finally { setBusy(""); } }
  const contentUrl = selected ? `${ATHENA_BASE_PATH}/api/studio/${encodeURIComponent(selected.id)}/content` : "";

  return <div className="flex flex-col gap-6 pb-12">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Athena Studio</h1><p className="text-sm text-muted-foreground">Crie, edite, visualize, versione e publique os arquivos produzidos pelos agentes.</p></div><div className="flex gap-2"><input ref={uploadRef} className="hidden" type="file" onChange={e => void upload(e.target.files?.[0])}/><Button ghost prefix={<Upload className="h-4 w-4"/>} onClick={() => uploadRef.current?.click()}>Importar</Button><Button ghost prefix={<RefreshCw className="h-4 w-4"/>} onClick={() => void load()}>Atualizar</Button></div></div>
    <div className="grid grid-cols-2 gap-2 md:grid-cols-6">{templates.map(template => { const Icon = template.icon; return <Button key={template.id} ghost className="h-auto justify-start py-3" prefix={<Icon className="h-4 w-4"/>} onClick={() => void create(template.id)}>{template.label}</Button>; })}</div>
    <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]"><Card><CardContent className="max-h-[72vh] overflow-auto py-3">{catalog?.artifacts.length ? catalog.artifacts.map(item => <button key={item.id} className={`mb-2 w-full rounded-lg border p-3 text-left ${selected?.id === item.id ? "border-primary bg-primary/5" : "border-border hover:bg-muted"}`} onClick={() => void open(item)}><div className="font-medium">{item.title}</div><div className="mt-1 flex items-center justify-between text-xs text-muted-foreground"><span>{item.filename}</span><Badge tone="secondary">v{item.version}</Badge></div></button>) : <p className="py-8 text-center text-sm text-muted-foreground">Crie ou importe seu primeiro arquivo.</p>}</CardContent></Card>
      <Card><CardContent className="py-4">{busy === "open" ? <Spinner/> : selected ? <div className="flex flex-col gap-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><Input className="text-lg font-medium" value={selected.title} onChange={e => setSelected({ ...selected, title: e.target.value })}/><div className="mt-1 text-xs text-muted-foreground">{selected.filename} · {(selected.size_bytes / 1024).toFixed(1)} KB · versão {selected.version}</div></div><div className="flex gap-2">{selected.editable ? <Button prefix={busy === "save" ? <Spinner/> : <Save className="h-4 w-4"/>} onClick={() => void save()}>Salvar versão</Button> : null}<Button ghost prefix={<Eye className="h-4 w-4"/>} onClick={() => void publish()}>Publicar</Button><Button ghost prefix={<Download className="h-4 w-4"/>} onClick={() => window.location.assign(`${contentUrl}?download=true`)}>Baixar</Button><Button ghost size="icon" onClick={() => void remove()}><Trash2 className="h-4 w-4"/></Button></div></div><div className="grid min-h-[58vh] gap-3 lg:grid-cols-2">{selected.editable ? <textarea className="min-h-[58vh] resize-none rounded-lg border border-border bg-background p-4 font-mono text-sm outline-none focus:border-primary" value={content} onChange={e => setContent(e.target.value)}/> : <div className="grid place-content-center rounded-lg border border-border text-muted-foreground">Este formato é visualizado ao lado.</div>}<Preview item={selected} content={content} url={contentUrl}/></div></div> : <div className="grid min-h-[60vh] place-content-center text-center text-muted-foreground"><FileText className="mx-auto mb-3 h-10 w-10"/><p>Selecione um arquivo para abrir o estúdio.</p></div>}</CardContent></Card></div><Toast toast={toast}/>
  </div>;
}

function Preview({ item, content, url }: { item: StudioArtifact; content: string; url: string }) {
  if (item.preview_kind === "html") return <iframe title={item.title} className="min-h-[58vh] w-full rounded-lg border border-border bg-white" sandbox="allow-scripts" srcDoc={content}/>;
  if (item.preview_kind === "markdown") return <div className="min-h-[58vh] overflow-auto rounded-lg border border-border bg-background p-5"><Markdown content={content}/></div>;
  if (item.preview_kind === "image") return <div className="grid min-h-[58vh] place-content-center overflow-auto rounded-lg border border-border bg-black/10 p-3"><img className="max-h-[54vh] max-w-full" src={item.editable ? `data:${item.media_type};utf8,${encodeURIComponent(content)}` : url} alt={item.title}/></div>;
  if (["pdf", "audio", "video"].includes(item.preview_kind)) return <iframe title={item.title} className="min-h-[58vh] w-full rounded-lg border border-border bg-white" src={url}/>;
  if (item.preview_kind === "csv") return <CsvPreview content={content}/>;
  return <pre className="min-h-[58vh] overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/20 p-4 text-sm">{content || "Prévia não disponível. Use Baixar para abrir este arquivo."}</pre>;
}

function CsvPreview({ content }: { content: string }) {
  const rows = content.split(/\r?\n/).filter(Boolean).slice(0, 100).map(line => line.split(","));
  return <div className="min-h-[58vh] overflow-auto rounded-lg border border-border"><table className="w-full text-sm"><tbody>{rows.map((row, i) => <tr key={i} className={i ? "border-t border-border" : "bg-muted font-medium"}>{row.map((cell, j) => <td key={j} className="px-3 py-2">{cell}</td>)}</tr>)}</tbody></table></div>;
}
