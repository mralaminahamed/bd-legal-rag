import "@/styles/globals.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { Toaster } from "sonner";
import { queryClient } from "@/lib/queryClient";
import { LangProvider } from "@/lib/langContext";
import { ThemeProvider } from "@/lib/themeContext";
import { router } from "@/app/routes";

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <LangProvider>
          <RouterProvider router={router} />
          <Toaster position="top-right" richColors />
        </LangProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
