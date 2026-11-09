import type { Metadata } from "next";
import { Workspace } from "./workspace";

export const metadata: Metadata = {
  title: "Workspace · pRAwG",
  description: "Chat with and manage your private knowledge base.",
};

export default function AppPage() {
  return <Workspace />;
}
