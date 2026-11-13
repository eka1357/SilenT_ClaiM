import { MotionConfig } from "motion/react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Adjuster } from "@/app/routes/Adjuster";
import { Console } from "@/app/routes/Console";
import { DevKit } from "@/app/routes/DevKit";
import { Lab } from "@/app/routes/Lab";
import { Merchant } from "@/app/routes/Merchant";
import { Privacy } from "@/app/routes/Privacy";
import { Toaster } from "@/components/ui/sonner";

export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/console" replace />} />
          <Route path="/console" element={<Console />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/merchant" element={<Merchant />} />
          <Route path="/adjuster" element={<Adjuster />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/dev/kit" element={<DevKit />} />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </MotionConfig>
  );
}
export default App;

