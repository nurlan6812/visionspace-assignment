import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Card({
  className,
  stripe = "navy",
  children,
}: Readonly<{
  className?: string;
  stripe?: "navy" | "amber" | "none";
  children: ReactNode;
}>) {
  return (
    <section
      className={cn(
        "relative border border-vision-line bg-white/90 shadow-industrial backdrop-blur-sm",
        "rounded-card",
        stripe !== "none" &&
          "before:absolute before:left-0 before:top-0 before:h-full before:w-1.5 before:content-['']",
        stripe === "navy" && "before:bg-vision-navy",
        stripe === "amber" && "before:bg-vision-amber",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({ className, children }: Readonly<{ className?: string; children: ReactNode }>) {
  return <div className={cn("border-b border-vision-line px-6 py-5", className)}>{children}</div>;
}

export function CardTitle({ children }: Readonly<{ children: ReactNode }>) {
  return <h2 className="text-xl font-bold tracking-tight text-vision-navy">{children}</h2>;
}

export function CardContent({ className, children }: Readonly<{ className?: string; children: ReactNode }>) {
  return <div className={cn("px-6 py-5", className)}>{children}</div>;
}
