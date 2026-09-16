import { AgentTestView } from "@/components/views/agent-test-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("agentTest");

export default function Page() {
  return <AgentTestView />;
}
