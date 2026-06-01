import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { ActsPage } from "@/pages/ActsPage";
import { PlaygroundPage } from "@/pages/PlaygroundPage";
import { SettingsPage } from "@/pages/SettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "acts", element: <ActsPage /> },
      { path: "playground", element: <PlaygroundPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);
