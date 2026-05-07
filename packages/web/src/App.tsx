import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Home } from "./routes/home";
import { Login } from "./routes/login";
import { MeetingDetail } from "./routes/meetings/detail";
import { MeetingsList } from "./routes/meetings/list";
import { NewMeeting } from "./routes/meetings/new";
import { Signup } from "./routes/signup";
import { TotpEnroll } from "./routes/totp/enroll";
import { TotpVerify } from "./routes/totp/verify";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/meetings" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/totp/enroll" element={<TotpEnroll />} />
        <Route path="/totp/verify" element={<TotpVerify />} />
        <Route path="/home" element={<Home />} />
        <Route path="/meetings" element={<MeetingsList />} />
        <Route path="/meetings/new" element={<NewMeeting />} />
        <Route path="/meetings/:id" element={<MeetingDetail />} />
      </Routes>
    </BrowserRouter>
  );
}
