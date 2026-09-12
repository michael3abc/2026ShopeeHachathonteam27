import { CaseWorkspace } from "@/components/case-workspace";

export default async function CasePage({
  params,
}: {
  params: Promise<{ caseRef: string }>;
}) {
  const { caseRef } = await params;
  return <CaseWorkspace caseRef={caseRef} />;
}
