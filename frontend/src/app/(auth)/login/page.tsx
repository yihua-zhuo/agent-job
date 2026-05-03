"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { login, getMe } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth-store";
import { Providers } from "@/lib/components/providers";

const loginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof loginSchema>;

function LoginForm() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (data) => {
      try {
        const me = await getMe(data.access_token);
        setAuth(data.access_token, me.data);
      } catch {
        setAuth(data.access_token, {
          id: 0, tenant_id: 0,
          username: form.getValues("username"),
          email: "", role: "user", status: "active",
        });
      }
      router.push("/customers");
    },
    onError: (err: Error) => {
      form.setError("password", { message: err.message });
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted px-4">
      <div className="w-full max-w-sm space-y-6 rounded-lg border bg-background p-6 shadow">
        <div className="space-y-1 text-center">
          <h1 className="text-2xl font-bold">Sign In</h1>
          <p className="text-sm text-muted-foreground">Access your CRM workspace</p>
        </div>
        <form onSubmit={form.handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Username</label>
            <input
              {...form.register("username")}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="username"
            />
            {form.formState.errors.username && (
              <p className="text-xs text-destructive">{form.formState.errors.username.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Password</label>
            <input
              {...form.register("password")}
              type="password"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="••••••••"
            />
            {form.formState.errors.password && (
              <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
            )}
          </div>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:pointer-events-none"
          >
            {mutation.isPending ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Providers>
      <LoginForm />
    </Providers>
  );
}
