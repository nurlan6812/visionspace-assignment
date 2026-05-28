import Link from "next/link";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function TrackShell({
  badge,
  title,
  description,
  children,
}: Readonly<{
  badge: string;
  title: string;
  description: string;
  children: ReactNode;
}>) {
  return (
    <main className="mx-auto max-w-[1560px] px-6 py-7">
      <header className="mb-8 flex flex-col gap-8 border-b border-vision-line pb-7 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <Badge tone="navy">VISION SPACE · AI Developer</Badge>
            <Badge tone="warn">{badge}</Badge>
          </div>
          <h1 className="text-4xl font-black tracking-tight text-vision-navy">{title}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>
        </div>
        <nav className="flex flex-wrap gap-2">
          <Link href="/">
            <Button variant="secondary">전체 보기</Button>
          </Link>
          <Link href="/track1">
            <Button variant="secondary">Track 1</Button>
          </Link>
          <Link href="/track3">
            <Button variant="secondary">Track 3</Button>
          </Link>
        </nav>
      </header>
      {children}
    </main>
  );
}
