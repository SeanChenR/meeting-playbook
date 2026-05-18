/**
 * Toaster — sonner wrapper bound to the Aura theme tokens.
 * ui-overhaul-primitive-upgrade task 8 (Decision 2: 4 semantic variants).
 *
 * it). Callsites use the semantic helpers via the re-exported `toast`:
 *   toast.info("...", { description: "..." })
 *   toast.success("...") / .warning(...) / .error(...)
 *
 * Stripe colour per variant is wired via `[data-sonner-toast][data-type=...]`
 * attribute selectors in `index.css` (set by P1 `ui-overhaul-aura-tokens`
 * D7) — keeps raw token refs out of component className strings. P2 layers
 * the semantic helper API + the surface/border/shadow token bindings below.
 */

import { Toaster as SonnerToaster, toast } from "sonner";
import { useTheme } from "../../lib/theme-provider";

export type { ToasterProps } from "sonner";

export function Toaster(props: React.ComponentProps<typeof SonnerToaster>) {
  const { resolved } = useTheme();
  return (
    <SonnerToaster
      theme={resolved}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast relative overflow-hidden border border-(--color-border) bg-(--color-surface) text-(--color-foreground) shadow-(--shadow-lg)",
          description: "text-(--color-muted-foreground)",
          actionButton: "bg-(--color-primary) text-(--color-primary-foreground)",
          cancelButton: "bg-(--color-muted) text-(--color-muted-foreground)",
        },
      }}
      {...props}
    />
  );
}

export { toast };
