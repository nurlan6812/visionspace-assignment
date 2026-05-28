import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "amber" | "secondary" | "ghost";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center border px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "border-vision-navy bg-vision-navy text-white hover:bg-[#12376f]",
        variant === "amber" && "border-vision-amber bg-vision-amber text-white hover:bg-[#b96205]",
        variant === "secondary" && "border-vision-line bg-white text-vision-navy hover:bg-vision-panel",
        variant === "ghost" && "border-transparent bg-transparent text-vision-navy hover:bg-vision-panel",
        className,
      )}
      {...props}
    />
  );
}
