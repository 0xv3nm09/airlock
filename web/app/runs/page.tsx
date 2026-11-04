import { redirect } from "next/navigation";

/* Run records now live in the Dashboard's "Runs" table. Keep the old URL working. */
export default function RunsIndex() {
  redirect("/console");
}
