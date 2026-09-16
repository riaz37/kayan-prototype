/** Re-mounts on navigation so each page fades in, as the original console did. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-enter">{children}</div>;
}
