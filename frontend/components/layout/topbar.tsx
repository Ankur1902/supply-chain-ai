"use client";

import { LogOut, User as UserIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

export function Topbar() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-end border-b bg-card px-4 md:px-6">
      <div className="flex items-center gap-3">
        {user && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <UserIcon className="h-4 w-4" />
            <span className="hidden sm:inline">{user.full_name}</span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium capitalize text-foreground">
              {user.roles[0]?.replace("_", " ")}
            </span>
          </div>
        )}
        <Button variant="ghost" size="icon" onClick={logout} title="Log out">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
