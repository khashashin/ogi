import { useEffect } from "react";
import { useLocation } from "react-router";
import ReactGA from "react-ga4";

export function GoogleAnalytics() {
  const location = useLocation();

  useEffect(() => {
    // We expect this to be defined in .env
    const measurementId = import.meta.env.VITE_GA_MEASUREMENT_ID;
    if (measurementId) {
      ReactGA.initialize(measurementId);
    } else {
      console.warn("Google Analytics disabled (VITE_GA_MEASUREMENT_ID is missing)");
    }
  }, []);

  useEffect(() => {
    // Send a pageview event whenever the route changes
    ReactGA.send({ 
      hitType: "pageview", 
      page: location.pathname + location.search 
    });
  }, [location]);

  return null; // This component is invisible
}
