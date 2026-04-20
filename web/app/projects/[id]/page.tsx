import { redirect } from "next/navigation";

export default function OldProjectPage({ params }: { params: { id: string } }) {
  redirect(`/project/${params.id}`);
}
