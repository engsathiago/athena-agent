import { useCallback, useEffect, useMemo, useState } from "react";
import { Cable, MessageCircle, Package, Plug, RefreshCw, Search } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { api, type IntegrationStoreItem, type IntegrationStoreResponse } from "@/lib/api";

const destinations = { mcp: "/mcp", plugin: "/plugins", channel: "/channels" };
const icons = { mcp: Plug, plugin: Package, channel: MessageCircle };

export default function IntegrationStorePage() {
  const [store, setStore] = useState<IntegrationStoreResponse | null>(null);
  const [query, setQuery] = useState(""); const [kind, setKind] = useState("all");
  const { toast, showToast } = useToast();
  const load = useCallback(async () => { try { setStore(await api.getIntegrationStore()); } catch (e) { showToast(String(e), "error"); } }, [showToast]);
  useEffect(() => { void load(); }, [load]);
  const rows = useMemo(() => (store?.items ?? []).filter(item => {
    const matchKind = kind === "all" || item.kind === kind; const text = `${item.name} ${item.description} ${item.source}`.toLowerCase();
    return matchKind && text.includes(query.toLowerCase());
  }), [store, query, kind]);
  return <div className="flex flex-col gap-6 pb-12">
    <div className="flex items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">Loja de Integrações</h1><p className="text-sm text-muted-foreground">Um único lugar para conectar ferramentas, extensões e canais à Athena.</p></div><Button ghost prefix={<RefreshCw className="h-4 w-4"/>} onClick={() => void load()}>Atualizar</Button></div>
    <div className="grid gap-3 md:grid-cols-3"><Card><CardContent className="py-4"><div className="text-2xl font-semibold">{store?.counts.total ?? 0}</div><div className="text-xs text-muted-foreground">integrações encontradas</div></CardContent></Card><Card><CardContent className="py-4"><div className="text-2xl font-semibold">{store?.counts.installed ?? 0}</div><div className="text-xs text-muted-foreground">configuradas</div></CardContent></Card><Card><CardContent className="py-4"><div className="text-2xl font-semibold">{store?.counts.enabled ?? 0}</div><div className="text-xs text-muted-foreground">ativas</div></CardContent></Card></div>
    <div className="flex flex-wrap gap-2"><div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground"/><Input className="pl-9" placeholder="Buscar integração..." value={query} onChange={e => setQuery(e.target.value)}/></div>{["all", "mcp", "plugin", "channel"].map(value => <Button key={value} ghost={kind !== value} onClick={() => setKind(value)}>{value === "all" ? "Todas" : value === "mcp" ? "Ferramentas" : value === "plugin" ? "Extensões" : "Canais"}</Button>)}</div>
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{rows.map(item => <IntegrationCard key={item.id} item={item}/>)}</div>
    <Card><CardContent className="flex items-center gap-3 py-4"><Cable className="h-5 w-5"/><div><div className="font-medium">Instalação externa</div><p className="text-sm text-muted-foreground">Os catálogos continuam aceitando servidores MCP personalizados e plugins por endereço Git.</p></div></CardContent></Card><Toast toast={toast}/>
  </div>;
}

function IntegrationCard({ item }: { item: IntegrationStoreItem }) {
  const Icon = icons[item.kind];
  return <Card><CardContent className="flex h-full flex-col py-5"><div className="flex items-start justify-between gap-3"><div className="flex items-center gap-3"><div className="rounded-lg bg-muted p-2"><Icon className="h-5 w-5"/></div><div><div className="font-medium">{item.name}</div><div className="text-xs text-muted-foreground">{item.source}</div></div></div><Badge tone={item.enabled ? "success" : item.installed ? "warning" : "secondary"}>{item.enabled ? "ativo" : item.installed ? "instalado" : "disponível"}</Badge></div><p className="mt-4 flex-1 text-sm text-muted-foreground">{item.description}</p><div className="mt-4 flex items-center justify-between"><span className="text-xs text-muted-foreground">{item.auth_type === "none" ? "sem autenticação" : `acesso: ${item.auth_type}`}</span><Button size="sm" onClick={() => window.location.assign(destinations[item.kind])}>{item.installed ? "Gerenciar" : "Instalar"}</Button></div></CardContent></Card>;
}
