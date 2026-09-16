"use client";

import { useId, useMemo, useState, type ReactNode } from "react";
import { KeyRound, LoaderCircle, Pencil, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataText, Empty, LoadError, MiniStat, NameAvatar, PageHead, SearchInput, TableSkeleton } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { RequirePermission } from "@/components/providers/require-permission";
import { ApiError, api } from "@/lib/api/client";
import { useApi, useDepartments } from "@/lib/api/hooks";
import type { Permission, SessionUser, StaffUsersResponse } from "@/lib/api/types";
import { normalizeArabic } from "@/lib/i18n/catalog";
import { cn } from "@/lib/utils";

const NONE = "none";

export function StaffView() {
  return (
    <RequirePermission permission="staff:manage">
      <StaffAdmin />
    </RequirePermission>
  );
}

function StaffAdmin() {
  const { t, fmt, label, dir } = useI18n();
  const { user: me } = useSession();
  const staff = useApi<StaffUsersResponse>("/staff/users");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<SessionUser | null>(null);
  const [creating, setCreating] = useState(false);
  const [passwordFor, setPasswordFor] = useState<SessionUser | null>(null);

  const users = useMemo(() => {
    const needle = normalizeArabic(query.toLowerCase());
    return (staff.data?.users ?? []).filter(
      (u) => !needle || normalizeArabic(`${u.name_ar ?? ""} ${u.name_en ?? ""} ${u.email ?? ""}`.toLowerCase()).includes(needle),
    );
  }, [staff.data, query]);

  const roles = staff.data?.roles ?? {};
  const allPermissions = staff.data?.all_permissions ?? [];
  const activeCount = (staff.data?.users ?? []).filter((u) => u.is_active).length;

  const toggleActive = async (u: SessionUser) => {
    try {
      await api.patch(`/staff/users/${encodeURIComponent(u.id)}`, { is_active: !u.is_active });
      toast.success(t.staff.updated);
      void staff.mutate();
    } catch {
      toast.error(t.staff.saveFailed);
    }
  };

  return (
    <div className="space-y-4">
      <PageHead
        title={t.staff.title}
        sub={t.staff.sub}
        right={
          <Button onClick={() => setCreating(true)}>
            <UserPlus /> {t.staff.add}
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MiniStat label={t.common.total} value={fmt.number(staff.data?.count ?? 0)} highlight />
        <MiniStat label={t.staff.active} value={fmt.number(activeCount)} />
        {(["admin", "committee"] as const).map((role) => (
          <MiniStat
            key={role}
            label={label("role", role)}
            value={fmt.number((staff.data?.users ?? []).filter((u) => u.role === role).length)}
          />
        ))}
      </div>

      <Card>
        <div className="border-b border-line p-4">
          <SearchInput
            placeholder={t.staff.searchPlaceholder}
            aria-label={t.staff.searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {staff.error && !staff.data ? (
          <LoadError onRetry={() => staff.mutate()} />
        ) : staff.isLoading ? (
          <TableSkeleton rows={5} />
        ) : users.length === 0 ? (
          <Empty title={t.staff.empty} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t.staff.name}</TableHead>
                <TableHead>{t.staff.role}</TableHead>
                <TableHead>{t.staff.permissions}</TableHead>
                <TableHead>{t.staff.lastLogin}</TableHead>
                <TableHead>{t.staff.status}</TableHead>
                <TableHead>
                  <span className="sr-only">{t.requests.cols.action}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => {
                const name = (dir === "rtl" ? u.name_ar : u.name_en || u.name_ar) || u.email || u.id;
                const isMe = u.id === me?.id;
                return (
                  <TableRow key={u.id} className={cn("hover:bg-line-soft/50", !u.is_active && "opacity-60")}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <NameAvatar name={name} size={30} />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-ink">
                            <DataText>{name}</DataText>
                            {isMe && <span className="ms-1.5 text-[11px] text-ink-soft">({t.staff.self})</span>}
                          </p>
                          <p className="truncate text-[11.5px] text-ink-soft" dir="ltr">
                            {u.email}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge tone={u.role === "admin" ? "violet" : "brand"}>{label("role", u.role)}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {u.extra_permissions.map((p) => (
                          <Badge key={p} tone="green" title={t.staff.granted}>
                            +{t.permissions[p]}
                          </Badge>
                        ))}
                        {u.revoked_permissions.map((p) => (
                          <Badge key={p} tone="rose" title={t.staff.revoked}>
                            −{t.permissions[p]}
                          </Badge>
                        ))}
                        {!u.extra_permissions.length && !u.revoked_permissions.length && (
                          <span className="text-[12px] text-ink-soft">{t.staff.fromRole}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-[12px] text-ink-muted">
                      {u.last_login_at ? fmt.relative(u.last_login_at) : t.staff.never}
                    </TableCell>
                    <TableCell>
                      <Badge tone={u.is_active ? "green" : "slate"} dot>
                        {u.is_active ? t.staff.active : t.staff.inactive}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(u)}>
                          <Pencil className="size-3.5" /> {t.common.edit}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setPasswordFor(u)} aria-label={t.staff.resetPassword}>
                          <KeyRound className="size-3.5" />
                        </Button>
                        {!isMe && (
                          <Button size="sm" variant={u.is_active ? "ghost" : "soft"} onClick={() => void toggleActive(u)}>
                            {u.is_active ? t.staff.deactivate : t.staff.activate}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      <UserDialog
        open={creating}
        onOpenChange={setCreating}
        roles={roles}
        allPermissions={allPermissions}
        onSaved={() => void staff.mutate()}
      />
      <UserDialog
        key={editing?.id}
        user={editing ?? undefined}
        open={!!editing}
        onOpenChange={(open) => !open && setEditing(null)}
        roles={roles}
        allPermissions={allPermissions}
        isSelf={editing?.id === me?.id}
        onSaved={() => void staff.mutate()}
      />
      <PasswordDialog user={passwordFor} onClose={() => setPasswordFor(null)} />
    </div>
  );
}

/** Label + control, wired together by a generated id (`children` receives it). */
function FieldRow({ label: text, children }: { label: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-[12.5px] font-normal text-ink-muted">
        {text}
      </Label>
      {children(id)}
    </div>
  );
}

function UserDialog({
  user,
  open,
  onOpenChange,
  roles,
  allPermissions,
  isSelf,
  onSaved,
}: {
  user?: SessionUser;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  roles: StaffUsersResponse["roles"];
  allPermissions: Permission[];
  isSelf?: boolean;
  onSaved: () => void;
}) {
  const { t, label } = useI18n();
  const departments = useDepartments();
  const editing = !!user;
  const [form, setForm] = useState({
    email: user?.email ?? "",
    password: "",
    name_ar: user?.name_ar ?? "",
    name_en: user?.name_en ?? "",
    role: user?.role ?? "services",
    department_id: user?.department_id ?? NONE,
    must_change_password: true,
  });
  const [extra, setExtra] = useState<Permission[]>(user?.extra_permissions ?? []);
  const [revoked, setRevoked] = useState<Permission[]>(user?.revoked_permissions ?? []);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const rolePermissions = new Set(roles[form.role]?.permissions ?? []);

  const togglePermission = (permission: Permission, checked: boolean) => {
    const fromRole = rolePermissions.has(permission);
    setExtra((list) => (checked && !fromRole ? [...new Set([...list, permission])] : list.filter((p) => p !== permission)));
    setRevoked((list) => (!checked && fromRole ? [...new Set([...list, permission])] : list.filter((p) => p !== permission)));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const department_id = form.department_id === NONE ? null : form.department_id;
    try {
      if (editing) {
        await api.patch(`/staff/users/${encodeURIComponent(user.id)}`, {
          name_ar: form.name_ar,
          name_en: form.name_en || null,
          ...(isSelf ? {} : { role: form.role }),
          department_id,
          extra_permissions: extra,
          revoked_permissions: revoked,
        });
        toast.success(t.staff.updated);
      } else {
        await api.post("/staff/users", {
          email: form.email.trim(),
          password: form.password,
          name_ar: form.name_ar,
          name_en: form.name_en || null,
          role: form.role,
          department_id,
          must_change_password: form.must_change_password,
        });
        toast.success(t.staff.created);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setError(status === 409 ? t.staff.emailExists : status === 422 ? t.auth.passwordShort : t.staff.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" closeLabel={t.common.close}>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{editing ? t.staff.editTitle : t.staff.addTitle}</DialogTitle>
            <DialogDescription>{t.staff.permissionsHint}</DialogDescription>
          </DialogHeader>
          <DialogBody className="max-h-[60vh] space-y-3 overflow-y-auto">
            {!editing && (
              <>
                <FieldRow label={t.auth.email}>
                  {(id) => (
                    <Input id={id} type="email" dir="ltr" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                  )}
                </FieldRow>
                <FieldRow label={t.staff.temporaryPassword}>
                  {(id) => (
                    <Input
                      id={id}
                      type="text"
                      dir="ltr"
                      required
                      minLength={8}
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                    />
                  )}
                </FieldRow>
                <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-ink-muted">
                  <Switch
                    checked={form.must_change_password}
                    onCheckedChange={(v) => setForm({ ...form, must_change_password: v })}
                  />
                  {t.staff.requireChange}
                </label>
              </>
            )}
            <FieldRow label={t.staff.name}>
              {(id) => (
                <Input id={id} dir="auto" required minLength={2} value={form.name_ar} onChange={(e) => setForm({ ...form, name_ar: e.target.value })} />
              )}
            </FieldRow>
            <FieldRow label={t.staff.nameEn}>
              {(id) => <Input id={id} dir="ltr" value={form.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} />}
            </FieldRow>
            <div className="grid gap-3 sm:grid-cols-2">
              <FieldRow label={t.staff.role}>
                {(id) => (
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })} disabled={isSelf}>
                  <SelectTrigger id={id} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    {Object.keys(roles).map((role) => (
                      <SelectItem key={role} value={role}>
                        {label("role", role)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                )}
              </FieldRow>
              <FieldRow label={t.staff.department}>
                {(id) => (
                <Select value={form.department_id} onValueChange={(v) => setForm({ ...form, department_id: v })}>
                  <SelectTrigger id={id} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    <SelectItem value={NONE}>{t.staff.none}</SelectItem>
                    {(departments.data?.departments ?? []).map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {label("department", d.id, d.name_ar)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                )}
              </FieldRow>
            </div>
            {isSelf && <p className="text-[11.5px] text-amber-700">{t.staff.cannotEditSelf}</p>}

            {editing && (
              <div className="space-y-2 border-t border-line pt-3">
                <p className="text-[12.5px] font-semibold text-ink">{t.staff.permissions}</p>
                <ul className="space-y-1.5">
                  {allPermissions
                    .filter((p) => p !== "admin:all")
                    .map((permission) => {
                      const fromRole = rolePermissions.has(permission);
                      const checked = (fromRole || extra.includes(permission)) && !revoked.includes(permission);
                      return (
                        <li key={permission} className="flex items-start gap-2">
                          <Checkbox
                            id={`perm-${permission}`}
                            checked={checked}
                            onCheckedChange={(v) => togglePermission(permission, v === true)}
                            className="mt-0.5"
                          />
                          <Label htmlFor={`perm-${permission}`} className="cursor-pointer text-[12.5px] font-normal text-ink">
                            {t.permissions[permission]}
                            {fromRole && <span className="ms-1.5 text-[11px] text-ink-soft">({t.staff.fromRole})</span>}
                          </Label>
                        </li>
                      );
                    })}
                </ul>
              </div>
            )}
            {error && (
              <p role="alert" className="text-[12px] text-rose-600">
                {error}
              </p>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              {t.common.cancel}
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <LoaderCircle className="animate-spin" />}
              {t.common.confirm}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PasswordDialog({ user, onClose }: { user: SessionUser | null; onClose: () => void }) {
  const { t } = useI18n();
  const [password, setPassword] = useState("");
  const [requireChange, setRequireChange] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    if (password.length < 8) return setError(t.auth.passwordShort);
    setBusy(true);
    try {
      await api.post(`/staff/users/${encodeURIComponent(user.id)}/set-password`, {
        password,
        must_change_password: requireChange,
      });
      toast.success(t.staff.passwordSet);
      setPassword("");
      onClose();
    } catch {
      setError(t.staff.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!user} onOpenChange={(open) => !open && onClose()}>
      <DialogContent closeLabel={t.common.close}>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{t.staff.resetPasswordTitle}</DialogTitle>
            <DialogDescription dir="ltr">{user?.email}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <FieldRow label={t.staff.temporaryPassword}>
              {(id) => (
                <Input
                  id={id}
                  type="text"
                  dir="ltr"
                  required
                  minLength={8}
                  autoFocus
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </FieldRow>
            <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-ink-muted">
              <Switch checked={requireChange} onCheckedChange={setRequireChange} />
              {t.staff.requireChange}
            </label>
            {error && (
              <p role="alert" className="text-[12px] text-rose-600">
                {error}
              </p>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={onClose} disabled={busy}>
              {t.common.cancel}
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <LoaderCircle className="animate-spin" />}
              {t.staff.resetPassword}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
