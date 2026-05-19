/**
 * Tabs primitive — Radix wrapper with an animate-ui-style sliding pill.
 *
 * The active highlight is rendered as a single absolutely-positioned
 * `motion.div` per TabsList that tracks the active trigger's bounding box
 * via DOM measurement. Switching tabs animates the pill's x + width with
 * a spring. This is more reliable than the layoutId approach for controlled
 * <Tabs value=...> usage where the parent's value prop lags behind the
 * click (e.g. when onValueChange triggers router navigation).
 *
 * Used by:
 *   - meeting detail (workspace ↔ summary)
 *   - meetings/list + meetings/calendar (Kanban / 行事曆)
 *   - any future shadcn-style Tabs surface
 */

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { motion, useReducedMotion } from "motion/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentProps,
} from "react";
import { cn } from "../../lib/utils";

interface TabsContextValue {
  activeValue: string;
  registerTrigger: (value: string, el: HTMLButtonElement | null) => void;
}

const _TabsContext = createContext<TabsContextValue | null>(null);

export function Tabs({
  value,
  defaultValue,
  onValueChange,
  ...props
}: ComponentProps<typeof TabsPrimitive.Root>) {
  // Internal state is authoritative so the pill animates immediately on
  // click, even before a controlled parent's `value` prop catches up (e.g.
  // the router-driven MeetingsViewTabs where navigation is async).
  const [internalActive, setInternalActive] = useState<string>(
    (value as string | undefined) ?? (defaultValue as string | undefined) ?? "",
  );

  // Sync external `value` → internal when the parent confirms a different
  // value. Skipping equal-value syncs avoids feedback loops.
  useEffect(() => {
    if (typeof value === "string" && value !== internalActive) {
      setInternalActive(value);
    }
  }, [value, internalActive]);

  const triggerRefs = useRef<Map<string, HTMLButtonElement | null>>(new Map());
  const registerTrigger = useCallback((v: string, el: HTMLButtonElement | null) => {
    if (el === null) triggerRefs.current.delete(v);
    else triggerRefs.current.set(v, el);
  }, []);

  return (
    <_TabsContext.Provider value={{ activeValue: internalActive, registerTrigger }}>
      <TabsPrimitive.Root
        value={value}
        defaultValue={defaultValue}
        onValueChange={(v) => {
          setInternalActive(v);
          onValueChange?.(v);
        }}
        {...props}
      />
    </_TabsContext.Provider>
  );
}

export function TabsList({
  className,
  children,
  ...props
}: ComponentProps<typeof TabsPrimitive.List>) {
  const ctx = useContext(_TabsContext);
  const listRef = useRef<HTMLDivElement | null>(null);
  const reduced = useReducedMotion();
  const [pill, setPill] = useState<{ x: number; w: number; mounted: boolean }>({
    x: 0,
    w: 0,
    mounted: false,
  });

  // Measure the active trigger's offset / width from inside the TabsList so
  // the pill can slide between them. Re-run when activeValue changes OR on
  // layout shifts (resize) so the pill stays anchored.
  useLayoutEffect(() => {
    if (!ctx || !listRef.current) return;
    function measure() {
      if (!ctx || !listRef.current) return;
      const target = listRef.current.querySelector<HTMLButtonElement>(
        `[data-tabs-trigger-value="${ctx.activeValue}"]`,
      );
      if (!target) return;
      const listBox = listRef.current.getBoundingClientRect();
      const triggerBox = target.getBoundingClientRect();
      setPill({
        x: triggerBox.left - listBox.left,
        w: triggerBox.width,
        mounted: true,
      });
    }
    measure();
    const obs = new ResizeObserver(measure);
    obs.observe(listRef.current);
    return () => obs.disconnect();
  }, [ctx?.activeValue, ctx]);

  return (
    <TabsPrimitive.List
      ref={listRef as React.RefObject<HTMLDivElement>}
      className={cn(
        "relative inline-flex h-10 items-center justify-center rounded-md bg-(--color-muted) p-1 text-(--color-muted-foreground)",
        className,
      )}
      {...props}
    >
      {/* Sliding pill — single element animated between trigger positions. */}
      {pill.mounted ? (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute top-1 bottom-1 rounded-sm bg-(--color-surface) shadow-(--shadow-sm)"
          initial={false}
          animate={{ x: pill.x, width: pill.w }}
          transition={
            reduced ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32, mass: 0.6 }
          }
          style={{ left: 0 }}
        />
      ) : null}
      {children}
    </TabsPrimitive.List>
  );
}

export function TabsTrigger({
  className,
  value,
  children,
  ...props
}: ComponentProps<typeof TabsPrimitive.Trigger>) {
  const ctx = useContext(_TabsContext);
  const ref = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (typeof value !== "string") return;
    ctx?.registerTrigger(value, ref.current);
    return () => ctx?.registerTrigger(value, null);
  }, [ctx, value]);
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      value={value}
      data-tabs-trigger-value={value}
      className={cn(
        "relative z-10 inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium",
        "transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-ring) focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:text-(--color-foreground)",
        className,
      )}
      {...props}
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn(
        "mt-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-ring) focus-visible:ring-offset-2",
        className,
      )}
      {...props}
    />
  );
}
