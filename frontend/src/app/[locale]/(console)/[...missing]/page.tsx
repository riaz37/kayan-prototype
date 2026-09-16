import { notFound } from "next/navigation";

/** Any unknown path under a locale renders the localised 404 inside the console shell. */
export default function CatchAll() {
  notFound();
}
