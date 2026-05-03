"use client";
import { useState, useEffect, useRef } from "react";
import { useCurrentUser } from "@/lib/api/queries";
import { useAuthStore } from "@/lib/store/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const { data } = useCurrentUser();
  const me = data?.data;

  const [profile, setProfile] = useState({
    full_name: user?.full_name ?? "",
    email: user?.email ?? "",
    bio: user?.bio ?? "",
  });
  const didHydrateProfile = useRef(false);

  useEffect(() => {
    if (!didHydrateProfile.current && me) {
      setProfile({
        full_name: me.full_name ?? "",
        email: me.email ?? "",
        bio: me.bio ?? "",
      });
      didHydrateProfile.current = true;
    }
  }, [me]);
  const [saved, setSaved] = useState(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleSave() {
    if (savedTimer.current) clearTimeout(savedTimer.current);
    setSaved(true);
    savedTimer.current = setTimeout(() => {
      savedTimer.current = null;
      setSaved(false);
    }, 2000);
  }

  useEffect(() => {
    return () => { if (savedTimer.current) clearTimeout(savedTimer.current); };
  }, []);

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Username</label>
              <Input value={me?.username ?? user?.username ?? ""} disabled className="bg-muted" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Role</label>
              <Input value={me?.role ?? user?.role ?? ""} disabled className="bg-muted" />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="full-name">Full Name</label>
            <Input
              id="full-name"
              value={profile.full_name}
              onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))}
              placeholder="Full Name"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="email">Email</label>
            <Input
              id="email"
              type="email"
              value={profile.email}
              onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
              placeholder="email@example.com"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="bio">Bio</label>
            <Input
              id="bio"
              value={profile.bio}
              onChange={(e) => setProfile((p) => ({ ...p, bio: e.target.value }))}
              placeholder="A short bio about yourself"
            />
          </div>
          <Button onClick={handleSave} disabled={saved}>
            {saved ? "Saved!" : "Save Profile"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Security</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="old-pwd">Current Password</label>
            <Input id="old-pwd" type="password" placeholder="Current password" />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="new-pwd">New Password</label>
            <Input id="new-pwd" type="password" placeholder="Min 8 characters" />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="confirm-pwd">Confirm Password</label>
            <Input id="confirm-pwd" type="password" placeholder="Confirm new password" />
          </div>
          <Button variant="outline">Change Password</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">System Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Tenant ID</span>
            <span className="font-mono">{me?.tenant_id ?? user?.tenant_id ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">User ID</span>
            <span className="font-mono">#{me?.id ?? user?.id ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Status</span>
            <span className="font-mono capitalize">{me?.status ?? user?.status ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Member Since</span>
            {(() => {
              const createdAtRaw = me?.created_at ?? user?.created_at ?? null;
              const createdAt = createdAtRaw ? new Date(String(createdAtRaw)) : null;
              const createdAtStr = createdAt && !Number.isNaN(createdAt.getTime())
                ? createdAt.toLocaleDateString()
                : "—";
              return <span className="font-mono">{createdAtStr}</span>;
            })()}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
