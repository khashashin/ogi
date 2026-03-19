import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./styles/globals.css";
import App from "./App.tsx";
import { GoogleAnalytics } from "./components/GoogleAnalytics.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <GoogleAnalytics />
      <App />
    </BrowserRouter>
  </StrictMode>
);
