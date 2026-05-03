"use client";
import { useState, useEffect, useRef } from "react";
import { useCurrentUser, useUpdateProfile, useChangePassword } from "@/lib/api/queries";
import { useAuthStore } from "@/lib/store/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const { data } = useCurrentUser();
  const me = data?.data;
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  const [profile, setProfile] = useState({
    full_name: user?.full_name ?? "",
    email: user?.email ?? "",
    bio: user?.bio ?? "",
  });
  const didHydrateProfile = useRef(false);
  const hasUserEditedProfile = useRef(false);

  useEffect(() => {
    if (!didHydrateProfile.current && me && !hasUserEditedProfile.current) {
      setProfile({
        full_name: me.full_name ?? "",
        email: me.email ?? "",
        bio: me.bio ?? "",
      });
      didHydrateProfile.current = true;
    }
  }, [me]);

  async function handleSave() {
    try {
      await updateProfile.mutateAsync(profile);
    } catch {
      // error surfaced via updateProfile.isError
    }
  }

  const [pwForm, setPwForm] = useState({ old_password: "", new_password: "", confirm: "" });
  const [pwError, setPwError] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);
  const pwTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleChangePassword() {
    if (pwForm.new_password !== pwForm.confirm) {
      setPwError("Passwords do not match");
      return;
    }
    if (pwForm.new_password.length < 8) {
      setPwError("Password must be at least 8 characters");
      return;
    }
    setPwError("");
    try {
      await changePassword.mutateAsync({ old_password: pwForm.old_password, new_password: pwForm.new_password });
      setPwForm({ old_password: "", new_password: "", confirm: "" });
      setPwSuccess(true);
      if (pwTimer.current) clearTimeout(pwTimer.current);
      pwTimer.current = setTimeout(() => { pwTimer.current = null; setPwSuccess(false); }, 3000);
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to change password");
    }
  }

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
              onChange={(e) => { hasUserEditedProfile.current = true; setProfile((p) => ({ ...p, full_name: e.target.value })); }}
              placeholder="Full Name"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="email">Email</label>
            <Input
              id="email"
              type="email"
              value={profile.email}
              onChange={(e) => { hasUserEditedProfile.current = true; setProfile((p) => ({ ...p, email: e.target.value })); }}
              placeholder="email@example.com"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="bio">Bio</label>
            <Input
              id="bio"
              value={profile.bio}
              onChange={(e) => { hasUserEditedProfile.current = true; setProfile((p) => ({ ...p, bio: e.target.value })); }}
              placeholder="A short bio about yourself"
            />
          </div>
          <Button
            onClick={handleSave}
            disabled={updateProfile.isPending}
          >
            {updateProfile.isPending ? "Saving…" : updateProfile.isSuccess ? "Saved!" : "Save Profile"}
          </Button>
          {updateProfile.isError && (
            <p className="text-xs text-destructive">Failed to save profile</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Security</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="old-pwd">Current Password</label>
            <Input
              id="old-pwd"
              type="password"
              placeholder="Current password"
              value={pwForm.old_password}
              onChange={(e) => setPwForm((p) => ({ ...p, old_password: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="new-pwd">New Password</label>
            <Input
              id="new-pwd"
              type="password"
              placeholder="Min 8 characters"
              value={pwForm.new_password}
              onChange={(e) => setPwForm((p) => ({ ...p, new_password: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="confirm-pwd">Confirm Password</label>
            <Input
              id="confirm-pwd"
              type="password"
              placeholder="Confirm new password"
              value={pwForm.confirm}
              onChange={(e) => setPwForm((p) => ({ ...p, confirm: e.target.value }))}
            />
          </div>
          {pwError && <p className="text-xs text-destructive">{pwError}</p>}
          {pwSuccess && <p className="text-xs text-green-600">Password changed successfully</p>}
          <Button
            variant="outline"
            onClick={handleChangePassword}
            disabled={changePassword.isPending || !pwForm.old_password || !pwForm.new_password || !pwForm.confirm}
          >
            {changePassword.isPending ? "Changing…" : "Change Password"}
          </Button>
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
