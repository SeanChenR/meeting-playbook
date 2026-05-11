/**
 * BackLink — slice ui-overhaul-claude-design task 2.4.
 *
 * Shared primitive for the "回到上一層" action that appears across
 * meeting detail / calendar / new pages. Wraps TanStack Router `<Link>`
 * with the shadcn `ghost` button style + lucide `ArrowLeft` icon.
 *
 * Default copy lives in i18n key `nav.backToList` ("返回列表" / "Back to list").
 * Pass `labelKey` to override (e.g. "nav.back" for a generic "返回" / "Back").
 */

import { Link, type LinkProps } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "../lib/utils";
import { buttonVariants } from "./ui/button";

type BackLinkProps = {
  to: LinkProps["to"];
  params?: LinkProps["params"];
  search?: LinkProps["search"];
  /** i18n key for the label text. Defaults to `nav.backToList`. */
  labelKey?: string;
  className?: string;
};

export function BackLink({
  to,
  params,
  search,
  labelKey = "nav.backToList",
  className,
}: BackLinkProps) {
  const { t } = useTranslation();

  return (
    <Link
      to={to}
      params={params}
      search={search}
      data-testid="back-link"
      className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-1.5", className)}
    >
      <ArrowLeft className="size-4" aria-hidden />
      <span>{t(labelKey)}</span>
    </Link>
  );
}
