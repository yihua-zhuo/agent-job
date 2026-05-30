"use client";
import React, { useState, type FormEvent } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface LoginFormData {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginProps {
  onSubmit: (data: LoginFormData) => Promise<void>;
  isLoading?: boolean;
}

export function Login({ onSubmit, isLoading: externalLoading }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [internalLoading, setIsLoading] = useState(false);
  const isLoading = externalLoading ?? internalLoading;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (externalLoading !== undefined) {
      await onSubmit({ email, password, rememberMe });
    } else {
      setIsLoading(true);
      try {
        await onSubmit({ email, password, rememberMe });
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor="email" className="sr-only">Username</label>
        <Input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="username"
          disabled={isLoading}
        />
      </div>
      <div className="space-y-1.5">
        <label htmlFor="password" className="sr-only">Password</label>
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          disabled={isLoading}
        />
      </div>
      <label htmlFor="remember-me" className="flex items-center gap-2 text-sm">
        <input
          id="remember-me"
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
          disabled={isLoading}
        />
        Remember me
      </label>
      <Link
        href="/forgot-password"
        className="text-sm text-muted-foreground hover:underline"
      >
        Forgot password?
      </Link>
      <Button type="submit" disabled={isLoading} className="w-full">
        {isLoading ? "Signing in…" : "Sign In"}
      </Button>
    </form>
  );
}
