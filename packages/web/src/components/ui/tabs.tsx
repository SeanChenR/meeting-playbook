/**
 * Tabs primitive — Radix wrapper with two visual variants:
 *
 *   - `pill` (default) — original animate-ui-style sliding pill behind the
 *     active trigger, sitting on a muted background. Still used by
 *     meetings/list (Kanban / 行事曆), settings sub-nav, etc.
 *
 *   - `underline` — Claude Design style: no muted backdrop, just a 2px
 *     primary-tinted bar that slides along the bottom of the active
 *     trigger. Active text picks up `--color-primary`. The sliding bar
 *     reuses the same DOM-measurement → spring animation as the pill, so
 *     animation feels identical and the layout shift on click is the same.
 *
 * Variant is set via the new `variant` prop on <TabsList>. Default stays
 * "pill" so no existing call site changes behaviour.
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

type TabsVariant = "pill" | "underline";

interface TabsContextValue {
  activeValue: string;
  registerTrigger: (value: string, el: HTMLButtonElement | null) => void;
  variant: TabsVariant;
}

const _TabsContext = createContext<TabsContextValue | null>(null);

interface TabsProps extends ComponentProps<typeof TabsPrimitive.Root> {
  variant?: TabsVariant;
}

export function Tabs({
  value,
  defaultValue,
  onValueChange,
  variant = "pill",
  ...props
}: TabsProps) {
  const [internalActive, setInternalActive] = useState<string>(
    (value as string | undefined) ?? (defaultValue as string | undefined) ?? "",
  );

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
    <_TabsContext.Provider value={{ activeValue: internalActive, registerTrigger, variant }}>
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

  const variant: TabsVariant = ctx?.variant ?? "pill";
  const isUnderline = variant === "underline";

  return (
    <TabsPrimitive.List
      ref={listRef as React.RefObject<HTMLDivElement>}
      data-variant={variant}
      className={cn(
        "relative inline-flex items-center justify-center text-(--color-muted-foreground)",
        isUnderline
          ? "h-10 gap-1 border-b border-(--color-border)/60"
          : "h-10 rounded-md bg-(--color-muted) p-1",
        className,
      )}
      {...props}
    >
      {pill.mounted ? (
        isUnderline ? (
          <motion.span
            aria-hidden
            data-testid="tabs-indicator"
            className="pointer-events-none absolute bottom-[-1px] h-[2px] rounded-full bg-(--color-primary)"
            initial={false}
            animate={{ x: pill.x, width: pill.w }}
            transition={
              reduced ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32, mass: 0.6 }
            }
            style={{ left: 0 }}
          />
        ) : (
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
        )
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
  const isUnderline = ctx?.variant === "underline";
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      value={value}
      data-tabs-trigger-value={value}
      className={cn(
        "relative z-10 inline-flex items-center justify-center whitespace-nowrap text-sm font-medium",
        "transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-ring) focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        isUnderline
          ? "px-3 pt-1 pb-2 text-(--color-muted-foreground) hover:text-(--color-foreground) data-[state=active]:text-(--color-primary)"
          : "rounded-sm px-3 py-1.5 data-[state=active]:text-(--color-foreground)",
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
