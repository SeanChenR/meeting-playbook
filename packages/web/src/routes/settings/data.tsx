/**
 * /settings/data — slice-19 polish, Sean review round 2.
 *
 * Three equal-height cards in a row (recording retention / export-all /
 * delete-account). Each card carries an animate-ui icon header + centered
 * body. Both action buttons open a localized "Coming soon" dialog instead
 * of dispatching a network call — slice-19 surfaces the entry points; the
 * actions land in a future slice.
 */

import { useState } from "react";
import { Clock, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Download } from "../../components/animate-ui/icons/download";
import { Trash } from "../../components/animate-ui/icons/trash";
import { GradientCardFrame } from "../../components/magicui/gradient-card-frame";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";

export function SettingsData() {
  const { t } = useTranslation();
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <div className="grid auto-rows-fr grid-cols-1 gap-4 md:grid-cols-3">
        {/* ─── Retention card ─────────────────────────────────────────── */}
        <GradientCardFrame
          data-testid="settings-data-retention-card"
          accent="var(--color-primary)"
          accentAlt="var(--color-accent)"
          className="h-full"
          bodyClassName="h-full"
        >
          <div className="flex h-full flex-col rounded-[inherit] p-6">
            <header className="flex items-center justify-center gap-2">
              <Clock className="size-4 text-(--color-primary)" aria-hidden />
              <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
                {t("settings.data.retentionLabel")}
              </h2>
            </header>
            <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6 text-center">
              <p
                data-testid="settings-data-retention"
                className="text-3xl font-bold tracking-tight text-(--color-foreground)"
              >
                {t("settings.data.retention_value")}
              </p>
              <p className="max-w-[16ch] text-xs text-(--color-muted-foreground)">
                {t("settings.data.retentionBody")}
              </p>
            </div>
          </div>
        </GradientCardFrame>

        {/* ─── Export card ────────────────────────────────────────────── */}
        <GradientCardFrame
          data-testid="settings-data-export-card"
          accent="var(--color-accent)"
          accentAlt="var(--color-primary)"
          className="h-full"
          bodyClassName="h-full"
        >
          <div className="flex h-full flex-col rounded-[inherit] p-6">
            <header className="flex items-center justify-center gap-2">
              <Download animate="hover" animateOnHover className="size-4 text-(--color-accent)" />
              <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
                {t("settings.data.export_all")}
              </h2>
            </header>
            <div className="flex flex-1 flex-col items-center justify-center gap-3 py-6 text-center">
              <p className="max-w-[24ch] text-xs text-(--color-muted-foreground)">
                {t("settings.data.exportBody")}
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                data-testid="settings-data-export-all"
                onClick={() => setDialogOpen(true)}
              >
                {t("settings.data.export_all")}
              </Button>
            </div>
          </div>
        </GradientCardFrame>

        {/* ─── Delete account card ────────────────────────────────────── */}
        <GradientCardFrame
          data-testid="settings-data-delete-card"
          accent="var(--color-destructive)"
          accentAlt="var(--color-destructive)"
          className="h-full"
          bodyClassName="h-full"
        >
          <div className="flex h-full flex-col rounded-[inherit] p-6">
            <header className="flex items-center justify-center gap-2">
              <Trash animate="hover" animateOnHover className="size-4 text-(--color-destructive)" />
              <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
                {t("settings.data.delete_account")}
              </h2>
            </header>
            <div className="flex flex-1 flex-col items-center justify-center gap-3 py-6 text-center">
              <p className="max-w-[24ch] text-xs text-(--color-muted-foreground)">
                {t("settings.data.deleteBody")}
              </p>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                data-testid="settings-data-delete-account"
                onClick={() => setDialogOpen(true)}
              >
                <Trash2 className="size-3.5" />
                {t("settings.data.delete_account")}
              </Button>
            </div>
          </div>
        </GradientCardFrame>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="settings-data-coming-soon-dialog">
          <DialogHeader>
            <DialogTitle>{t("settings.data.coming_soon_title")}</DialogTitle>
            <DialogDescription>{t("settings.data.coming_soon_body")}</DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex justify-end">
            <Button
              type="button"
              data-testid="settings-data-coming-soon-close"
              onClick={() => setDialogOpen(false)}
            >
              {t("settings.data.coming_soon_close")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
