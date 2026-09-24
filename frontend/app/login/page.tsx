"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Loader2, Truck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiRequestError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

const DEMO_ACCOUNTS = [
  { label: "Admin", email: "admin@supplychain-demo.com" },
  { label: "Operations Manager", email: "ops@supplychain-demo.com" },
  { label: "Analyst", email: "analyst@supplychain-demo.com" },
  { label: "Viewer", email: "viewer@supplychain-demo.com" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "DemoPass123!" } });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    setIsSubmitting(true);
    try {
      await login(values.email, values.password);
    } catch (err) {
      setServerError(err instanceof ApiRequestError ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Truck className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-semibold">AI Supply Chain Intelligence</h1>
          <p className="text-sm text-muted-foreground">Sign in to your operations workspace</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 rounded-lg border bg-card p-6 shadow-sm">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input id="email" type="email" placeholder="you@company.com" {...register("email")} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <Input id="password" type="password" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>

          {serverError && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {serverError}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign in
          </Button>
        </form>

        <div className="rounded-lg border bg-card p-4 text-xs text-muted-foreground">
          <p className="mb-2 font-medium text-foreground">Demo accounts (password: DemoPass123!)</p>
          <div className="grid grid-cols-2 gap-1.5">
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.email}
                type="button"
                onClick={() => setValue("email", acct.email)}
                className="rounded border px-2 py-1 text-left hover:bg-accent"
              >
                {acct.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
