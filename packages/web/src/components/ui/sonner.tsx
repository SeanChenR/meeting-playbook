/**
 * Toaster — sonner wrapper bound to the project theme tokens.
 * Slice ui-overhaul-claude-design task 1.3.
 *
 * `<Toaster />` MUST be mounted once at the app root (ProtectedShell wraps
 * it). Callsites trigger toasts via `import { toast } from "sonner"` —
 * we re-export `toast` here so consumers can stay on the project barrel
 * instead of importing from the sonner package directly.
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
            "group toast border border-(--color-border) bg-(--color-card) text-(--color-foreground) shadow-md",
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
