import { type HTMLAttributes, useState } from "react";
import { cn } from "../../lib/utils";

type AvatarProps = HTMLAttributes<HTMLSpanElement> & {
  src?: string | null;
  alt?: string;
  /** Single character (or two) to render when there is no image. */
  fallback: string;
};

/**
 * Round avatar with image-or-initials fallback. No external lib —
 * happy-dom-friendly, no portals, no focus traps.
 */
export function Avatar({ src, alt, fallback, className, ...rest }: AvatarProps) {
  const [errored, setErrored] = useState(false);
  const showImage = src && !errored;

  return (
    <span
      {...rest}
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full",
        "bg-(--color-muted) text-(--color-foreground)",
        "text-xs font-medium uppercase",
        className,
      )}
      aria-label={alt ?? rest["aria-label"]}
    >
      {showImage ? (
        <img
          src={src}
          alt={alt ?? ""}
          className="size-full object-cover"
          onError={() => setErrored(true)}
        />
      ) : (
        fallback.slice(0, 2)
      )}
    </span>
  );
}
