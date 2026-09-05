import React from "react";
import ReactDOM from "react-dom/client";
import { createTheme, MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
import App from "./App";

const theme = createTheme({
  primaryColor: "flora",
  primaryShade: 5,
  defaultRadius: "md",
  fontFamily: 'Inter, "Segoe UI", system-ui, sans-serif',
  headings: {
    fontFamily: 'Inter, "Segoe UI", system-ui, sans-serif',
    fontWeight: "600",
  },
  colors: {
    flora: [
      "#e5fff5",
      "#c2fbe4",
      "#91efce",
      "#64dfb8",
      "#42d3a7",
      "#36bf97",
      "#239b7c",
      "#1c7a63",
      "#185f4f",
      "#134c40",
    ],
    dark: [
      "#e5eaf0",
      "#c4cdd7",
      "#919dab",
      "#64717e",
      "#35414f",
      "#26313d",
      "#1b2530",
      "#141d26",
      "#101820",
      "#0b1219",
    ],
  },
  components: {
    Button: { defaultProps: { size: "sm" } },
    Tooltip: { defaultProps: { withArrow: true } },
    Modal: {
      defaultProps: {
        centered: true,
        overlayProps: { backgroundOpacity: 0.65, blur: 5 },
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider theme={theme} forceColorScheme="dark">
      <App />
    </MantineProvider>
  </React.StrictMode>,
);
