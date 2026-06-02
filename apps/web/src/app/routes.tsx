import { useEffect } from "react";
import { createBrowserRouter, useNavigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { ActsPage } from "@/pages/ActsPage";
import { CorpusPage } from "@/pages/CorpusPage";
import { PlaygroundPage } from "@/pages/PlaygroundPage";

// /playground → redirect to /playground/:uuid (new thread each visit)
function PlaygroundRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate(`/playground/${crypto.randomUUID()}`, { replace: true });
  }, [navigate]);
  return null;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "acts", element: <ActsPage /> },
      { path: "corpus", element: <CorpusPage /> },
      { path: "playground", element: <PlaygroundRedirect /> },
      { path: "playground/:threadId", element: <PlaygroundPage /> },
    ],
  },
]);
