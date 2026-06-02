import { useEffect } from "react";
import { createBrowserRouter, useNavigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { ActsPage } from "@/pages/ActsPage";
import { ActReaderPage } from "@/pages/ActReaderPage";
import { PlaygroundPage } from "@/pages/PlaygroundPage";
import { ThreadsPage } from "@/pages/ThreadsPage";

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
      { path: "acts/:slug/read", element: <ActReaderPage /> },
      { path: "acts/:slug/read/:sectionId", element: <ActReaderPage /> },
      { path: "threads", element: <ThreadsPage /> },
      { path: "playground", element: <PlaygroundRedirect /> },
      { path: "playground/:threadId", element: <PlaygroundPage /> },
    ],
  },
]);
