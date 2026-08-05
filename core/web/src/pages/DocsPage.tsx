import { useLayoutEffect } from "react";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";
import { PluginSlot } from "@/plugins";

export default function DocsPage() {
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  useLayoutEffect(() => {
    setEnd(null);
    return () => setEnd(null);
  }, [setEnd]);

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", "pt-1 sm:pt-2")}>
      <PluginSlot name="docs:top" />
      <section
        className={cn(
          "mx-auto mt-8 w-full max-w-3xl rounded-sm border border-current/20",
          "bg-background p-6 text-foreground shadow-sm",
        )}
      >
        <h1 className="mb-3 text-2xl font-bold">{t.app.nav.documentation}</h1>
        <p className="mb-4 text-sm text-midground">
          Athena documentation is bundled with the source checkout. No inherited
          documentation service is contacted by this independent build.
        </p>
        <div className="space-y-2 font-mono text-sm">
          <div>athena --help</div>
          <div>athena &lt;command&gt; --help</div>
          <div>README.md</div>
        </div>
      </section>
      <PluginSlot name="docs:bottom" />
    </div>
  );
}
