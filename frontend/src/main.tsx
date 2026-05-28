import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./styles/globals.css";
import App from "./App.tsx";
import { GoogleAnalytics } from "./components/GoogleAnalytics.tsx";

const rootElement = document.getElementById("root")!;
if (rootElement.dataset.prerendered === "true") {
  rootElement.innerHTML = "";
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <GoogleAnalytics />
      <App />
    </BrowserRouter>
  </StrictMode>
);
