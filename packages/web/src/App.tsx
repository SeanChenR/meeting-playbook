import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Home } from "./routes/home";
import { Login } from "./routes/login";
import { Signup } from "./routes/signup";
import { TotpEnroll } from "./routes/totp/enroll";
import { TotpVerify } from "./routes/totp/verify";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/totp/enroll" element={<TotpEnroll />} />
        <Route path="/totp/verify" element={<TotpVerify />} />
        <Route path="/home" element={<Home />} />
      </Routes>
    </BrowserRouter>
  );
}
