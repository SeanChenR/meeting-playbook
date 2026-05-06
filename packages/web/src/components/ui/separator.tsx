import { type HTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

type Orientation = "horizontal" | "vertical";

export type SeparatorProps = HTMLAttributes<HTMLDivElement> & {
  orientation?: Orientation;
};

export const Separator = forwardRef<HTMLDivElement, SeparatorProps>(
  ({ className, orientation = "horizontal", ...props }, ref) => (
    <div
      ref={ref}
      role="separator"
      aria-orientation={orientation}
      className={cn(
        "shrink-0 bg-(--color-border)",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className,
      )}
      {...props}
    />
  ),
);
Separator.displayName = "Separator";
