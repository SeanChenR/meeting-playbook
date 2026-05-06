import { type ReactNode } from "react";

type Props = {
  children: ReactNode;
  /** Optional small caption shown above the headline. */
  eyebrow?: string;
  headline?: string;
  subhead?: string;
};

/**
 * Centered card scaffold shared by every auth-related route.
 * Hierarchy: wordmark → optional eyebrow → headline → subhead → content slot.
 */
export function AuthShell({
  children,
  eyebrow,
  headline = "Meeting Playbook",
  subhead = "個人 AI 會議助理",
}: Props) {
  return (
    <div className="relative min-h-dvh overflow-hidden bg-(--color-background)">
      {/* Faint corner glow so the page is not totally flat. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[680px] -translate-x-1/2 rounded-full bg-(--color-accent)/5 blur-3xl"
      />
      <main className="relative mx-auto flex min-h-dvh max-w-md flex-col items-stretch justify-center gap-6 px-5 py-14">
        <header className="space-y-2 text-center">
          {eyebrow && (
            <p className="text-xs uppercase tracking-[0.18em] text-(--color-muted-foreground)">
              {eyebrow}
            </p>
          )}
          <h1 className="text-2xl font-semibold tracking-tight text-(--color-foreground)">
            {headline}
          </h1>
          <p className="text-sm text-(--color-muted-foreground)">{subhead}</p>
        </header>
        {children}
        <footer className="text-center text-xs text-(--color-muted-foreground)">
          v0.0.1 · personal preview
        </footer>
      </main>
    </div>
  );
}
