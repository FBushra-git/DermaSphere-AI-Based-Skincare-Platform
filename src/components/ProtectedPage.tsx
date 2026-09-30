"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

type Role = "customer" | "seller" | "admin";
export function ProtectedPage({ role, children }: { role: Role; children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready && !user) {
      const destination = `${window.location.pathname}${window.location.search}`;
      router.replace(`/login?next=${encodeURIComponent(destination)}`);
    }
    else if (ready && user && user.role !== role) router.replace(user.role === "admin" ? "/admin" : user.role === "seller" ? "/seller" : "/customer");
  }, [ready, user, role, router]);
  if (!ready || !user || user.role !== role) return <main className="protected-loading"><span>✿</span><p>Opening your DermaSphere space…</p></main>;
  return <>{children}</>;
}
