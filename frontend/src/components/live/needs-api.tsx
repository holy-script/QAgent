import { Plug } from "lucide-react";
import { Empty } from "@/components/ui";

export const NeedsApi = ({ what }: { what: string }) => (
  <Empty icon={<Plug className="size-8" />} title="Needs the live API" hint={`${what} come from the backend. Start it with \`make dev\` (the frontend then gets NEXT_PUBLIC_API_URL).`} />
);
