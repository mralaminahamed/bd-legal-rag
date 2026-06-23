import { useEffect } from "react";
import { createBrowserRouter, useNavigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { DashboardPage } from "@/pages/DashboardPage";
import { ActsPage } from "@/pages/ActsPage";
import { ActReaderPage } from "@/pages/ActReaderPage";
import { PlaygroundPage } from "@/pages/PlaygroundPage";
import { ThreadsPage } from "@/pages/ThreadsPage";
import { SettingsPage } from "@/pages/SettingsPage";

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
      { index: true, element: <ErrorBoundary><DashboardPage /></ErrorBoundary> },
      { path: "acts", element: <ErrorBoundary><ActsPage /></ErrorBoundary> },
      { path: "acts/:slug/read", element: <ErrorBoundary><ActReaderPage /></ErrorBoundary> },
      { path: "acts/:slug/read/:sectionId", element: <ErrorBoundary><ActReaderPage /></ErrorBoundary> },
      { path: "threads", element: <ErrorBoundary><ThreadsPage /></ErrorBoundary> },
      { path: "playground", element: <PlaygroundRedirect /> },
      { path: "playground/:threadId", element: <ErrorBoundary><PlaygroundPage /></ErrorBoundary> },
      { path: "settings", element: <ErrorBoundary><SettingsPage /></ErrorBoundary> },
    ],
  },
]);
