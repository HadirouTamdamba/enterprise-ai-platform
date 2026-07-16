"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3,
  BotMessageSquare,
  Database,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  Moon,
  ShieldCheck,
  Sun,
  Users,
} from "lucide-react";
import { clearTokens } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/rag", label: "RAG Studio", icon: Database },
  { href: "/playground", label: "Playground", icon: MessagesSquare },
  { href: "/agents", label: "Agents", icon: BotMessageSquare },
  { href: "/monitoring", label: "Monitoring", icon: BarChart3 },
  { href: "/governance", label: "Governance", icon: ShieldCheck },
  { href: "/admin", label: "Administration", icon: Users },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("eap_access_token")) router.replace("/login");
    const stored = localStorage.getItem("eap_theme") === "dark";
    setDark(stored);
    document.documentElement.classList.toggle("dark", stored);
  }, [router]);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    localStorage.setItem("eap_theme", next ? "dark" : "light");
    document.documentElement.classList.toggle("dark", next);
  }

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 flex w-60 flex-col border-r border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-8 px-2">
          <p className="text-lg font-bold">Enterprise AI</p>
          <p className="text-xs text-zinc-500">Platform Console</p>
        </div>
        <nav className="flex-1 space-y-1">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
                pathname.startsWith(href)
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-100"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="space-y-1 border-t border-zinc-200 pt-4 dark:border-zinc-800">
          <button
            onClick={toggleTheme}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {dark ? "Light mode" : "Dark mode"}
          </button>
          <button
            onClick={() => {
              clearTokens();
              router.replace("/login");
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>
      <main className="ml-60 flex-1 p-8">{children}</main>
    </div>
  );
}
