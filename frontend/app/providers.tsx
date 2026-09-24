"use client";

import { AuthProvider } from "@/lib/auth-context";
import { QueryProvider } from "@/lib/query-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <AuthProvider>{children}</AuthProvider>
    </QueryProvider>
  );
}
